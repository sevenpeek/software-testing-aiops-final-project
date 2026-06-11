"""Read-only Kubernetes evidence collection for the AIOps Agent."""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any


SENSITIVE_LOG_FIELDS = {
    "credit_card_number": "****",
    "credit_card_cvv": "***",
    "credit_card_expiration_year": "****",
    "credit_card_expiration_month": "**",
}


def _tail_lines(text: str, limit: int) -> str:
    lines = text.splitlines()
    if limit > 0 and len(lines) > limit:
        lines = lines[-limit:]
    return "\n".join(lines)


def _redact_sensitive_logs_with_count(text: str) -> tuple[str, int]:
    redacted = text
    replacement_count = 0
    for field, replacement in SENSITIVE_LOG_FIELDS.items():
        escaped_field = re.escape(field)

        quoted_value_pattern = re.compile(
            rf'(?P<prefix>\\*"{escaped_field}\\*"\s*:\s*\\*")(?P<value>\d+)(?P<suffix>\\*")',
            re.I,
        )
        redacted, count = quoted_value_pattern.subn(rf'\g<prefix>{replacement}\g<suffix>', redacted)
        replacement_count += count

        numeric_value_pattern = re.compile(
            rf'(?P<prefix>\\*"{escaped_field}\\*"\s*:\s*)(?P<value>\d+)',
            re.I,
        )
        def replace_numeric_value(match: re.Match[str]) -> str:
            prefix = match.group("prefix")
            quote = r'\"' if r'\"' in prefix else '"'
            return f"{prefix}{quote}{replacement}{quote}"

        redacted, count = numeric_value_pattern.subn(replace_numeric_value, redacted)
        replacement_count += count

        loose_pattern = re.compile(
            rf'(?P<prefix>\b{escaped_field}\b\s*[=:]\s*)(?P<quote>\\*")?(?P<value>\d+)(?P<suffix>\\*")?',
            re.I,
        )
        redacted, count = loose_pattern.subn(rf'\g<prefix>"{replacement}"', redacted)
        replacement_count += count

    redacted, count = re.subn(r'(?i)(visa\s+ending\s+)\d{4}\b', r'\1****', redacted)
    replacement_count += count
    return redacted, replacement_count


def _redact_sensitive_logs(text: str) -> str:
    return _redact_sensitive_logs_with_count(text)[0]


def _self_test_redaction() -> bool:
    plain_json = (
        '"credit_card_number":"4730638300025695",'
        '"credit_card_cvv":987,'
        '"credit_card_expiration_year":2078,'
        '"credit_card_expiration_month":2,'
        'Transaction processed: visa ending 5657'
    )
    escaped_json = (
        r'\"credit_card_number\":\"4730638300025695\",'
        r'\"credit_card_cvv\":987,'
        r'\"credit_card_expiration_year\":2078,'
        r'\"credit_card_expiration_month\":2,'
        r'Transaction processed: visa ending 5657'
    )
    combined = plain_json + "\n" + escaped_json
    redacted = _redact_sensitive_logs(combined)
    forbidden_patterns = [
        r'credit_card_number\\*"?\s*:\s*\\*"?\d+',
        r'credit_card_cvv\\*"?\s*:\s*\\*"?\d+',
        r'credit_card_expiration_year\\*"?\s*:\s*\\*"?\d+',
        r'credit_card_expiration_month\\*"?\s*:\s*\\*"?\d+',
        r'visa\s+ending\s+\d{4}\b',
    ]
    return not any(re.search(pattern, redacted, re.I) for pattern in forbidden_patterns)


