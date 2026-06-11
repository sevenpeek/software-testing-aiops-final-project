"""ChaosMesh fault manifest and command helpers.

The functions in this module build manifests and command drafts only. They do
not execute kubectl and do not change Kubernetes cluster state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


SUPPORTED_FAULTS: dict[str, dict[str, str]] = {
    "cpu_stress": {
        "label": "CPU pressure",
        "status": "verified",
        "kind": "StressChaos",
        "resource": "stresschaos",
        "suffix": "cpu-stress",
        "crd": "stresschaos.chaos-mesh.org",
        "decision": "cpu_pressure_investigation",
        "basis": "service_cpu_rate",
        "limitation": "This is the fully verified demo scenario for paymentservice.",
    },
    "memory_stress": {
        "label": "Memory pressure",
        "status": "experimental",
        "kind": "StressChaos",
        "resource": "stresschaos",
        "suffix": "memory-stress",
        "crd": "stresschaos.chaos-mesh.org",
        "decision": "memory_pressure_investigation",
        "basis": "service_memory_working_set_mib",
        "limitation": "Memory thresholds need to be calibrated for local cluster capacity.",
    },
    "pod_kill": {
        "label": "Pod kill",
        "status": "experimental",
        "kind": "PodChaos",
        "resource": "podchaos",
        "suffix": "pod-kill",
        "crd": "podchaos.chaos-mesh.org",
        "decision": "pod_restart_investigation or pod_recovery_observe",
        "basis": "Pod status, restart count, and Kubernetes Events",
        "limitation": "Pod restart signals depend on timing and scrape availability.",
    },
    "network_delay": {
        "label": "Network delay",
        "status": "planned",
        "kind": "NetworkChaos",
        "resource": "networkchaos",
        "suffix": "network-delay",
        "crd": "networkchaos.chaos-mesh.org",
        "decision": "network_latency_manual_review",
        "basis": "Kubernetes Events plus future latency/error-rate metrics",
        "limitation": "Current Prometheus queries do not include application latency/error rate.",
    },
}


def list_supported_faults() -> dict[str, dict[str, str]]:
    """Return metadata for supported fault experiment types."""

    return SUPPORTED_FAULTS.copy()


def _require_fault(fault_type: str) -> dict[str, str]:
    if fault_type not in SUPPORTED_FAULTS:
        supported = ", ".join(sorted(SUPPORTED_FAULTS))
        raise ValueError(f"Unsupported fault_type={fault_type!r}. Supported: {supported}")
    return SUPPORTED_FAULTS[fault_type]


def get_fault_resource_name(fault_type: str, service: str) -> str:
    """Return the stable ChaosMesh resource name for a fault type and service."""

    metadata = _require_fault(fault_type)
    return f"{service}-{metadata['suffix']}"


def _manifest_filename(fault_type: str, service: str) -> str:
    safe_service = service.replace("_", "-")
    return f"{safe_service}_{fault_type}_runtime.yaml"


def build_fault_manifest(
    fault_type: str,
    service: str = "paymentservice",
    namespace: str = "online-boutique",
    chaos_namespace: str = "chaos-testing",
    params: dict[str, Any] | None = None,
) -> str:
    """Build a ChaosMesh manifest as YAML text."""

    metadata = _require_fault(fault_type)
    values = params or {}
    name = get_fault_resource_name(fault_type, service)
    duration = str(values.get("duration", "2m"))
    workers = int(values.get("workers", 1))

    if fault_type == "cpu_stress":
        load = int(values.get("cpu_load", values.get("load", 80)))
        return f"""apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: {name}
  namespace: {chaos_namespace}
spec:
  mode: one
  selector:
    namespaces:
      - {namespace}
    labelSelectors:
      app: {service}
  stressors:
    cpu:
      workers: {workers}
      load: {load}
  duration: "{duration}"
"""

    if fault_type == "memory_stress":
        memory_size = str(values.get("memory_size", "128MB"))
        return f"""apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: {name}
  namespace: {chaos_namespace}
spec:
  mode: one
  selector:
    namespaces:
      - {namespace}
    labelSelectors:
      app: {service}
  stressors:
    memory:
      workers: {workers}
      size: "{memory_size}"
  duration: "{duration}"
"""

    if fault_type == "pod_kill":
        mode = str(values.get("mode", "one"))
        return f"""apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: {name}
  namespace: {chaos_namespace}
spec:
  action: pod-kill
  mode: {mode}
  selector:
    namespaces:
      - {namespace}
    labelSelectors:
      app: {service}
"""

    if fault_type == "network_delay":
        latency = str(values.get("latency", "100ms"))
        jitter = str(values.get("jitter", "10ms"))
        return f"""apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: {name}
  namespace: {chaos_namespace}
spec:
  action: delay
  mode: one
  selector:
    namespaces:
      - {namespace}
    labelSelectors:
      app: {service}
  delay:
    latency: "{latency}"
    correlation: "0"
    jitter: "{jitter}"
  duration: "{duration}"
"""

    raise AssertionError(f"Unhandled fault_type={fault_type!r}; metadata={metadata}")


def write_runtime_manifest(
    project_root: Path,
    fault_type: str,
    service: str = "paymentservice",
    namespace: str = "online-boutique",
    chaos_namespace: str = "chaos-testing",
    params: dict[str, Any] | None = None,
    output_dir: str | Path = "aiops_agent/chaos/generated",
) -> Path:
    """Write a generated runtime manifest under aiops_agent/chaos/generated."""

    output_path = Path(output_dir)
    if not output_path.is_absolute():
        output_path = project_root / output_path
    output_path.mkdir(parents=True, exist_ok=True)
    manifest_path = output_path / _manifest_filename(fault_type, service)
    manifest = build_fault_manifest(fault_type, service, namespace, chaos_namespace, params)
    manifest_path.write_text(manifest, encoding="utf-8")
    return manifest_path


def build_apply_command(manifest_path: str | Path, kubectl: str = "kubectl") -> list[str]:
    return [kubectl, "apply", "-f", str(manifest_path)]


def build_delete_command(
    fault_type: str,
    service: str = "paymentservice",
    chaos_namespace: str = "chaos-testing",
    kubectl: str = "kubectl",
) -> list[str]:
    metadata = _require_fault(fault_type)
    return [
        kubectl,
        "delete",
        metadata["resource"],
        get_fault_resource_name(fault_type, service),
        "-n",
        chaos_namespace,
        "--ignore-not-found",
    ]


def build_status_command(
    fault_type: str,
    service: str | None = None,
    chaos_namespace: str = "chaos-testing",
    kubectl: str = "kubectl",
) -> list[str]:
    metadata = _require_fault(fault_type)
    command = [kubectl, "get", metadata["resource"], "-n", chaos_namespace]
    if service:
        command.insert(3, get_fault_resource_name(fault_type, service))
    return command


def check_required_crd_command(fault_type: str, kubectl: str = "kubectl") -> list[str]:
    metadata = _require_fault(fault_type)
    return [kubectl, "get", "crd", metadata["crd"]]

