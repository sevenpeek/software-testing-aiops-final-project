"""Dry-run recovery recommendation planner for the AIOps Agent.

This module only generates advice and command drafts. It never executes
kubectl and never changes Kubernetes cluster state.
"""

from __future__ import annotations

from typing import Any


def _service_cpu_rate(prometheus_metrics: dict[str, Any] | None) -> float | None:
    value = ((prometheus_metrics or {}).get("summary") or {}).get("service_cpu_rate")
    return value if isinstance(value, (int, float)) else None


def _memory_working_set_mib(prometheus_metrics: dict[str, Any] | None) -> float | None:
    value = ((prometheus_metrics or {}).get("summary") or {}).get("service_memory_working_set_mib")
    return value if isinstance(value, (int, float)) else None


def _readonly_commands(namespace: str, service_name: str) -> list[str]:
    return [
        f"kubectl get pods -n {namespace} | findstr {service_name}",
        f"kubectl logs deployment/{service_name} -n {namespace} --tail=100",
        f"kubectl get events -n {namespace} --sort-by=.lastTimestamp",
    ]


def _fault_type(config: dict[str, Any], root_metric: str, scenario: str) -> str:
    configured = str(config.get("faults", {}).get("default_fault_type") or "").strip()
    metric = root_metric.lower()
    scenario_text = scenario.lower()
    if "memory" in metric or "memory" in scenario_text:
        return "memory_stress"
    if "podkill" in scenario_text or "pod-kill" in scenario_text or "pod_kill" in scenario_text:
        return "pod_kill"
    if "network" in scenario_text or "latency" in metric or "latency" in scenario_text:
        return "network_delay"
    return configured or "cpu_stress"


def _is_prometheus_available(prometheus_metrics: dict[str, Any] | None) -> bool:
    return bool((prometheus_metrics or {}).get("prometheus_available"))


def _has_explicit_pod_kill_evidence(kubernetes_evidence: dict[str, Any] | None) -> bool:
    evidence = kubernetes_evidence or {}
    event_sources: list[str] = []
    event_sources.append(str(evidence.get("recent_events") or ""))
    event_sources.extend(str(item) for item in (evidence.get("recent_warning_events") or []))
    event_sources.extend(str(item) for item in (evidence.get("last_event_messages") or []))
    event_text = "\n".join(event_sources).lower()
    pod_kill_keywords = (
        "podchaos",
        "pod-chaos",
        "pod_kill",
        "pod-kill",
        "chaos-mesh",
        "chaos mesh",
        "paymentservice-pod-kill",
    )
    return any(keyword in event_text for keyword in pod_kill_keywords)


