"""Streamlit dashboard for the AIOps Agent demo."""

from __future__ import annotations

import csv
import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from tools.kpiroot_tool import analyze_kpiroot
from tools.kubernetes_tool import collect_kubernetes_evidence
from tools.prometheus_tool import collect_prometheus_metrics
from tools.recovery_tool import generate_recovery_plan
from tools.chaos_fault_tool import list_supported_faults
from tools.realtime_dataset_adapter import build_realtime_datasets
from tools.realtime_prometheus_collector import collect_realtime_prometheus_metrics
from tools.usad_tool import analyze_usad


AGENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AGENT_DIR.parent
CONFIG_PATH = PROJECT_ROOT / "aiops_agent" / "config.json"
OUTPUTS_DIR = PROJECT_ROOT / "aiops_agent" / "outputs"
WATCH_HISTORY = OUTPUTS_DIR / "watch_history.csv"
RUNTIME_DATA_DIR = PROJECT_ROOT / "aiops_agent" / "runtime_data"
RUNTIME_OUTPUTS_DIR = PROJECT_ROOT / "aiops_agent" / "runtime_outputs"
ARK_DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_SERVICES = [
    "frontend",
    "checkoutservice",
    "paymentservice",
    "productcatalogservice",
    "cartservice",
    "currencyservice",
    "shippingservice",
    "recommendationservice",
    "emailservice",
    "adservice",
    "redis-cart",
]
FAULT_TYPE_LABELS = {
    "cpu_stress": "CPU 压力故障（已完整验证）",
    "memory_stress": "内存压力故障（实验性）",
    "pod_kill": "Pod Kill 故障（实验性）",
    "network_delay": "网络延迟故障（待扩展）",
}
FAULT_SCENARIO_SUFFIX = {
    "cpu_stress": "cpu",
    "memory_stress": "memory",
    "pod_kill": "podkill",
    "network_delay": "network-delay",
}


