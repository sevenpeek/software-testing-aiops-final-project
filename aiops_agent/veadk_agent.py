"""Optional VeADK / LLM-style Agent wrapper for aiops_agent.

The stable rule orchestration still lives in run_agent.py. This file adds an
optional tool-calling layer that can run without an API key.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable

try:  # VeADK APIs may vary by version; keep this import optional.
    import veadk  # type: ignore  # noqa: F401

    VEADK_AVAILABLE = True
except Exception:
    veadk = None  # type: ignore
    VEADK_AVAILABLE = False

from tools.kpiroot_tool import analyze_kpiroot
from tools.kubernetes_tool import collect_kubernetes_evidence
from tools.prometheus_tool import collect_prometheus_metrics
from tools.recovery_tool import generate_recovery_plan as build_recovery_plan
from tools.report_tool import generate_report
from tools.usad_tool import analyze_usad


ARK_DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


def _load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def _json_dumps(value: Any) -> str:
    return json.dumps(_to_jsonable(value), ensure_ascii=False, indent=2)


def _resolve_llm_config() -> dict[str, Any]:
    ark_api_key = os.environ.get("ARK_API_KEY")
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    api_key = ark_api_key or openai_api_key
    provider = "ark" if ark_api_key else "openai" if openai_api_key else None
    base_url = os.environ.get("ARK_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    if ark_api_key and not base_url:
        base_url = ARK_DEFAULT_BASE_URL
    model = os.environ.get("ARK_MODEL") or os.environ.get("OPENAI_MODEL")
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "provider": provider,
        "ark_api_key_detected": bool(ark_api_key),
        "openai_api_key_detected": bool(openai_api_key),
    }


def _safe_tool_result_for_llm(tool_name: str, result: dict[str, Any], local_tools: "LocalAIOpsTools") -> dict[str, Any]:
    """Return a compact result for the LLM, without raw Kubernetes logs."""
    if "error" in result:
        return {"error": result.get("error")}

    if tool_name == "query_usad_result":
        statistics = result.get("statistics") or {}
        return {
            "has_anomaly": statistics.get("has_anomaly"),
            "anomaly_windows": statistics.get("anomaly_windows"),
            "max_anomaly_score": statistics.get("max_anomaly_score"),
            "threshold": statistics.get("threshold"),
            "warnings": result.get("warnings"),
        }

    if tool_name == "query_kpiroot_result":
        return {
            "top_service": result.get("top_service"),
            "top_metric": result.get("top_metric"),
            "top_score": result.get("top_score"),
            "warnings": result.get("warnings"),
        }

    if tool_name == "query_kubernetes_evidence":
        return {
            "service_name": result.get("service_name"),
            "kubernetes_health_status": result.get("health_status"),
            "kubectl_available": result.get("kubectl_available"),
            "event_warning_count": result.get("event_warning_count"),
            "has_event_warnings": result.get("has_event_warnings"),
            "event_interpretation": result.get("event_interpretation"),
            "warnings": result.get("warnings"),
        }

    if tool_name == "query_prometheus_metrics":
        summary = result.get("summary") or {}
        return {
            "prometheus_available": result.get("prometheus_available"),
            "service_cpu_rate": summary.get("service_cpu_rate"),
            "service_memory_working_set_mib": summary.get("service_memory_working_set_mib"),
            "service_container_count": summary.get("service_container_count"),
            "interpretation": summary.get("interpretation"),
            "warnings": result.get("warnings"),
        }

    if tool_name == "generate_recovery_plan":
        return {
            "recovery_decision": result.get("decision"),
            "recovery_risk_level": result.get("risk_level"),
            "dry_run": result.get("dry_run"),
            "execute_recovery": result.get("execute_recovery"),
            "service_name": result.get("service_name"),
            "root_metric": result.get("root_metric"),
            "recommended_actions": result.get("recommended_actions"),
            "safety_notes": result.get("safety_notes"),
        }

    if tool_name == "run_full_diagnosis":
        return _safe_diagnosis_summary(result, local_tools)

    return {"status": "ok"}


def _safe_diagnosis_summary(result: dict[str, Any], local_tools: "LocalAIOpsTools") -> dict[str, Any]:
    prometheus_summary = (local_tools.prometheus_metrics or {}).get("summary", {})
    return {
        "has_anomaly": result.get("has_anomaly"),
        "top_service": result.get("top_service"),
        "top_metric": result.get("top_metric"),
        "kubernetes_health_status": result.get("kubernetes_health_status"),
        "prometheus_available": result.get("prometheus_available"),
        "service_cpu_rate": result.get("service_cpu_rate"),
        "service_memory_working_set_mib": result.get(
            "service_memory_working_set_mib",
            prometheus_summary.get("service_memory_working_set_mib"),
        ),
        "recovery_decision": result.get("recovery_decision"),
        "recovery_risk_level": result.get("recovery_risk_level"),
        "dry_run": result.get("dry_run"),
        "report_path": result.get("report_path"),
    }


class LocalAIOpsTools:
    """Tool facade used by both fallback and OpenAI-compatible tool calling."""

    def __init__(self, config: dict[str, Any], project_root: Path):
        self.config = config
        self.project_root = project_root
        self.usad_result: dict[str, Any] | None = None
        self.kpiroot_result: dict[str, Any] | None = None
        self.kubernetes_evidence: dict[str, Any] | None = None
        self.prometheus_metrics: dict[str, Any] | None = None
        self.recovery_plan: dict[str, Any] | None = None
        self.report_path: Path | None = None

    def query_usad_result(self) -> dict[str, Any]:
        self.usad_result = analyze_usad(self.config, self.project_root)
        return {
            "dataset_name": self.usad_result.get("dataset_name"),
            "statistics": self.usad_result.get("statistics"),
            "summary": self.usad_result.get("summary"),
            "warnings": self.usad_result.get("warnings"),
        }

    def query_kpiroot_result(self) -> dict[str, Any]:
        self.kpiroot_result = analyze_kpiroot(self.config, self.project_root)
        return {
            "scenario": self.kpiroot_result.get("scenario"),
            "top_metric": self.kpiroot_result.get("top_metric"),
            "top_service": self.kpiroot_result.get("top_service"),
            "top_score": self.kpiroot_result.get("top_score"),
            "top_candidates": self.kpiroot_result.get("top_candidates"),
            "warnings": self.kpiroot_result.get("warnings"),
        }

    def query_kubernetes_evidence(self, service_name: str | None = None) -> dict[str, Any]:
        service = service_name or self._top_service()
        self.kubernetes_evidence = collect_kubernetes_evidence(self.config, service)
        return self.kubernetes_evidence

    def query_prometheus_metrics(self, service_name: str | None = None) -> dict[str, Any]:
        service = service_name or self._top_service()
        self.prometheus_metrics = collect_prometheus_metrics(self.config, service)
        return self.prometheus_metrics

    def generate_recovery_plan(self, service_name: str | None = None) -> dict[str, Any]:
        if self.usad_result is None:
            self.query_usad_result()
        if self.kpiroot_result is None:
            self.query_kpiroot_result()

        if service_name:
            self.kpiroot_result = dict(self.kpiroot_result or {})
            self.kpiroot_result["top_service"] = service_name

        if self.kubernetes_evidence is None:
            self.query_kubernetes_evidence(service_name)
        if self.prometheus_metrics is None:
            self.query_prometheus_metrics(service_name)

        self.recovery_plan = build_recovery_plan(
            self.config,
            self.usad_result or {},
            self.kpiroot_result or {},
            self.kubernetes_evidence or {},
            self.prometheus_metrics or {},
        )
        return self.recovery_plan

    def run_full_diagnosis(self) -> dict[str, Any]:
        self.usad_result = analyze_usad(self.config, self.project_root)
        self.kpiroot_result = analyze_kpiroot(self.config, self.project_root)
        service = self.kpiroot_result.get("top_service")

        if self.config.get("kubernetes", {}).get("enabled") and service:
            self.kubernetes_evidence = collect_kubernetes_evidence(self.config, service)
        else:
            self.kubernetes_evidence = {"enabled": False, "health_status": "disabled", "warnings": []}

        if self.config.get("prometheus", {}).get("enabled") and service:
            self.prometheus_metrics = collect_prometheus_metrics(self.config, service)
        else:
            self.prometheus_metrics = {"enabled": False, "prometheus_available": False, "summary": {}, "warnings": []}

        self.recovery_plan = build_recovery_plan(
            self.config,
            self.usad_result,
            self.kpiroot_result,
            self.kubernetes_evidence,
            self.prometheus_metrics,
        )
        self.report_path = generate_report(
            self.config,
            self.project_root,
            self.usad_result,
            self.kpiroot_result,
            self.kubernetes_evidence,
            self.prometheus_metrics,
            self.recovery_plan,
        )

        return {
            "report_path": str(self.report_path),
            "has_anomaly": self.usad_result.get("statistics", {}).get("has_anomaly"),
            "top_service": self.kpiroot_result.get("top_service"),
            "top_metric": self.kpiroot_result.get("top_metric"),
            "kubernetes_health_status": self.kubernetes_evidence.get("health_status"),
            "prometheus_available": self.prometheus_metrics.get("prometheus_available"),
            "service_cpu_rate": self.prometheus_metrics.get("summary", {}).get("service_cpu_rate"),
            "service_memory_working_set_mib": self.prometheus_metrics.get("summary", {}).get(
                "service_memory_working_set_mib"
            ),
            "recovery_decision": self.recovery_plan.get("decision"),
            "recovery_risk_level": self.recovery_plan.get("risk_level"),
            "dry_run": self.recovery_plan.get("dry_run"),
        }

    def _top_service(self) -> str | None:
        if self.kpiroot_result is None:
            self.query_kpiroot_result()
        return (self.kpiroot_result or {}).get("top_service")


def _tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "query_usad_result",
                "description": "Read USAD anomaly detection output and return anomaly summary.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_kpiroot_result",
                "description": "Read KPIRoot output and return root-cause ranking summary.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_kubernetes_evidence",
                "description": "Read-only Kubernetes query for Pod, Deployment, Service, Event and Log evidence.",
                "parameters": {
                    "type": "object",
                    "properties": {"service_name": {"type": "string"}},
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_prometheus_metrics",
                "description": "Read-only Prometheus query for service CPU, memory and container metrics.",
                "parameters": {
                    "type": "object",
                    "properties": {"service_name": {"type": "string"}},
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_recovery_plan",
                "description": "Generate a dry-run recovery plan. Does not execute recovery commands.",
                "parameters": {
                    "type": "object",
                    "properties": {"service_name": {"type": "string"}},
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_full_diagnosis",
                "description": "Run the full rule-based diagnosis flow and generate diagnosis_report.md.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
    ]


def _tool_mapping(local_tools: LocalAIOpsTools) -> dict[str, Callable[..., dict[str, Any]]]:
    return {
        "query_usad_result": lambda: local_tools.query_usad_result(),
        "query_kpiroot_result": lambda: local_tools.query_kpiroot_result(),
        "query_kubernetes_evidence": lambda service_name=None: local_tools.query_kubernetes_evidence(service_name),
        "query_prometheus_metrics": lambda service_name=None: local_tools.query_prometheus_metrics(service_name),
        "generate_recovery_plan": lambda service_name=None: local_tools.generate_recovery_plan(service_name),
        "run_full_diagnosis": lambda: local_tools.run_full_diagnosis(),
    }


def _run_fallback(local_tools: LocalAIOpsTools, reason: str | None = None) -> int:
    if reason:
        print(reason, flush=True)
    else:
        print("No ARK_API_KEY or OPENAI_API_KEY found. Running deterministic fallback diagnosis.", flush=True)
    result = local_tools.run_full_diagnosis()
    print("Fallback diagnosis completed.", flush=True)
    print(_json_dumps(_safe_diagnosis_summary(result, local_tools)), flush=True)
    return 0


def _run_openai_tool_calling(alert: str, local_tools: LocalAIOpsTools, llm_config: dict[str, Any]) -> int:
    try:
        from openai import OpenAI
    except Exception:
        print("OpenAI SDK is not installed. Please run: pip install openai", flush=True)
        return _run_fallback(local_tools, "OpenAI SDK unavailable. Running deterministic fallback diagnosis.")

    api_key = llm_config.get("api_key")
    base_url = llm_config.get("base_url")
    model = llm_config.get("model")
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    tool_map = _tool_mapping(local_tools)

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are an AIOps diagnosis agent. Use tools to inspect USAD, KPIRoot, Kubernetes, Prometheus, "
                "and dry-run recovery evidence. Never execute recovery commands or mutate Kubernetes state."
            ),
        },
        {"role": "user", "content": alert},
    ]

    final_text = ""
    for _ in range(5):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=_tool_schemas(),
            tool_choice="auto",
        )
        message = response.choices[0].message
        tool_calls = message.tool_calls or []
        messages.append(message.model_dump())
        if not tool_calls:
            final_text = message.content or ""
            break

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            print(f"[Agent Tool Call] {tool_name}", flush=True)
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
                result = tool_map[tool_name](**arguments)
            except Exception as exc:  # pragma: no cover - defensive for model-provided args
                result = {"error": str(exc)}
            safe_result = _safe_tool_result_for_llm(tool_name, result, local_tools)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": _json_dumps(safe_result),
                }
            )

    if local_tools.report_path is None:
        print("[Agent Tool Call] run_full_diagnosis", flush=True)
        local_tools.run_full_diagnosis()

    print("Final Agent Diagnosis:", flush=True)
    print(final_text or "Diagnosis report generated. Please review aiops_agent/outputs/diagnosis_report.md.", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Optional VeADK / LLM Agent wrapper for aiops_agent")
    parser.add_argument("--config", default="aiops_agent/config.json", help="Path to config.json")
    parser.add_argument("--alert", default="Online Boutique alert", help="Alert text for the Agent")
    parser.add_argument("--llm", action="store_true", help="Enable OpenAI-compatible LLM tool calling")
    args = parser.parse_args()

    agent_dir = Path(__file__).resolve().parent
    project_root = agent_dir.parent
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = project_root / config_path

    if not VEADK_AVAILABLE:
        print("VeADK is not installed. Please run: pip install veadk-python", flush=True)

    config = _load_config(config_path)
    local_tools = LocalAIOpsTools(config, project_root)
    llm_config = _resolve_llm_config()

    if llm_config["ark_api_key_detected"]:
        print("ARK_API_KEY detected. Using Volcengine Ark OpenAI-compatible mode.", flush=True)
    elif llm_config["openai_api_key_detected"]:
        print("OPENAI_API_KEY detected. Using OpenAI-compatible mode.", flush=True)

    if not args.llm:
        return _run_fallback(local_tools, "LLM mode is disabled. Running deterministic fallback diagnosis.")

    if not llm_config["api_key"]:
        return _run_fallback(local_tools)

    if not llm_config["model"]:
        return _run_fallback(
            local_tools,
            "API key detected but no model is configured. Please set ARK_MODEL or OPENAI_MODEL.",
        )

    try:
        return _run_openai_tool_calling(args.alert, local_tools, llm_config)
    except Exception as exc:
        return _run_fallback(
            local_tools,
            f"LLM API call failed: {exc}. Running deterministic fallback diagnosis.",
        )


if __name__ == "__main__":
    raise SystemExit(main())