def generate_recovery_plan(
    config: dict[str, Any],
    usad_result: dict[str, Any],
    kpiroot_result: dict[str, Any],
    kubernetes_evidence: dict[str, Any] | None,
    prometheus_metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    """Generate a dry-run recovery plan from diagnosis evidence."""

    recovery_config = config.get("recovery", {})
    faults_config = config.get("faults", {})
    enabled = bool(recovery_config.get("enabled", False))
    dry_run = bool(recovery_config.get("dry_run", True))
    execute_recovery = bool(recovery_config.get("execute_recovery", False))
    cpu_pressure_threshold = float(recovery_config.get("cpu_pressure_threshold", 0.05))
    memory_pressure_threshold_mib = float(
        faults_config.get("memory_pressure_threshold_mib", recovery_config.get("memory_pressure_threshold_mib", 150))
    )
    execute_enabled = bool(enabled and execute_recovery and config.get("agent", {}).get("enable_recovery", False) and not dry_run)

    namespace = config.get("system", {}).get("namespace") or "online-boutique"
    service_name = kpiroot_result.get("top_service") or faults_config.get("default_service") or "paymentservice"
    root_metric = kpiroot_result.get("top_metric") or "<unknown-metric>"
    scenario = kpiroot_result.get("scenario") or ""
    health_status = (kubernetes_evidence or {}).get("health_status")
    deployment_available = (kubernetes_evidence or {}).get("deployment_available")
    pod_ready = (kubernetes_evidence or {}).get("pod_ready")
    pod_restart_count = int((kubernetes_evidence or {}).get("pod_restart_count") or 0)
    has_event_warnings = bool((kubernetes_evidence or {}).get("has_event_warnings"))
    service_cpu_rate = _service_cpu_rate(prometheus_metrics)
    memory_mib = _memory_working_set_mib(prometheus_metrics)
    prometheus_available = _is_prometheus_available(prometheus_metrics)
    root_metric_lower = str(root_metric).lower()
    fault_type = _fault_type(config, str(root_metric), str(scenario))
    explicit_pod_kill_evidence = _has_explicit_pod_kill_evidence(kubernetes_evidence)
    cpu_below_threshold = service_cpu_rate is not None and service_cpu_rate < cpu_pressure_threshold
    memory_below_threshold = memory_mib is not None and memory_mib < memory_pressure_threshold_mib

    recommended_actions: list[str] = []
    suggested_commands: list[str] = []

    if not enabled:
        decision = "disabled"
        risk_level = "low"
        recommended_actions.append("Recovery planning is disabled in config.")
        suggested_commands.extend(_readonly_commands(namespace, service_name))
    elif service_cpu_rate is not None and service_cpu_rate >= cpu_pressure_threshold:
        fault_type = "cpu_stress"
        decision = "cpu_pressure_investigation"
        risk_level = "medium"
        recommended_actions.extend(
            [
                (
                    f"Prometheus service_cpu_rate={service_cpu_rate:.6f} is above threshold "
                    f"{cpu_pressure_threshold:.6f}; this supports a {service_name} CPU pressure investigation."
                ),
                "Continue checking CPU, logs, Events, and pod-level runtime state before taking action.",
                "Scaling or restart commands are only drafts and require manual confirmation.",
            ]
        )
        suggested_commands.extend(
            [
                *(_readonly_commands(namespace, service_name)),
                f"kubectl top pod -n {namespace}",
                f"# Run only after manual confirmation: kubectl rollout restart deployment/{service_name} -n {namespace}",
            ]
        )
    elif fault_type == "memory_stress" and memory_mib is not None and memory_mib >= memory_pressure_threshold_mib:
        fault_type = "memory_stress"
        decision = "memory_pressure_investigation"
        risk_level = "medium"
        recommended_actions.extend(
            [
                (
                    f"Prometheus memory working set={memory_mib:.2f} MiB is above threshold "
                    f"{memory_pressure_threshold_mib:.2f} MiB."
                ),
                "Check for memory leak symptoms, container memory limits, OOM-related Events, and recent logs.",
                "Keep recovery dry-run; do not restart automatically.",
            ]
        )
        suggested_commands.extend(
            [
                *(_readonly_commands(namespace, service_name)),
                f"kubectl describe deployment/{service_name} -n {namespace}",
                f"kubectl describe pods -n {namespace} -l app={service_name}",
            ]
        )
    elif fault_type in ("cpu_stress", "generic", "") and health_status == "healthy" and prometheus_available and cpu_below_threshold and memory_below_threshold:
        fault_type = "cpu_stress" if fault_type in ("", "generic") else fault_type
        decision = "observe"
        risk_level = "low"
        recommended_actions.extend(
            [
                "Current Kubernetes health is healthy and real-time Prometheus CPU/memory metrics are below thresholds.",
                "No explicit Pod Kill, CPU pressure, or memory pressure evidence is present; keep observing.",
            ]
        )
        suggested_commands.extend(_readonly_commands(namespace, service_name))
    elif fault_type == "network_delay":
        fault_type = "network_delay"
        decision = "network_latency_manual_review"
        risk_level = "medium"
        recommended_actions.extend(
            [
                "Network delay experiments need application latency and error-rate metrics for strong diagnosis.",
                "Check service dependency paths, frontend/request logs, and Prometheus latency/error metrics after they are added.",
                "Current version treats network delay as an extension demo and keeps the final decision as manual review.",
            ]
        )
        suggested_commands.extend(_readonly_commands(namespace, service_name))
    elif fault_type == "pod_kill" or explicit_pod_kill_evidence:
        fault_type = "pod_kill"
        if explicit_pod_kill_evidence or (fault_type == "pod_kill" and (pod_restart_count > 0 or has_event_warnings)):
            if health_status == "healthy" and pod_ready is True and deployment_available is True:
                decision = "pod_recovery_observe"
                risk_level = "low"
                recommended_actions.extend(
                    [
                        "Pod restart/Event evidence exists, but the current Pod and Deployment appear recovered.",
                        "Observe the service and preserve the report as evidence of transient Pod recovery.",
                    ]
                )
            else:
                decision = "pod_restart_investigation"
                risk_level = "medium"
                recommended_actions.extend(
                    [
                        "Pod restart or warning Event evidence was detected; inspect Events and logs first.",
                        "Confirm whether the Deployment has restored the desired replica state.",
                    ]
                )
        else:
            decision = "pod_recovery_observe"
            risk_level = "low"
            recommended_actions.append("No clear restart evidence is visible yet; keep observing Pod status and Events.")
        suggested_commands.extend(
            [
                *(_readonly_commands(namespace, service_name)),
                f"kubectl describe pods -n {namespace} -l app={service_name}",
            ]
        )
    elif health_status == "healthy" and service_cpu_rate is not None and service_cpu_rate < cpu_pressure_threshold:
        decision = "observe"
        risk_level = "low"
        recommended_actions.extend(
            [
                "Current real-time Kubernetes and Prometheus evidence is stable; immediate restart is not recommended.",
                "Continue observing Prometheus metrics and keep the diagnosis report for comparison.",
            ]
        )
        suggested_commands.extend(_readonly_commands(namespace, service_name))
    elif health_status == "image_pull_error":
        decision = "fix_image_pull"
        risk_level = "high"
        recommended_actions.extend(
            [
                "Prioritize image pull troubleshooting.",
                "Check image address, proxy, imagePullPolicy, and local Minikube image cache.",
            ]
        )
        suggested_commands.extend(
            [
                f"kubectl describe deployment/{service_name} -n {namespace}",
                f"kubectl get events -n {namespace} --sort-by=.lastTimestamp",
                f"# Run only after manual confirmation: kubectl rollout restart deployment/{service_name} -n {namespace}",
            ]
        )
    elif health_status == "crash_loop":
        decision = "inspect_crash_loop"
        risk_level = "high"
        recommended_actions.extend(
            [
                "Inspect current logs and previous container logs before taking any recovery action.",
                "Locate startup failure, dependency failure, or configuration error first.",
            ]
        )
        suggested_commands.extend(
            [
                f"kubectl logs deployment/{service_name} -n {namespace} --tail=100",
                f"kubectl logs deployment/{service_name} -n {namespace} --previous --tail=100",
            ]
        )
    elif health_status == "not_found":
        decision = "service_not_found"
        risk_level = "medium"
        recommended_actions.extend(
            [
                "Check namespace, service name mapping, and whether the Deployment exists.",
                "Confirm that the KPIRoot service name matches Kubernetes deployment/service names.",
            ]
        )
        suggested_commands.extend(
            [
                f"kubectl get deploy -n {namespace}",
                f"kubectl get svc -n {namespace}",
                f"kubectl get pods -n {namespace} -o wide",
            ]
        )
    else:
        decision = "manual_review"
        risk_level = "medium"
        recommended_actions.extend(
            [
                "Current evidence is insufficient for a specific recovery recommendation.",
                "Review Pod status, logs, Events, and Prometheus metrics before taking action.",
            ]
        )
        suggested_commands.extend(_readonly_commands(namespace, service_name))

    safety_notes = [
        "execute_recovery=false / dry_run=true: Agent only generates recovery advice and never executes real recovery commands.",
        "agent.enable_recovery=false protects against automatic recovery.",
        "Commands such as rollout restart are shown only as manually confirmed drafts.",
        f"CPU pressure threshold: {cpu_pressure_threshold}.",
        f"Memory pressure threshold: {memory_pressure_threshold_mib} MiB.",
    ]
    if memory_mib is not None:
        safety_notes.append(f"Current memory working set: {memory_mib:.2f} MiB.")

    return {
        "enabled": enabled,
        "execute_enabled": execute_enabled,
        "execute_recovery": execute_recovery,
        "dry_run": dry_run,
        "service_name": service_name,
        "root_metric": root_metric,
        "fault_type": fault_type,
        "decision": decision,
        "risk_level": risk_level,
        "recommended_actions": recommended_actions,
        "suggested_commands": suggested_commands,
        "safety_notes": safety_notes,
    }