def apply_dashboard_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2.5rem;
            max-width: 1500px;
        }
        h1 {
            font-size: 2.25rem !important;
            line-height: 1.2 !important;
            margin-bottom: 1rem !important;
        }
        h2, h3 {
            letter-spacing: 0 !important;
        }
        .aiops-card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 0.85rem;
            margin: 0.75rem 0 1rem 0;
        }
        .aiops-card {
            border: 1px solid #d9e2ec;
            border-radius: 8px;
            padding: 0.85rem 1rem;
            background: #ffffff;
            min-height: 86px;
            overflow-wrap: anywhere;
            word-break: break-word;
            white-space: normal;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        .aiops-card-label {
            color: #52606d;
            font-size: 0.82rem;
            margin-bottom: 0.42rem;
        }
        .aiops-card-value {
            color: #102a43;
            font-size: 1.08rem;
            font-weight: 650;
            line-height: 1.35;
            white-space: normal;
        }
        .aiops-card.good .aiops-card-value {
            color: #0f766e;
        }
        .aiops-card.warn .aiops-card-value {
            color: #b45309;
        }
        .aiops-card.bad .aiops-card-value {
            color: #b91c1c;
        }
        .aiops-note {
            border: 1px solid #fde68a;
            border-radius: 8px;
            background: #fffbeb;
            color: #78350f;
            padding: 0.8rem 1rem;
            margin: 0.75rem 0;
            line-height: 1.5;
        }
        .aiops-danger {
            border: 1px solid #fecaca;
            border-radius: 8px;
            background: #fef2f2;
            color: #7f1d1d;
            padding: 0.8rem 1rem;
            margin: 0.75rem 0;
            line-height: 1.5;
        }
        div[data-testid="stCodeBlock"] pre {
            max-height: 500px;
            overflow: auto;
            white-space: pre-wrap;
            word-break: break-word;
        }
        div[data-testid="stDataFrame"] {
            overflow-x: auto;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def build_llm_env() -> dict[str, str]:
    env = os.environ.copy()
    api_key = st.session_state.get("ark_api_key")
    base_url = st.session_state.get("ark_base_url")
    model = st.session_state.get("ark_model")
    if api_key:
        env["ARK_API_KEY"] = api_key
    if base_url:
        env["ARK_BASE_URL"] = base_url
    if model:
        env["ARK_MODEL"] = model
    return env


def llm_config_status() -> dict[str, Any]:
    api_key = st.session_state.get("ark_api_key") or os.environ.get("ARK_API_KEY")
    base_url = st.session_state.get("ark_base_url") or os.environ.get("ARK_BASE_URL") or ARK_DEFAULT_BASE_URL
    model = st.session_state.get("ark_model") or os.environ.get("ARK_MODEL")
    return {
        "api_key_detected": bool(api_key),
        "base_url": base_url,
        "model": model or "",
        "ready": bool(api_key and model),
    }


def run_command(
    command: list[str],
    timeout: int = 240,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=env,
    )


def command_output(result: subprocess.CompletedProcess[str]) -> str:
    output = result.stdout or ""
    if result.stderr:
        output += "\n" + result.stderr
    return output.strip()


def parse_agent_output(output: str) -> dict[str, str]:
    patterns = {
        "recovery_decision": r"Recovery decision:\s*(.+)",
        "risk_level": r"Recovery risk_level:\s*(.+)",
        "report_path": r"Report generated:\s*(.+)",
        "auto_report_path": r"Archived diagnosis report:\s*(.+)",
        "llm_output_path": r"Saved LLM diagnosis summary:\s*(.+)",
    }
    parsed: dict[str, str] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        parsed[key] = match.group(1).strip() if match else ""
    return parsed


def render_cards(items: list[tuple[str, Any, str]]) -> None:
    html_cards = ['<div class="aiops-card-grid">']
    for label, value, status_class in items:
        label_text = html.escape(str(label))
        value_text = html.escape("" if value is None else str(value))
        html_cards.append(
            f'<div class="aiops-card {status_class}">'
            f'<div class="aiops-card-label">{label_text}</div>'
            f'<div class="aiops-card-value">{value_text}</div>'
            "</div>"
        )
    html_cards.append("</div>")
    st.markdown("".join(html_cards), unsafe_allow_html=True)


def render_output_box(label: str, output: str, height: int = 460) -> None:
    st.text_area(label, value=output or "(无输出)", height=height)


def render_summary_cards(parsed: dict[str, str]) -> None:
    items = [
        ("recovery decision", parsed.get("recovery_decision") or "(未解析)", "warn"),
        ("risk level", parsed.get("risk_level") or "(未解析)", "warn"),
        ("diagnosis_report.md 路径", parsed.get("report_path") or str(OUTPUTS_DIR / "diagnosis_report.md"), ""),
        ("auto_diagnosis 报告路径", parsed.get("auto_report_path") or "(未生成)", ""),
        ("LLM 输出路径", parsed.get("llm_output_path") or "(未生成)", ""),
    ]
    render_cards(items)


def format_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def current_status(config: dict[str, Any]) -> dict[str, Any]:
    usad_result = analyze_usad(config, PROJECT_ROOT)
    kpiroot_result = analyze_kpiroot(config, PROJECT_ROOT)
    service_name = kpiroot_result.get("top_service") or "paymentservice"
    kubernetes_evidence = collect_kubernetes_evidence(config, service_name)
    prometheus_metrics = collect_prometheus_metrics(config, service_name)
    recovery_plan = generate_recovery_plan(
        config,
        usad_result,
        kpiroot_result,
        kubernetes_evidence,
        prometheus_metrics,
    )
    summary = prometheus_metrics.get("summary", {})
    return {
        "service_name": service_name,
        "kubernetes_health_status": kubernetes_evidence.get("health_status"),
        "prometheus_available": prometheus_metrics.get("prometheus_available"),
        "service_cpu_rate": summary.get("service_cpu_rate"),
        "service_memory_working_set_mib": summary.get("service_memory_working_set_mib"),
        "recovery_decision": recovery_plan.get("decision"),
        "risk_level": recovery_plan.get("risk_level"),
    }


def discover_services(namespace: str) -> list[str]:
    try:
        result = run_command(["kubectl", "get", "deploy", "-n", namespace, "--no-headers"], timeout=12)
    except Exception:
        return DEFAULT_SERVICES
    if result.returncode != 0:
        return DEFAULT_SERVICES
    services = []
    for line in (result.stdout or "").splitlines():
        parts = line.split()
        if parts:
            services.append(parts[0])
    return sorted(set(services)) or DEFAULT_SERVICES


def fault_type_from_label(label: str) -> str:
    for fault_type, display in FAULT_TYPE_LABELS.items():
        if display == label:
            return fault_type
    return "cpu_stress"


def fault_resource(fault_type: str) -> str:
    if fault_type in {"cpu_stress", "memory_stress"}:
        return "stresschaos"
    if fault_type == "pod_kill":
        return "podchaos"
    return "networkchaos"


def fault_resource_name(fault_type: str, service: str) -> str:
    suffix = {
        "cpu_stress": "cpu-stress",
        "memory_stress": "memory-stress",
        "pod_kill": "pod-kill",
        "network_delay": "network-delay",
    }.get(fault_type, "cpu-stress")
    return f"{service}-{suffix}"


def default_scenario_for_fault(fault_type: str, service: str) -> str:
    suffix = FAULT_SCENARIO_SUFFIX.get(fault_type, "cpu")
    return f"realtime-{service}-{suffix}"


def fault_explanation(fault_type: str) -> str:
    explanations = {
        "cpu_stress": "CPU 压力故障是当前已完整验证场景，主要依赖 Prometheus service_cpu_rate。",
        "memory_stress": "内存压力故障主要依赖 memory working set、Pod Event 和容器限制，当前为实验性扩展。",
        "pod_kill": "Pod Kill 主要依赖 Pod 状态、restart count、Deployment available 和 Kubernetes Event。",
        "network_delay": "网络延迟故障当前缺少应用层 latency/error rate 指标，解释能力有限，适合作为扩展演示。",
    }
    return explanations.get(fault_type, explanations["cpu_stress"])


def report_files() -> list[Path]:
    files = sorted(OUTPUTS_DIR.glob("diagnosis_report*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    files.extend(sorted(OUTPUTS_DIR.glob("auto_diagnosis_*.md"), key=lambda item: item.stat().st_mtime, reverse=True))
    seen: set[Path] = set()
    unique_files: list[Path] = []
    for path in files:
        if path not in seen:
            unique_files.append(path)
            seen.add(path)
    return unique_files


def pipeline_report_files() -> list[Path]:
    if not RUNTIME_OUTPUTS_DIR.exists():
        return []
    return sorted(
        RUNTIME_OUTPUTS_DIR.glob("realtime_pipeline_report_*.md"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeError:
        return path.read_text(encoding="utf-8")


def show_report(path: Path) -> None:
    try:
        st.markdown(read_text(path))
    except Exception as exc:
        st.error(f"Failed to read report: {exc}")


def read_watch_history() -> list[dict[str, str]]:
    if not WATCH_HISTORY.exists():
        return []
    with WATCH_HISTORY.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def archive_watch_history(clear_after_archive: bool = False) -> Path | None:
    if not WATCH_HISTORY.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = OUTPUTS_DIR / f"watch_history_archive_{timestamp}.csv"
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(WATCH_HISTORY, archive_path)
    if clear_after_archive:
        WATCH_HISTORY.unlink()
        st.session_state["watch_history_rows"] = []
    return archive_path


def clear_watch_history() -> bool:
    if not WATCH_HISTORY.exists():
        return False
    WATCH_HISTORY.unlink()
    st.session_state["watch_history_rows"] = []
    return True


def render_sidebar() -> None:
    st.sidebar.title("LLM API 设置")
    provider = st.sidebar.selectbox("Provider", ["火山方舟 Ark", "OpenAI-compatible"], index=0)
    default_base_url = ARK_DEFAULT_BASE_URL if provider == "火山方舟 Ark" else ""
    api_key = st.sidebar.text_input("API Key", type="password", placeholder="仅保存到当前 Streamlit 会话")
    base_url = st.sidebar.text_input("Base URL", value=st.session_state.get("ark_base_url", default_base_url))
    model = st.sidebar.text_input(
        "Model",
        value=st.session_state.get("ark_model", ""),
        placeholder="例如 doubao-seed-2-0-lite-260428",
    )

    if st.sidebar.button("保存 LLM 设置到当前会话"):
        if api_key:
            st.session_state["ark_api_key"] = api_key
        st.session_state["ark_base_url"] = base_url or default_base_url
        st.session_state["ark_model"] = model
        st.sidebar.success("LLM API 设置已保存到当前会话。")

    if st.sidebar.button("清除 LLM API 设置"):
        for key in ["ark_api_key", "ark_base_url", "ark_model"]:
            st.session_state.pop(key, None)
        st.sidebar.success("已清除当前会话中的 LLM API 设置。")

    status = llm_config_status()
    st.sidebar.write(f"ARK_API_KEY detected: {status['api_key_detected']}")
    st.sidebar.write(f"ARK_MODEL: {status['model'] or '(未设置)'}")
    st.sidebar.write(f"ARK_BASE_URL: {status['base_url']}")

    if st.sidebar.button("测试 LLM 配置"):
        if status["ready"] and status["base_url"]:
            st.sidebar.success("配置项完整，可以运行 LLM 检测。")
        else:
            st.sidebar.error("配置不完整，请填写 API Key、Base URL 和 Model。")


def render_overview_tab(config: dict[str, Any]) -> None:
    system = config.get("system", {})
    recovery = config.get("recovery", {})
    st.subheader("系统总览")
    render_cards(
        [
            ("系统名", system.get("name", "Online Boutique"), ""),
            ("namespace", system.get("namespace", "online-boutique"), ""),
            ("当前服务", st.session_state.get("current_status", {}).get("service_name", "paymentservice"), ""),
            ("Agent 模式", config.get("mode", "hybrid"), ""),
            ("dry-run", str(recovery.get("dry_run", True)), "good"),
            ("CPU 阈值", recovery.get("cpu_pressure_threshold", 0.05), ""),
        ]
    )
    st.markdown(
        '<div class="aiops-note">恢复动作保持 dry-run，不会自动执行真实恢复命令。</div>',
        unsafe_allow_html=True,
    )

    if st.button("刷新当前状态"):
        with st.spinner("正在采集 Kubernetes / Prometheus / Recovery 摘要..."):
            try:
                st.session_state["current_status"] = current_status(config)
            except Exception as exc:
                st.error(f"状态刷新失败：{exc}")

    status = st.session_state.get("current_status")
    if status:
        health_class = "good" if status.get("kubernetes_health_status") == "healthy" else "warn"
        decision_class = "good" if status.get("recovery_decision") == "observe" else "warn"
        render_cards(
            [
                ("当前服务", status.get("service_name"), ""),
                ("Kubernetes health_status", status.get("kubernetes_health_status"), health_class),
                ("Prometheus available", status.get("prometheus_available"), "good" if status.get("prometheus_available") else "warn"),
                ("service_cpu_rate", status.get("service_cpu_rate"), ""),
                ("memory MiB", status.get("service_memory_working_set_mib"), ""),
                ("recovery decision", status.get("recovery_decision"), decision_class),
                ("risk level", status.get("risk_level"), decision_class),
            ]
        )

    st.subheader("项目能力摘要")
    render_cards(
        [
            ("ChaosMesh 故障注入", "已接入", "good"),
            ("Prometheus 实时采集", "已接入", "good"),
            ("USAD 实时异常检测", "已接入并可真实执行", "good"),
            ("KPIRoot 实时根因定位", "已接入并可真实执行", "good"),
            ("Agent 综合诊断", "已接入", "good"),
            ("LLM 智能体总结", "可选", "warn"),
            ("恢复动作", "dry-run 保护", "good"),
        ]
    )
    st.markdown(
        """
        <div class="aiops-note">
        当前推荐主流程为“端到端实时 AIOps”：每次故障实验后，使用 Prometheus 当前实时数据重新生成 runtime 输入，
        并真实执行 USAD 与 KPIRoot，再由 Agent 生成诊断和 dry-run 恢复建议。旧的 run_agent.py / 离线结果读取能力仅作为兼容和高级调试保留。
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chaos_tab() -> None:
    st.subheader("故障注入")
    st.markdown(
        '<div class="aiops-danger">该操作会创建或删除 ChaosMesh StressChaos 对象，会影响目标服务；恢复动作仍为 dry-run，不会执行服务重启。</div>',
        unsafe_allow_html=True,
    )
    service = st.text_input("Service", value="paymentservice", help="目标服务名，对应 Pod label app=<Service>。")
    duration = st.selectbox("Duration", ["30s", "1m", "2m", "3m", "5m"], index=2, help="CPU 压力持续时间。")
    load = st.slider("CPU Load", min_value=10, max_value=100, value=80, step=5, help="CPU 压力负载百分比。")
    workers = st.slider("Workers", min_value=1, max_value=4, value=1, step=1, help="StressChaos CPU worker 数量。")

    col1, col2, col3 = st.columns(3)
    if col1.button("注入 CPU 压力"):
        with st.spinner("正在创建 StressChaos，请等待..."):
            result = run_command(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "aiops_agent\\scripts\\apply_paymentservice_cpu_stress.ps1",
                    "-Service",
                    service,
                    "-Duration",
                    duration,
                    "-Load",
                    str(load),
                    "-Workers",
                    str(workers),
                ],
                timeout=120,
            )
        render_output_box("故障注入输出", command_output(result), height=360)

    if col2.button("删除 CPU 压力"):
        with st.spinner("正在删除 StressChaos，请等待..."):
            result = run_command(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "aiops_agent\\scripts\\delete_paymentservice_cpu_stress.ps1",
                ],
                timeout=120,
            )
        render_output_box("删除故障输出", command_output(result), height=360)

    if col3.button("查看 StressChaos 状态"):
        with st.spinner("正在查询 StressChaos 状态..."):
            get_result = run_command(["kubectl", "get", "stresschaos", "-n", "chaos-testing"], timeout=30)
            get_output = command_output(get_result)
            if "No resources found" in get_output or not get_output.strip():
                st.info("当前没有残留 StressChaos。")
                render_output_box("StressChaos 状态输出", get_output or "No resources found.", height=260)
            else:
                describe_result = run_command(
                    ["kubectl", "describe", "stresschaos", "paymentservice-cpu-stress", "-n", "chaos-testing"],
                    timeout=30,
                )
                render_output_box("StressChaos 状态输出", get_output + "\n\n" + command_output(describe_result), height=420)


def render_chaos_tab_v2(config: dict[str, Any]) -> None:
    st.subheader("实时故障实验")
    st.markdown(
        '<div class="aiops-danger">故障注入会创建或删除 ChaosMesh 实验对象，可能影响目标服务；恢复动作保持 dry-run，不会自动执行真实恢复命令，也不会执行服务重启或 rollout restart。</div>',
        unsafe_allow_html=True,
    )
    namespace = config.get("system", {}).get("namespace", "online-boutique")
    chaos_namespace = "chaos-testing"
    discovered_services = discover_services(namespace)
    default_service = config.get("faults", {}).get("default_service", "paymentservice")
    service_index = discovered_services.index(default_service) if default_service in discovered_services else 0
    service = st.selectbox("目标服务", discovered_services, index=service_index, help="优先从 Kubernetes Deployment 动态读取，失败时使用默认 Online Boutique 服务列表。")
    st.info("推荐演示目标：paymentservice。若列表中出现 loadgenerator，请注意它是流量发生组件，推荐演示目标仍为 paymentservice。")

    fault_label = st.selectbox("故障类型", list(FAULT_TYPE_LABELS.values()), index=0)
    fault_type = fault_type_from_label(fault_label)
    metadata = list_supported_faults().get(fault_type, {})
    st.info(f"{fault_explanation(fault_type)} 当前状态：{metadata.get('status', 'unknown')}。")
    if fault_type != "cpu_stress":
        st.warning("当前故障类型已接入故障实验框架，但端到端算法解释仍需进一步校准；当前完整验证场景仍为 paymentservice CPU 压力故障。")
    show_next_step = st.checkbox("注入故障后显示端到端诊断建议", value=True)

    duration = "2m"
    cpu_load = 80
    workers = 1
    memory_size = "128MB"
    latency = "100ms"
    jitter = "10ms"

    if fault_type == "cpu_stress":
        duration = st.selectbox("Duration（压力持续时间）", ["30s", "1m", "2m", "3m", "5m"], index=2)
        cpu_load = st.slider("CPU Load（目标 CPU 负载百分比）", min_value=10, max_value=100, value=80, step=5)
        workers = st.slider("Workers（CPU stress worker 数量）", min_value=1, max_value=4, value=1, step=1)
    elif fault_type == "memory_stress":
        duration = st.selectbox("Duration（内存压力持续时间）", ["30s", "1m", "2m", "3m", "5m"], index=2)
        memory_size = st.selectbox("Memory Size（单 worker 内存压力大小）", ["64MB", "128MB", "256MB", "512MB"], index=1)
        workers = st.slider("Workers（Memory stress worker 数量）", min_value=1, max_value=4, value=1, step=1)
        st.caption("默认 128MB，避免在本地集群中过高内存压力导致整体不稳定。")
    elif fault_type == "pod_kill":
        st.selectbox("Mode", ["one"], index=0, help="只杀一个匹配 app=<service> 的 Pod，不修改 Deployment 副本数。")
        st.caption("Pod Kill 通常是一次性动作；实验窗口由报告和事件时间线记录。")
    elif fault_type == "network_delay":
        duration = st.selectbox("Duration（网络延迟持续时间）", ["30s", "1m", "2m", "3m", "5m"], index=2)
        latency = st.selectbox("Latency（注入延迟）", ["100ms", "200ms", "500ms"], index=0)
        jitter = st.selectbox("Jitter（延迟抖动）", ["0ms", "10ms", "30ms", "50ms"], index=1)
        st.caption("当前版本没有完整接入应用层 latency/error rate 指标，网络延迟实验主要用于扩展展示。")

    render_cards(
        [
            ("fault_type", fault_type, "good" if fault_type == "cpu_stress" else "warn"),
            ("ChaosMesh kind", metadata.get("kind", "N/A"), ""),
            ("检测依据", metadata.get("basis", "N/A"), ""),
            ("Agent 决策", metadata.get("decision", "N/A"), ""),
        ]
    )

    col1, col2, col3 = st.columns(3)
    if col1.button("注入故障"):
        with st.spinner("正在创建 ChaosMesh 故障实验对象，请等待..."):
            command = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "aiops_agent\\scripts\\apply_fault.ps1",
                "-FaultType",
                fault_type,
                "-Service",
                service,
                "-Namespace",
                namespace,
                "-ChaosNamespace",
                chaos_namespace,
                "-Duration",
                duration,
                "-CpuLoad",
                str(cpu_load),
                "-Workers",
                str(workers),
                "-MemorySize",
                memory_size,
                "-Latency",
                latency,
                "-Jitter",
                jitter,
            ]
            result = run_command(command, timeout=120)
        render_output_box("故障注入输出", command_output(result), height=420)
        if result.returncode == 0 and show_next_step:
            st.success("故障注入命令已完成。下一步请进入“端到端 AIOps 诊断”，运行 execute USAD + KPIRoot 模式，以使用当前故障产生的实时数据完成异常检测、根因定位和 Agent 诊断。")

    if col2.button("清理故障"):
        with st.spinner("正在删除 ChaosMesh 故障实验对象，请等待..."):
            result = run_command(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "aiops_agent\\scripts\\delete_fault.ps1",
                    "-FaultType",
                    fault_type,
                    "-Service",
                    service,
                    "-ChaosNamespace",
                    chaos_namespace,
                ],
                timeout=120,
            )
        status_result = run_command(["kubectl", "get", "stresschaos,podchaos,networkchaos", "-n", chaos_namespace], timeout=30)
        status_output = command_output(status_result)
        if "No resources found" in status_output or not status_output.strip():
            status_output = "当前没有残留 stresschaos/podchaos/networkchaos。"
        render_output_box("清理故障输出与当前 Chaos 状态", command_output(result) + "\n\n" + status_output, height=420)

    if col3.button("查看 Chaos 状态"):
        resource = fault_resource(fault_type)
        name = fault_resource_name(fault_type, service)
        with st.spinner("正在查询 ChaosMesh 实验对象状态..."):
            get_result = run_command(["kubectl", "get", "stresschaos,podchaos,networkchaos", "-n", chaos_namespace], timeout=30)
            get_output = command_output(get_result)
            describe_result = run_command(["kubectl", "describe", resource, name, "-n", chaos_namespace], timeout=30)
            describe_output = command_output(describe_result)
        if "No resources found" in get_output or not get_output.strip():
            st.info("当前没有残留故障实验对象。")
            render_output_box("Chaos 状态输出", get_output or "No resources found.", height=260)
        else:
            render_output_box("Chaos 状态输出", get_output + "\n\n" + describe_output, height=500)


def ensure_llm_ready() -> bool:
    status = llm_config_status()
    if status["ready"]:
        st.info(f"ARK_API_KEY detected: True\n\nARK_MODEL: {status['model']}")
        return True
    st.error("请先在左侧 LLM API 设置中填写 API Key 和 Model，或在本机环境变量中设置 ARK_API_KEY 和 ARK_MODEL。")
    return False


def render_detection_tab() -> None:
    st.subheader("检测中心")
    detection_type = st.radio("检测方式", ["一次检测", "自动巡检"], horizontal=True)
    execution_mode = st.radio("执行模式", ["本地规则模式", "LLM 智能体模式"], horizontal=True)

    alert_text = st.text_input("告警文本", value="Online Boutique paymentservice CPU anomaly")

    if detection_type == "一次检测" and execution_mode == "本地规则模式":
        if st.button("运行一次本地诊断"):
            with st.spinner("正在运行 run_agent.py，请等待..."):
                result = run_command([sys.executable, "aiops_agent\\run_agent.py", "--config", "aiops_agent\\config.json"])
                output = command_output(result)
            parsed = parse_agent_output(output)
            render_output_box("run_agent.py 输出", output, height=460)
            render_summary_cards(parsed)

    elif detection_type == "一次检测" and execution_mode == "LLM 智能体模式":
        if st.button("运行一次 LLM 智能体诊断"):
            if ensure_llm_ready():
                with st.spinner("正在运行 LLM 智能体诊断，请等待..."):
                    result = run_command(
                        [
                            sys.executable,
                            "aiops_agent\\veadk_agent.py",
                            "--config",
                            "aiops_agent\\config.json",
                            "--alert",
                            alert_text,
                            "--llm",
                        ],
                        timeout=360,
                        env=build_llm_env(),
                    )
                    output = command_output(result)
                render_output_box("veadk_agent.py --llm 输出", output, height=500)
                parsed = parse_agent_output(output)
                parsed["report_path"] = parsed.get("report_path") or str(OUTPUTS_DIR / "diagnosis_report.md")
                render_summary_cards(parsed)

    elif detection_type == "自动巡检":
        interval = st.number_input("interval 秒数", min_value=1, max_value=3600, value=5, step=1)
        max_rounds = st.number_input("max_rounds", min_value=1, max_value=1000, value=3, step=1)
        cooldown = st.number_input("cooldown 秒数", min_value=0, max_value=3600, value=60, step=5)
        trigger_once = st.checkbox("trigger_once", value=True)
        st.markdown(
            """
            <div class="aiops-note">
            自动巡检会按照 interval 和 max_rounds 运行；页面会在子进程结束后一次性展示输出。
            如果当前没有故障，输出中会显示 No realtime CPU anomaly detected。
            如果检测到异常，会自动生成 auto_diagnosis_*.md 报告。
            右上角 Stop 是 Streamlit 的运行状态按钮，不代表程序错误。
            </div>
            """,
            unsafe_allow_html=True,
        )
        llm_mode = execution_mode == "LLM 智能体模式"
        button_label = "启动 LLM 自动巡检" if llm_mode else "启动本地自动巡检"

        if st.button(button_label):
            if llm_mode and not ensure_llm_ready():
                return
            st.info("自动巡检正在运行中，请等待。本页面会在 watch_agent.py 执行完成后显示结果。右上角出现 Stop 是 Streamlit 正在执行任务的正常提示。")
            command = [
                sys.executable,
                "aiops_agent\\watch_agent.py",
                "--config",
                "aiops_agent\\config.json",
                "--interval",
                str(interval),
                "--max-rounds",
                str(max_rounds),
                "--cooldown",
                str(cooldown),
            ]
            if trigger_once:
                command.append("--trigger-once")
            if llm_mode:
                command.extend(["--llm", "--alert", alert_text])
            with st.spinner("自动巡检正在运行，请等待..."):
                result = run_command(command, timeout=max(120, int(interval) * int(max_rounds) + 240), env=build_llm_env())
                output = command_output(result)
            render_output_box("watch_agent.py 输出", output, height=500)
            render_summary_cards(parse_agent_output(output))
            st.info("自动巡检结束后可在“自动巡检日志”Tab 查看 watch_history.csv 新增记录。")


def render_watch_history_tab() -> None:
    st.subheader("自动巡检日志")
    st.markdown(
        """
        <div class="aiops-note">
        watch_history.csv 是持久化历史记录文件，刷新页面或重启 Streamlit 后不会自动清空。
        如需进行干净演示，可以先点击“归档当前日志”保存历史记录，再点击“清空当前日志”。
        清空日志只会删除 watch_history.csv，不会删除 diagnosis_report*.md、auto_diagnosis_*.md 或 llm_diagnosis_*.txt。
        </div>
        """,
        unsafe_allow_html=True,
    )

    archive_and_clear = st.checkbox("归档后清空当前日志", value=False)
    refresh_col, archive_col, clear_col = st.columns(3)

    if refresh_col.button("刷新自动巡检日志"):
        st.session_state["watch_history_rows"] = read_watch_history()

    if archive_col.button("归档当前日志"):
        archive_path = archive_watch_history(clear_after_archive=archive_and_clear)
        if archive_path is None:
            st.warning("当前没有 watch_history.csv，无法归档。")
        elif archive_and_clear:
            st.success(f"已归档并清空当前日志：{archive_path}")
        else:
            st.success(f"已归档当前日志：{archive_path}")
        st.session_state["watch_history_rows"] = read_watch_history()

    if clear_col.button("清空当前日志"):
        if clear_watch_history():
            st.success("已清空 watch_history.csv，后续自动巡检会重新生成新的日志文件。")
        else:
            st.info("当前没有 watch_history.csv，无需清空。")

    rows = st.session_state.get("watch_history_rows")
    if rows is None:
        rows = read_watch_history()
    if not rows:
        st.info("暂无自动巡检记录。")
        return

    key_columns = [
        "timestamp",
        "service",
        "service_cpu_rate",
        "threshold",
        "triggered",
        "recovery_decision",
        "risk_level",
        "mode",
        "report_path",
        "llm_executed",
        "llm_output_path",
    ]
    display_rows = [{column: row.get(column, "") for column in key_columns} for row in rows]
    st.dataframe(display_rows, use_container_width=True, hide_index=True)
    triggered_rows = [row for row in rows if str(row.get("triggered", "")).lower() == "true"]
    if triggered_rows:
        latest = triggered_rows[-1]
        st.warning("最近一次异常触发：")
        render_cards(
            [
                ("时间", latest.get("timestamp"), "warn"),
                ("CPU rate", latest.get("service_cpu_rate"), "warn"),
                ("recovery decision", latest.get("recovery_decision"), "warn"),
                ("risk level", latest.get("risk_level"), "warn"),
                ("报告路径", latest.get("report_path") or "(无)", ""),
                ("LLM 输出路径", latest.get("llm_output_path") or "(无)", ""),
                ("llm_enabled", latest.get("llm_enabled"), ""),
                ("llm_executed", latest.get("llm_executed"), ""),
            ]
        )
        st.warning("triggered=true 的自动巡检记录：")
        triggered_display = [{column: row.get(column, "") for column in key_columns} for row in triggered_rows]
        st.dataframe(triggered_display, use_container_width=True, hide_index=True)


def render_report_tab() -> None:
    st.subheader("报告中心")
    files = report_files()
    if not files:
        st.info("暂无可展示的诊断报告。")
        return
    selected = st.selectbox("选择报告", files, format_func=lambda path: f"{path.name} | {format_mtime(path)}")
    stat = selected.stat()
    st.write("当前展示的是 Agent 自动生成的诊断报告。")
    st.write(f"文件修改时间：{format_mtime(selected)}")
    st.write(f"文件大小：{stat.st_size} bytes")
    show_report(selected)


def render_realtime_pipeline_tab(config: dict[str, Any]) -> None:
    st.subheader("端到端实时流水线")
    st.markdown(
        """
        <div class="aiops-note">
        该功能用于将 Prometheus 当前实时指标采集、USAD/KPIRoot 算法复现项目和 aiops_agent 诊断串联起来。
        默认 dry-run，不会真正运行 external_projects 中的算法脚本；只有勾选 execute_external 并完成确认后才会尝试执行。
        </div>
        """,
        unsafe_allow_html=True,
    )

    pipeline_config = config.get("realtime_pipeline", {})
    namespace = config.get("system", {}).get("namespace", "online-boutique")
    pipeline_services = discover_services(namespace)
    default_service = config.get("faults", {}).get("default_service", "paymentservice")
    pipeline_service_index = pipeline_services.index(default_service) if default_service in pipeline_services else 0
    pipeline_service = st.selectbox("当前目标服务", pipeline_services, index=pipeline_service_index, key="pipeline_target_service")
    pipeline_fault_label = st.selectbox("实验场景类型", list(FAULT_TYPE_LABELS.values()), index=0, key="pipeline_fault_type")
    pipeline_fault_type = fault_type_from_label(pipeline_fault_label)
    st.caption("该选项用于场景归档和 KPIRoot scenario 生成，不作为诊断结论。")
    st.info(fault_explanation(pipeline_fault_type))
    duration_minutes = st.number_input(
        "duration_minutes",
        min_value=1,
        max_value=120,
        value=int(pipeline_config.get("default_duration_minutes", 5)),
        step=1,
    )
    step_seconds = st.number_input(
        "step_seconds",
        min_value=5,
        max_value=300,
        value=int(pipeline_config.get("default_step_seconds", 15)),
        step=5,
    )
    execution_mode = st.selectbox(
        "执行模式",
        ["dry-run，只采集实时数据并规划命令", "execute USAD only，真实运行 USAD", "execute KPIRoot only，真实运行 KPIRoot", "execute USAD + KPIRoot，真实运行两者"],
        index=0,
    )
    dry_run = execution_mode.startswith("dry-run")
    execute_usad_only = execution_mode.startswith("execute USAD only")
    execute_kpiroot_only = execution_mode.startswith("execute KPIRoot only")
    execute_external = execution_mode.startswith("execute USAD + KPIRoot")
    usad_epochs = st.number_input("USAD epochs", min_value=1, max_value=200, value=1, step=1)
    usad_window = st.number_input("USAD window", min_value=2, max_value=60, value=5, step=1)
    usad_train_ratio = st.number_input("USAD train ratio", min_value=0.1, max_value=0.95, value=0.7, step=0.05)
    kpiroot_scenario = st.text_input("KPIRoot scenario", value=default_scenario_for_fault(pipeline_fault_type, pipeline_service))
    kpiroot_alarm = st.text_input("KPIRoot alarm", value=pipeline_service)
    enable_llm = st.checkbox("启用 LLM 总结", value=False)
    confirm_external = False
    if not dry_run:
        st.markdown(
            '<div class="aiops-danger">该操作会运行 external_projects 中的算法代码，可能耗时较长；输出将写入 aiops_agent/runtime_outputs，不会覆盖 external_projects 原始结果。</div>',
            unsafe_allow_html=True,
        )
        confirm_external = st.checkbox("我确认需要尝试运行 external_projects，并理解不会执行真实恢复命令。", value=False)
    if dry_run:
        st.info("dry_run=True：不会真正运行 external_projects，只会生成实时数据、适配输入和模拟命令。")

    col1, col2, col3, col4 = st.columns(4)

    if col1.button("仅采集实时 Prometheus 数据"):
        with st.spinner("正在采集 Prometheus query_range 数据，请等待..."):
            result = collect_realtime_prometheus_metrics(
                config,
                namespace=config.get("system", {}).get("namespace", "online-boutique"),
                duration_minutes=int(duration_minutes),
                step_seconds=int(step_seconds),
                output_dir=pipeline_config.get("runtime_data_dir", "aiops_agent/runtime_data"),
            )
        render_cards(
            [
                ("Prometheus CSV 路径", result.get("csv_path"), ""),
                ("Metadata JSON 路径", result.get("meta_path"), ""),
                ("warnings", len(result.get("warnings", [])), "warn" if result.get("warnings") else "good"),
            ]
        )
        if result.get("warnings"):
            render_output_box("采集 warnings", "\n".join(result.get("warnings", [])), height=240)

    latest_csvs = sorted(RUNTIME_DATA_DIR.glob("prometheus_realtime_*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
    selected_csv = None
    if latest_csvs:
        selected_csv = st.selectbox("用于构建输入的 Prometheus CSV", latest_csvs, format_func=lambda path: f"{path.name} | {format_mtime(path)}")
    else:
        st.info("尚未发现 prometheus_realtime_*.csv。可以先点击“仅采集实时 Prometheus 数据”。")

    if col2.button("构建 USAD/KPIRoot 输入"):
        if selected_csv is None:
            st.error("没有可用的 Prometheus CSV。")
        else:
            with st.spinner("正在构建 USAD / KPIRoot runtime 输入..."):
                result = build_realtime_datasets(
                    config,
                    selected_csv,
                    output_dir=pipeline_config.get("runtime_data_dir", "aiops_agent/runtime_data"),
                )
            render_cards(
                [
                    ("USAD input 路径", result.get("usad_input_csv"), ""),
                    ("KPIRoot input 路径", result.get("kpiroot_input_csv"), ""),
                    ("KPIRoot phase2 dir", result.get("kpiroot_phase2_dir"), ""),
                ]
            )
            if result.get("warnings"):
                render_output_box("适配 warnings", "\n".join(result.get("warnings", [])), height=260)

    if col3.button("运行实时 AIOps 流水线"):
        if not dry_run and not confirm_external:
            st.error("请先勾选二次确认。")
        elif enable_llm and not ensure_llm_ready():
            return
        else:
            command = [
                sys.executable,
                "aiops_agent\\realtime_pipeline_agent.py",
                "--config",
                "aiops_agent\\config.json",
                "--duration-minutes",
                str(int(duration_minutes)),
                "--step-seconds",
                str(int(step_seconds)),
                "--usad-epochs",
                str(int(usad_epochs)),
                "--usad-window",
                str(int(usad_window)),
                "--usad-train-ratio",
                str(float(usad_train_ratio)),
                "--kpiroot-scenario",
                kpiroot_scenario,
                "--kpiroot-alarm",
                kpiroot_alarm,
            ]
            if dry_run:
                command.append("--dry-run")
            if execute_usad_only and confirm_external:
                command.append("--execute-usad-only")
            if execute_kpiroot_only and confirm_external:
                command.append("--execute-kpiroot-only")
            if execute_external and confirm_external:
                command.append("--execute-external")
            if enable_llm:
                command.append("--llm")
            with st.spinner("实时 AIOps 流水线正在运行，请等待..."):
                result = run_command(command, timeout=900, env=build_llm_env())
            output = command_output(result)
            render_output_box("realtime_pipeline_agent.py 输出", output, height=520)
            parsed = parse_agent_output(output)
            pipeline_match = re.search(r"Pipeline report generated:\s*(.+)", output)
            pipeline_report = pipeline_match.group(1).strip() if pipeline_match else ""
            render_cards(
                [
                    ("USAD 是否运行", str(("--execute-usad-only" in command or "--execute-external" in command) and not dry_run), ""),
                    ("KPIRoot 是否运行", str(("--execute-kpiroot-only" in command or "--execute-external" in command) and not dry_run), ""),
                    ("pipeline report 路径", pipeline_report or "(未解析)", ""),
                    ("diagnosis_report.md 路径", parsed.get("report_path") or "(未解析)", ""),
                    ("recovery decision", parsed.get("recovery_decision") or "(未解析)", "warn"),
                    ("risk level", parsed.get("risk_level") or "(未解析)", "warn"),
                ]
            )

    if col4.button("查看最新 pipeline report"):
        reports = pipeline_report_files()
        if not reports:
            st.info("暂无 realtime_pipeline_report_*.md。")
        else:
            st.write(f"最新 pipeline report：{reports[0]}")
            show_report(reports[0])


def _glob_many(patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        files.extend(PROJECT_ROOT.glob(pattern))
    return sorted([path for path in files if path.is_file()], key=lambda item: item.stat().st_mtime, reverse=True)


def _display_artifact(path: Path) -> None:
    st.write(f"完整路径：`{path}`")
    st.write(f"修改时间：{format_mtime(path)}")
    st.write(f"文件大小：{path.stat().st_size} bytes")
    suffix = path.suffix.lower()
    if suffix == ".md":
        st.markdown(read_text(path))
    elif suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            st.dataframe(list(csv.DictReader(file)), use_container_width=True, hide_index=True)
    elif suffix == ".png":
        st.image(str(path))
    elif suffix == ".json":
        st.code(read_text(path), language="json")
    else:
        st.code(read_text(path), language="text")


def _parse_pipeline_output(output: str) -> dict[str, str]:
    patterns = {
        "prometheus_csv": r"Prometheus CSV:\s*(.+)",
        "usad_input_csv": r"USAD input:\s*(.+)",
        "kpiroot_input_csv": r"KPIRoot input:\s*(.+)",
        "pipeline_report": r"Pipeline report generated:\s*(.+)",
        "data_source_mode": r"Data source mode:\s*(.+)",
        "llm_output_path": r"LLM output path:\s*(.+)",
        "llm_mode": r"LLM mode:\s*(.+)",
        "service_cpu_rate": r"Prometheus service_cpu_rate:\s*(.+)",
        "recovery_decision": r"Recovery decision:\s*(.+)",
        "risk_level": r"Recovery risk_level:\s*(.+)",
        "diagnosis_report": r"Report generated:\s*(.+)",
    }
    parsed: dict[str, str] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        parsed[key] = match.group(1).strip() if match else ""
    return parsed


def render_realtime_aiops_tab(config: dict[str, Any]) -> None:
    st.subheader("端到端 AIOps 诊断")
    st.markdown(
        """
        <div class="aiops-note">
        本页面会从 Prometheus 采集当前 Online Boutique 实时指标，生成 USAD/KPIRoot runtime 输入，并根据执行模式真实运行 USAD/KPIRoot，
        再由 Agent 综合生成诊断报告。推荐正式演示选择：execute USAD + KPIRoot。
        </div>
        """,
        unsafe_allow_html=True,
    )
    pipeline_config = config.get("realtime_pipeline", {})
    namespace = config.get("system", {}).get("namespace", "online-boutique")
    services = discover_services(namespace)
    default_service = config.get("faults", {}).get("default_service", "paymentservice")
    service_index = services.index(default_service) if default_service in services else 0
    service = st.selectbox("当前目标服务", services, index=service_index, key="main_pipeline_service")
    fault_label = st.selectbox("实验场景类型", list(FAULT_TYPE_LABELS.values()), index=0, key="main_pipeline_fault")
    fault_type = fault_type_from_label(fault_label)
    st.caption("该选项用于场景归档和 KPIRoot scenario 生成，不作为诊断结论；最终结论以 USAD/KPIRoot、Kubernetes、Prometheus 和 Agent 综合诊断为准。")
    st.info(fault_explanation(fault_type))

    col_a, col_b = st.columns(2)
    duration_minutes = col_a.number_input("duration_minutes", min_value=1, max_value=120, value=int(pipeline_config.get("default_duration_minutes", 5)), step=1, key="main_duration_minutes")
    step_seconds = col_b.number_input("step_seconds", min_value=5, max_value=300, value=int(pipeline_config.get("default_step_seconds", 15)), step=5, key="main_step_seconds")
    execution_mode = st.selectbox(
        "执行模式",
        ["dry-run，只采集数据并规划命令", "execute USAD only", "execute KPIRoot only", "execute USAD + KPIRoot（推荐演示）"],
        index=0,
    )
    dry_run = execution_mode.startswith("dry-run")
    execute_usad_only = execution_mode.startswith("execute USAD only")
    execute_kpiroot_only = execution_mode.startswith("execute KPIRoot only")
    execute_external = execution_mode.startswith("execute USAD + KPIRoot")
    st.info("为了安全，恢复动作保持 dry-run，不会自动执行真实恢复命令；推荐正式演示选择：execute USAD + KPIRoot。")

    usad_col1, usad_col2, usad_col3 = st.columns(3)
    usad_epochs = usad_col1.number_input("USAD epochs", min_value=1, max_value=200, value=1, step=1)
    usad_window = usad_col2.number_input("USAD window", min_value=2, max_value=60, value=5, step=1)
    usad_train_ratio = usad_col3.number_input("USAD train ratio", min_value=0.1, max_value=0.95, value=0.7, step=0.05)
    kpiroot_scenario = st.text_input("KPIRoot scenario", value=default_scenario_for_fault(fault_type, service))
    kpiroot_alarm = st.text_input("KPIRoot alarm", value=service)
    enable_llm = st.checkbox("启用 LLM 总结", value=False)

    confirm_external = False
    if not dry_run:
        st.markdown(
            '<div class="aiops-danger">该操作会真实运行 external_projects 中的 USAD/KPIRoot 代码，可能耗时较长；所有输出写入 aiops_agent/runtime_outputs，不覆盖 external_projects 原始结果。</div>',
            unsafe_allow_html=True,
        )
        confirm_external = st.checkbox("我确认需要运行 external_projects 中的算法代码，并理解恢复动作保持 dry-run，不会自动执行真实恢复命令。", value=False)

    if st.button("运行端到端实时 AIOps 诊断"):
        if not dry_run and not confirm_external:
            st.error("请先勾选执行模式安全确认。")
            return
        if enable_llm and not ensure_llm_ready():
            return
        command = [
            sys.executable,
            "aiops_agent\\realtime_pipeline_agent.py",
            "--config",
            "aiops_agent\\config.json",
            "--duration-minutes",
            str(int(duration_minutes)),
            "--step-seconds",
            str(int(step_seconds)),
            "--usad-epochs",
            str(int(usad_epochs)),
            "--usad-window",
            str(int(usad_window)),
            "--usad-train-ratio",
            str(float(usad_train_ratio)),
            "--kpiroot-scenario",
            kpiroot_scenario,
            "--kpiroot-alarm",
            kpiroot_alarm,
        ]
        if dry_run:
            command.append("--dry-run")
        if execute_usad_only:
            command.append("--execute-usad-only")
        if execute_kpiroot_only:
            command.append("--execute-kpiroot-only")
        if execute_external:
            command.append("--execute-external")
        if enable_llm:
            command.append("--llm")
        with st.spinner("端到端实时 AIOps 诊断正在运行，请等待..."):
            result = run_command(command, timeout=900, env=build_llm_env())
        output = command_output(result)
        parsed = _parse_pipeline_output(output)
        render_output_box("端到端 AIOps 诊断输出", output, height=520)
        usad_executed = (execute_usad_only or execute_external) and not dry_run
        kpiroot_executed = (execute_kpiroot_only or execute_external) and not dry_run
        render_cards(
            [
                ("Prometheus 实时采集", "成功" if parsed.get("prometheus_csv") else "失败/未解析", "good" if parsed.get("prometheus_csv") else "warn"),
                ("USAD 输入生成", "成功" if parsed.get("usad_input_csv") else "失败/未解析", "good" if parsed.get("usad_input_csv") else "warn"),
                ("USAD 执行", "成功/已执行" if usad_executed else "跳过", "good" if usad_executed else "warn"),
                ("KPIRoot 输入生成", "成功" if parsed.get("kpiroot_input_csv") else "失败/未解析", "good" if parsed.get("kpiroot_input_csv") else "warn"),
                ("KPIRoot 执行", "成功/已执行" if kpiroot_executed else "跳过", "good" if kpiroot_executed else "warn"),
                ("LLM 总结", parsed.get("llm_mode") or ("未启用" if not enable_llm else "失败/未解析"), "good" if parsed.get("llm_output_path") else "warn"),
                ("LLM 输出路径", parsed.get("llm_output_path") or "(未生成)", ""),
                ("Agent 诊断", parsed.get("recovery_decision") or "(未解析)", "good" if parsed.get("recovery_decision") == "observe" else "warn"),
                ("Pipeline 报告路径", parsed.get("pipeline_report") or "(未解析)", ""),
                ("data_source_mode", parsed.get("data_source_mode") or "(未解析)", "good" if parsed.get("data_source_mode") == "realtime_runtime" else "warn"),
            ]
        )
        st.subheader("关键结果")
        render_cards(
            [
                ("prometheus_csv", parsed.get("prometheus_csv") or "(未解析)", ""),
                ("usad_input_csv", parsed.get("usad_input_csv") or "(未解析)", ""),
                ("kpiroot_input_csv", parsed.get("kpiroot_input_csv") or "(未解析)", ""),
                ("usad output_dir", "(见 pipeline report)", ""),
                ("kpiroot output_dir", "(见 pipeline report)", ""),
                ("USAD anomaly_windows", "(见 diagnosis_report / metrics_summary)", ""),
                ("USAD max_anomaly_score", "(见 diagnosis_report / metrics_summary)", ""),
                ("KPIRoot top_service", "(见 diagnosis_report / ranking.csv)", ""),
                ("KPIRoot top_metric", "(见 diagnosis_report / ranking.csv)", ""),
                ("Prometheus service_cpu_rate", parsed.get("service_cpu_rate") or "(未解析)", ""),
                ("recovery decision", parsed.get("recovery_decision") or "(未解析)", "warn"),
                ("risk level", parsed.get("risk_level") or "(未解析)", "warn"),
                ("llm_output_path", parsed.get("llm_output_path") or "(未生成)", ""),
            ]
        )
        if parsed.get("recovery_decision") == "cpu_pressure_investigation":
            st.warning("当前实时数据表明目标服务存在 CPU 压力，USAD 已检测到异常，KPIRoot 将根因定位到对应服务 CPU 指标，Agent 建议进入 CPU 压力排查。恢复动作保持 dry-run，不会自动执行真实恢复命令。")
        elif parsed.get("recovery_decision") == "observe":
            st.success("当前实时 Prometheus 证据未显示明显资源压力，Agent 建议继续观察。")

    if st.button("查看最新端到端 AIOps 报告"):
        reports = pipeline_report_files()
        if reports:
            show_report(reports[0])
        else:
            st.info("暂无 realtime_pipeline_report_*.md。")


def render_results_center_tab() -> None:
    st.subheader("结果与报告中心")
    groups = {
        "Agent 诊断报告": ["aiops_agent/outputs/diagnosis_report*.md"],
        "自动巡检报告与日志": ["aiops_agent/outputs/auto_diagnosis_*.md", "aiops_agent/outputs/watch_history*.csv"],
        "端到端 AIOps 报告": ["aiops_agent/runtime_outputs/realtime_pipeline_report_*.md"],
        "LLM 智能总结": [
            "aiops_agent/runtime_outputs/realtime_pipeline_llm_*.txt",
            "aiops_agent/runtime_outputs/realtime_pipeline_llm_*.md",
            "aiops_agent/outputs/*llm*.md",
            "aiops_agent/outputs/*llm*.txt",
        ],
        "USAD 实时输出": [
            "aiops_agent/runtime_outputs/usad_realtime_*/anomaly_scores.csv",
            "aiops_agent/runtime_outputs/usad_realtime_*/metrics_summary.txt",
            "aiops_agent/runtime_outputs/usad_realtime_*/anomaly_score.png",
            "aiops_agent/runtime_outputs/usad_realtime_*/reconstruction_error.png",
        ],
        "KPIRoot 实时输出": [
            "aiops_agent/runtime_outputs/kpiroot_realtime_*/summary.csv",
            "aiops_agent/runtime_outputs/kpiroot_realtime_*/*/ranking.csv",
            "aiops_agent/runtime_outputs/kpiroot_realtime_*/*/summary.json",
            "aiops_agent/runtime_outputs/kpiroot_realtime_*/topk_scores.png",
            "aiops_agent/runtime_outputs/kpiroot_realtime_*/alarm_top_candidates.png",
        ],
    }
    group_name = st.selectbox("结果分组", list(groups.keys()))
    files = _glob_many(groups[group_name])
    if not files:
        st.info("当前分组暂无可展示文件。")
        return
    selected = st.selectbox("选择文件", files, format_func=lambda path: f"{path.name} | {format_mtime(path)}")
    _display_artifact(selected)


def render_advanced_tools_tab() -> None:
    st.subheader("高级工具")
    st.markdown(
        """
        <div class="aiops-note">
        本页为兼容与调试工具。项目主线推荐使用“端到端 AIOps 诊断”，该主线会基于当前 Prometheus 实时数据重新运行 USAD/KPIRoot，
        而不是仅读取已有离线结果。旧 run_agent.py / 离线读取能力仅用于兼容调试和对照验证，不是当前推荐主流程。
        </div>
        """,
        unsafe_allow_html=True,
    )
    tool_tab1, tool_tab2 = st.tabs(["兼容检测与自动巡检", "自动巡检日志管理"])
    with tool_tab1:
        render_detection_tab()
    with tool_tab2:
        render_watch_history_tab()


def render_architecture_tab() -> None:
    st.subheader("项目架构说明")
    st.markdown(
        """
        ### 项目定位
        面向 Online Boutique 的端到端实时 AIOps 智能运维原型系统。

        ### 全组模块关系
        - ChaosMesh：故障注入。
        - Prometheus：实时指标采集。
        - USAD：异常检测。
        - KPIRoot：根因定位。
        - aiops_agent：统一编排、证据查询、诊断报告和 dry-run 恢复建议。
        - VeADK / 火山方舟：可选 LLM 智能体诊断总结。
        - Dashboard：可视化控制台。

        ### 完整主流程
        故障注入 → Prometheus 实时采集 → USAD 实时异常检测 → KPIRoot 实时根因定位 → Kubernetes / Prometheus 证据查询 → Agent 综合诊断 → LLM 可选总结 → dry-run 恢复建议 → 报告展示。

        ### 当前已完整验证场景
        `paymentservice` CPU 压力故障。

        ### 扩展故障类型
        - 内存压力故障：实验性。
        - Pod Kill 故障：实验性。
        - 网络延迟故障：待扩展，需要补充 latency / error rate 指标。

        ### 关于离线方案
        早期版本支持读取 external_projects 已有离线输出用于 Agent 诊断；当前主流程已经升级为端到端实时 AIOps，会在每次实验中采集当前 Prometheus 指标并生成 runtime 数据，再真实运行 USAD/KPIRoot。
        离线读取能力仅作为兼容与调试保留，不再作为推荐演示路线。
        """
    )


def main() -> None:
    st.set_page_config(page_title="AIOps Agent 智能运维控制台", layout="wide")
    apply_dashboard_css()
    st.title("AIOps Agent 智能运维控制台")
    render_sidebar()
    config = load_config()

    overview_tab, fault_tab, realtime_tab, results_tab, advanced_tab, architecture_tab = st.tabs(
        ["系统总览", "实时故障实验", "端到端 AIOps 诊断", "结果与报告中心", "高级工具", "项目架构说明"]
    )
    with overview_tab:
        render_overview_tab(config)
    with fault_tab:
        render_chaos_tab_v2(config)
    with realtime_tab:
        render_realtime_aiops_tab(config)
    with results_tab:
        render_results_center_tab()
    with advanced_tab:
        render_advanced_tools_tab()
    with architecture_tab:
        render_architecture_tab()
    return

    overview_tab, fault_tab, realtime_tab, results_tab, advanced_tab, architecture_tab = st.tabs(
        ["系统总览", "故障注入", "检测中心", "自动巡检日志", "报告中心", "端到端实时流水线"]
    )
    with overview_tab:
        render_overview_tab(config)
    with chaos_tab:
        render_chaos_tab_v2(config)
    with detection_tab:
        render_detection_tab()
    with history_tab:
        render_watch_history_tab()
    with report_tab:
        render_report_tab()
    with realtime_tab:
        render_realtime_pipeline_tab(config)


if __name__ == "__main__":
    main()