def _run_kubectl(command: list[str], timeout_seconds: int, warnings: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        warnings.append(f"Command timed out after {timeout_seconds}s: {' '.join(command)}")
        return ""
    except FileNotFoundError:
        warnings.append(f"kubectl executable not found: {command[0]}")
        return ""
    except Exception as exc:  # pragma: no cover - defensive for local runtime issues
        warnings.append(f"Command failed unexpectedly: {' '.join(command)}; error={exc}")
        return ""

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode != 0:
        message = stderr or stdout or f"exit code {completed.returncode}"
        warnings.append(f"Command failed: {' '.join(command)}; {message}")
    return stdout


def _parse_health_status(pod_summary: str) -> str:
    text = pod_summary or ""
    if "ImagePullBackOff" in text or "ErrImagePull" in text:
        return "image_pull_error"
    if "CrashLoopBackOff" in text:
        return "crash_loop"
    if not text.strip() or "No resources found" in text:
        return "not_found"
    if "Running" in text and not any(token in text for token in ("ImagePullBackOff", "CrashLoopBackOff", "ErrImagePull")):
        return "healthy"
    return "unknown"


def _event_warning_lines(events: str) -> list[str]:
    keywords = ("Warning", "Unhealthy", "Failed", "BackOff")
    return [line for line in events.splitlines() if any(keyword.lower() in line.lower() for keyword in keywords)]


def _parse_int(value: str) -> int:
    match = re.search(r"\d+", value or "")
    return int(match.group(0)) if match else 0


def _parse_pod_table(pod_summary: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "selected_pod_names": [],
        "pod_restart_count": 0,
        "pod_ready": None,
        "pod_phase": "not_found",
    }
    lines = [line for line in (pod_summary or "").splitlines() if line.strip()]
    if len(lines) <= 1 or "No resources found" in (pod_summary or ""):
        return parsed

    ready_values: list[bool] = []
    phases: list[str] = []
    for line in lines[1:]:
        columns = re.split(r"\s+", line.strip())
        if len(columns) < 4:
            continue
        parsed["selected_pod_names"].append(columns[0])
        ready_text = columns[1]
        status_text = columns[2]
        restart_text = columns[3]
        phases.append(status_text)
        parsed["pod_restart_count"] += _parse_int(restart_text)
        ready_match = re.match(r"(?P<ready>\d+)/(?P<total>\d+)", ready_text)
        if ready_match:
            ready_values.append(int(ready_match.group("ready")) == int(ready_match.group("total")))

    if ready_values:
        parsed["pod_ready"] = all(ready_values)
    if phases:
        parsed["pod_phase"] = "Running" if all(phase == "Running" for phase in phases) else ",".join(sorted(set(phases)))
    return parsed


def _parse_deployment_available(deployment_summary: str) -> bool | None:
    lines = [line for line in (deployment_summary or "").splitlines() if line.strip()]
    if len(lines) <= 1 or "No resources found" in (deployment_summary or ""):
        return None
    columns = re.split(r"\s+", lines[1].strip())
    if len(columns) < 4:
        return None
    ready_match = re.match(r"(?P<ready>\d+)/(?P<desired>\d+)", columns[1])
    available = _parse_int(columns[3])
    if ready_match:
        desired = int(ready_match.group("desired"))
        ready = int(ready_match.group("ready"))
        return desired > 0 and ready == desired and available >= desired
    return available > 0


def _last_event_messages(events: str, limit: int = 5) -> list[str]:
    lines = [line for line in (events or "").splitlines() if line.strip()]
    if lines and lines[0].lower().startswith("last seen"):
        lines = lines[1:]
    return lines[-limit:]


def _event_interpretation(health_status: str, warning_count: int) -> str:
    if warning_count <= 0:
        return "当前 Event 未显示明显异常。"
    if health_status == "healthy":
        return (
            "近期 Event 中存在启动阶段的 Warning/Unhealthy 记录，但当前 Pod 和 Deployment 已处于 "
            "Running/Available，需结合时间和实时指标判断是否仍有影响。"
        )
    return "近期 Event 中存在 Warning/Unhealthy/Failed/BackOff 记录，这些事件可能与当前异常有关。"


def collect_kubernetes_evidence(config: dict[str, Any], service_name: str | None) -> dict[str, Any]:
    """Collect read-only Kubernetes evidence for a service.

    This function intentionally limits itself to kubectl get and kubectl logs.
    It does not modify cluster state.
    """

    kubernetes_config = config.get("kubernetes", {})
    enabled = bool(kubernetes_config.get("enabled", False))
    namespace = config.get("system", {}).get("namespace") or "online-boutique"
    kubectl = kubernetes_config.get("kubectl") or "kubectl"
    event_tail_lines = int(kubernetes_config.get("event_tail_lines", 30))
    log_tail_lines = int(kubernetes_config.get("log_tail_lines", 80))
    report_log_lines = int(kubernetes_config.get("report_log_lines", 20))
    timeout_seconds = int(kubernetes_config.get("command_timeout_seconds", 15))
    redact_logs = bool(kubernetes_config.get("redact_sensitive_logs", True))
    warnings: list[str] = []

    result: dict[str, Any] = {
        "enabled": enabled,
        "namespace": namespace,
        "service_name": service_name,
        "kubectl_available": False,
        "pod_summary": "",
        "deployment_summary": "",
        "service_summary": "",
        "recent_events": "",
        "logs_tail": "",
        "report_logs_tail": "",
        "logs_redacted": redact_logs,
        "logs_redaction_applied": False,
        "log_redaction_replacement_count": 0,
        "health_status": "unknown",
        "event_warning_count": 0,
        "has_event_warnings": False,
        "event_interpretation": "Kubernetes evidence collection has not run.",
        "pod_restart_count": 0,
        "pod_ready": None,
        "pod_phase": "unknown",
        "recent_warning_events": [],
        "last_event_messages": [],
        "deployment_available": None,
        "selected_pod_names": [],
        "warnings": warnings,
    }

    if not enabled:
        result["health_status"] = "disabled"
        result["event_interpretation"] = "Kubernetes evidence collection is disabled."
        return result
    if not service_name:
        warnings.append("Kubernetes evidence collection skipped because service_name is empty.")
        result["health_status"] = "not_found"
        result["event_interpretation"] = "No service name was available for Kubernetes evidence collection."
        return result
    if shutil.which(kubectl) is None:
        warnings.append(f"kubectl is not available in PATH: {kubectl}")
        result["kubectl_available"] = False
        result["health_status"] = "unknown"
        result["event_interpretation"] = "kubectl is unavailable, so Event evidence could not be collected."
        return result

    result["kubectl_available"] = True

    pod_command = [kubectl, "get", "pods", "-n", namespace, "-l", f"app={service_name}", "-o", "wide"]
    deploy_command = [kubectl, "get", "deploy", service_name, "-n", namespace, "-o", "wide"]
    svc_command = [kubectl, "get", "svc", service_name, "-n", namespace, "-o", "wide"]
    events_command = [kubectl, "get", "events", "-n", namespace, "--sort-by=.lastTimestamp"]
    logs_command = [kubectl, "logs", f"deployment/{service_name}", "-n", namespace, f"--tail={log_tail_lines}"]

    result["pod_summary"] = _run_kubectl(pod_command, timeout_seconds, warnings)
    result["deployment_summary"] = _run_kubectl(deploy_command, timeout_seconds, warnings)
    result["service_summary"] = _run_kubectl(svc_command, timeout_seconds, warnings)
    result["recent_events"] = _tail_lines(_run_kubectl(events_command, timeout_seconds, warnings), event_tail_lines)

    raw_logs = _tail_lines(_run_kubectl(logs_command, timeout_seconds, warnings), log_tail_lines)
    if redact_logs and raw_logs:
        result["logs_tail"], replacement_count = _redact_sensitive_logs_with_count(raw_logs)
        result["logs_redaction_applied"] = True
        result["log_redaction_replacement_count"] = replacement_count
    else:
        result["logs_tail"] = raw_logs
    result["report_logs_tail"] = _tail_lines(result["logs_tail"], report_log_lines)

    result["health_status"] = _parse_health_status(result["pod_summary"])
    warning_lines = _event_warning_lines(result["recent_events"])
    result["event_warning_count"] = len(warning_lines)
    result["has_event_warnings"] = bool(warning_lines)
    result["event_interpretation"] = _event_interpretation(result["health_status"], len(warning_lines))
    result.update(_parse_pod_table(result["pod_summary"]))
    result["deployment_available"] = _parse_deployment_available(result["deployment_summary"])
    result["recent_warning_events"] = warning_lines[-10:]
    result["last_event_messages"] = _last_event_messages(result["recent_events"], limit=5)

    return result
