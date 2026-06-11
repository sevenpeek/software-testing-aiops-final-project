"""Markdown report generator for the offline AIOps Agent."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def _resolve_path(project_root: Path, raw_path: str | None) -> Path:
    path = Path(raw_path or "aiops_agent/outputs/diagnosis_report.md")
    if path.is_absolute():
        return path
    return project_root / path


def _fmt(value: Any, digits: int = 6) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _bool_text(value: Any) -> str:
    return "是" if bool(value) else "否"


def _code_block(text: str | None, language: str = "text") -> list[str]:
    content = (text or "").strip() or "N/A"
    return [f"```{language}", content, "```"]


def _top_candidates_markdown(candidates: list[dict[str, Any]]) -> list[str]:
    if not candidates:
        return ["- N/A"]
    lines = []
    for item in candidates:
        lines.append(
            f"- Rank {item.get('rank', 'N/A')}: "
            f"`{_fmt(item.get('metric'))}` "
            f"(service=`{_fmt(item.get('service'))}`, score={_fmt(item.get('score'))})"
        )
    return lines


def _frontend_error_metrics(top_errors: list[dict[str, Any]]) -> list[str]:
    frontend_names = {"frontend_latency_ms", "frontend_status_code", "frontend_success"}
    return [str(item.get("metric")) for item in top_errors if str(item.get("metric")) in frontend_names]


def _evidence_chain_lines(usad_result: dict[str, Any], kpiroot_result: dict[str, Any]) -> list[str]:
    stats = usad_result.get("statistics", {})
    summary = usad_result.get("summary", {})
    top_metric = kpiroot_result.get("top_metric")
    top_service = kpiroot_result.get("top_service")
    metric_text = (top_metric or "").lower()
    top_errors = summary.get("top_reconstruction_error_metrics") or []
    frontend_metrics = _frontend_error_metrics(top_errors)

    lines = [
        (
            "- 异常检测证据：USAD 在当前数据集中检测到 "
            f"{_fmt(stats.get('anomaly_windows'), digits=0)} 个异常窗口，"
            f"最大异常分数为 {_fmt(stats.get('max_anomaly_score'))}，"
            f"阈值为 {_fmt(stats.get('threshold'))}。"
        ),
        f"- 根因定位证据：KPIRoot 将 `{_fmt(top_metric)}` 排在第 1 位，对应服务为 `{_fmt(top_service)}`。",
    ]

    if "cpu" in metric_text:
        lines.append("- 指标解释：Top1 指标包含 CPU，说明该场景更倾向于 CPU 压力或计算资源异常。")
    elif "memory" in metric_text:
        lines.append("- 指标解释：Top1 指标包含 memory，说明该场景更倾向于内存压力、Pod 重启或服务状态异常。")
    elif "latency" in metric_text:
        lines.append("- 指标解释：Top1 指标包含 latency，说明该场景更倾向于请求延迟或调用链异常。")
    else:
        lines.append("- 指标解释：Top1 指标需要结合服务日志、事件和监控曲线进一步解释。")

    if frontend_metrics:
        lines.append(
            "- 影响解释：USAD 的 Top reconstruction-error metrics 中包含 "
            f"{', '.join(f'`{name}`' for name in frontend_metrics)}，"
            "说明异常最终可能反映在用户入口层；这并不否定 KPIRoot 的后端根因指向，仍需通过日志和事件进一步验证。"
        )
    else:
        lines.append("- 影响解释：当前 USAD 重构误差最高指标未明显集中在前端入口指标，建议继续结合 Top-K 根因候选排查。")

    return lines


def _kubernetes_section(kubernetes_evidence: dict[str, Any] | None) -> list[str]:
    evidence = kubernetes_evidence or {}
    warnings = evidence.get("warnings") or []
    log_note = (
        "日志内容已进行脱敏处理，仅保留排障所需的摘要信息。"
        f"本次脱敏替换次数：{_fmt(evidence.get('log_redaction_replacement_count'), digits=0)}。"
        if evidence.get("logs_redaction_applied")
        else "日志内容为空，或本次未执行日志脱敏处理。"
    )
    lines = [
        "## Kubernetes 运行证据",
        "",
        f"- 查询 namespace：`{_fmt(evidence.get('namespace'))}`",
        f"- 查询服务名：`{_fmt(evidence.get('service_name'))}`",
        f"- 当前健康状态：`{_fmt(evidence.get('health_status'))}`",
        f"- kubectl 可用：{_bool_text(evidence.get('kubectl_available'))}",
        f"- Pod restart count：{_fmt(evidence.get('pod_restart_count'), digits=0)}",
        f"- Pod ready：{_fmt(evidence.get('pod_ready'))}",
        f"- Pod phase：`{_fmt(evidence.get('pod_phase'))}`",
        f"- Deployment available：{_fmt(evidence.get('deployment_available'))}",
        f"- Selected pod names：`{', '.join(evidence.get('selected_pod_names') or []) or 'N/A'}`",
        f"- Event warning 数量：{_fmt(evidence.get('event_warning_count'), digits=0)}",
        f"- Event 解释：{_fmt(evidence.get('event_interpretation'))}",
        f"- 最近 warning events：`{len(evidence.get('recent_warning_events') or [])}`",
        "",
        "Pod 查询结果：",
        *_code_block(evidence.get("pod_summary")),
        "",
        "Deployment 查询结果：",
        *_code_block(evidence.get("deployment_summary")),
        "",
        "Service 查询结果：",
        *_code_block(evidence.get("service_summary")),
        "",
        "近期 Event：",
        *_code_block(evidence.get("recent_events")),
        "",
        "服务日志尾部：",
        "",
        log_note,
        *_code_block(evidence.get("report_logs_tail") or evidence.get("logs_tail")),
    ]
    if warnings:
        lines.extend(["", "Kubernetes warnings："])
        lines.extend(f"- {warning}" for warning in warnings)
    return lines


def _kubernetes_diagnosis_lines(kubernetes_evidence: dict[str, Any] | None) -> list[str]:
    evidence = kubernetes_evidence or {}
    status = evidence.get("health_status")
    logs_tail = evidence.get("report_logs_tail") or evidence.get("logs_tail")
    has_event_warnings = bool(evidence.get("has_event_warnings"))
    lines: list[str] = []

    if not evidence.get("enabled"):
        lines.append("Kubernetes 证据查询当前未启用，因此本报告未纳入实时集群状态。")
        return lines

    if status == "healthy":
        lines.append(
            "Kubernetes 证据显示当前该服务处于 Running/Available 状态，当前运行状态未显示明显容器级故障。"
            "因此 USAD 与 KPIRoot 结果更像是离线故障实验数据中的异常证据，需要结合后续 Prometheus 实时指标进一步验证。"
        )
        if has_event_warnings:
            lines.append(
                "近期 Event 中存在启动阶段的 Warning/Unhealthy 记录，但当前 Pod 与 Deployment 已恢复为 "
                "Running/Available，因此这些事件更可能是启动过程中的短暂探针失败，仍建议结合 Prometheus 实时指标进一步确认。"
            )
    elif status == "image_pull_error":
        lines.append("Kubernetes 证据显示服务当前存在镜像拉取问题，可能导致服务不可用。")
    elif status == "crash_loop":
        lines.append("Kubernetes 证据显示服务容器反复崩溃，需要优先检查日志。")
    elif status == "not_found":
        lines.append("Kubernetes 证据显示根因服务在当前 namespace 中未找到，需要检查部署状态或服务名映射。")
    else:
        lines.append("Kubernetes 证据暂未给出明确健康结论，需要结合 Pod、Deployment、Event 与日志继续判断。")
        if has_event_warnings:
            lines.append("近期 Event 中存在 Warning/Unhealthy/Failed/BackOff 记录，这些事件可能与当前异常有关。")

    if logs_tail:
        lines.append("Agent 已经完成该服务的日志尾部采集，日志已脱敏并限制展示行数，可在“Kubernetes 运行证据”章节中查看。")
    return lines


def _prometheus_section(prometheus_metrics: dict[str, Any] | None) -> list[str]:
    metrics = prometheus_metrics or {}
    summary = metrics.get("summary") or {}
    raw_queries = metrics.get("raw_queries") or {}
    warnings = metrics.get("warnings") or []

    lines = [
        "## Prometheus 实时指标证据",
        "",
        f"- 查询模式：`{_fmt(metrics.get('query_mode'))}`",
        f"- monitoring namespace：`{_fmt(metrics.get('monitoring_namespace'))}`",
        f"- Prometheus deployment：`{_fmt(metrics.get('prometheus_deployment'))}`",
        f"- 查询服务名：`{_fmt(metrics.get('service_name'))}`",
        f"- Prometheus 可用性：{_bool_text(metrics.get('prometheus_available'))}",
        f"- CPU 指标序列数量：{_fmt(summary.get('cpu_series_count'))}",
        f"- Online Boutique 总 CPU rate：{_fmt(summary.get('online_boutique_cpu_total_rate'))}",
        f"- 服务 CPU rate：{_fmt(summary.get('service_cpu_rate'))}",
        f"- 服务 memory working set bytes：{_fmt(summary.get('service_memory_working_set_bytes'))}",
        f"- 服务 memory working set MiB：{_fmt(summary.get('service_memory_working_set_mib'))}",
        f"- service container count：{_fmt(summary.get('service_container_count'))}",
        f"- container restart count（可选 kube-state 指标）：{_fmt(summary.get('container_restart_count'))}",
        f"- 指标解释：{_fmt(summary.get('interpretation'))}",
        f"- Memory 指标解释：{_fmt(summary.get('memory_interpretation'))}",
        f"- Network latency 指标说明：{_fmt(summary.get('network_latency_interpretation'))}",
        "",
        "查询 PromQL：",
    ]

    if raw_queries:
        for name, promql in raw_queries.items():
            lines.append(f"- `{name}`:")
            lines.extend(_code_block(str(promql), "promql"))
    else:
        lines.append("- N/A")

    if warnings:
        lines.extend(["", "Prometheus warnings："])
        lines.extend(f"- {warning}" for warning in warnings)
    return lines


def _prometheus_diagnosis_lines(
    kubernetes_evidence: dict[str, Any] | None,
    prometheus_metrics: dict[str, Any] | None,
) -> list[str]:
    prometheus = prometheus_metrics or {}
    summary = prometheus.get("summary") or {}
    service_cpu_rate = summary.get("service_cpu_rate")
    prometheus_available = bool(prometheus.get("prometheus_available"))
    kubernetes_status = (kubernetes_evidence or {}).get("health_status")
    lines: list[str] = []

    if not prometheus.get("enabled"):
        lines.append("Prometheus 实时指标查询当前未启用。")
        return lines

    if not prometheus_available:
        lines.append("Prometheus 查询不到指标或 API 不可用，需要检查 Prometheus scrape 配置、Prometheus Pod 状态或 kubectl exec 权限。")
    elif service_cpu_rate is None:
        lines.append("Prometheus 当前未返回服务 CPU rate，需要检查容器指标标签、Pod 名称匹配或 scrape 配置。")
    elif kubernetes_status == "healthy" and service_cpu_rate < 0.01:
        lines.append(
            "Kubernetes health_status=healthy，且 Prometheus service_cpu_rate 很低，"
            "说明当前实时系统运行较平稳，离线 USAD/KPIRoot 异常更可能来自历史故障注入数据。"
        )
    elif service_cpu_rate >= 0.5:
        lines.append("Prometheus service_cpu_rate 较高，实时指标支持 CPU 压力判断。")
    else:
        lines.append("Prometheus 已返回服务级 CPU 指标，但当前数值未达到明显 CPU 压力阈值，建议结合历史基线继续判断。")

    lines.append("当前阶段未依赖 kube-state-metrics，因为 kube-state-metrics 当前不可用或未恢复；报告主要使用 cAdvisor/container 指标。")
    return lines


def _fault_type_metadata(fault_type: str | None) -> dict[str, str]:
    mapping = {
        "cpu_stress": {
            "status": "verified",
            "basis": "Prometheus service_cpu_rate",
            "limitation": "CPU pressure is the fully verified end-to-end demo scenario.",
            "diagnosis": "CPU fault context: if service_cpu_rate is above threshold, the Agent treats this as CPU pressure evidence.",
        },
        "memory_stress": {
            "status": "experimental",
            "basis": "Prometheus service_memory_working_set_mib plus Kubernetes Events",
            "limitation": "Memory thresholds depend on local cluster capacity and container limits.",
            "diagnosis": "Memory fault context: the Agent prioritizes memory working set, OOM/Event evidence, and container limits.",
        },
        "pod_kill": {
            "status": "experimental",
            "basis": "Pod phase, readiness, restart count, Deployment availability, and Kubernetes Events",
            "limitation": "Pod kill evidence is timing-sensitive and may disappear after the Deployment recovers.",
            "diagnosis": "Pod kill context: if restart/Event evidence exists but Pods are Running, the recommendation is observe and preserve evidence.",
        },
        "network_delay": {
            "status": "planned / experimental",
            "basis": "Kubernetes Events plus future application latency/error-rate metrics",
            "limitation": "Current Prometheus queries do not include application latency/error-rate metrics.",
            "diagnosis": "Network delay context: current version keeps the decision as manual review until latency/error metrics are added.",
        },
    }
    return mapping.get(str(fault_type or "cpu_stress"), mapping["cpu_stress"])


def _fault_context_section(
    config: dict[str, Any],
    kpiroot_result: dict[str, Any],
    recovery_plan: dict[str, Any] | None,
) -> list[str]:
    fault_type = (
        (recovery_plan or {}).get("fault_type")
        or config.get("faults", {}).get("default_fault_type")
        or "cpu_stress"
    )
    target_service = (
        (recovery_plan or {}).get("service_name")
        or kpiroot_result.get("top_service")
        or config.get("faults", {}).get("default_service")
        or "paymentservice"
    )
    metadata = _fault_type_metadata(str(fault_type))
    return [
        "## 故障实验上下文",
        "",
        f"- fault_type: `{_fmt(fault_type)}`",
        f"- target_service: `{_fmt(target_service)}`",
        f"- fault_status: `{metadata['status']}`",
        f"- 检测依据: {metadata['basis']}",
        f"- 当前局限: {metadata['limitation']}",
    ]


def _fault_diagnosis_lines(recovery_plan: dict[str, Any] | None) -> list[str]:
    if (recovery_plan or {}).get("decision") == "observe":
        return [
            "Fault context: current real-time evidence does not show active CPU, memory, Pod Kill, or network-delay fault pressure; the Agent keeps the recovery recommendation at observe."
        ]
    fault_type = (recovery_plan or {}).get("fault_type") or "cpu_stress"
    metadata = _fault_type_metadata(str(fault_type))
    return [metadata["diagnosis"]]


def _recovery_diagnosis_lines(recovery_plan: dict[str, Any] | None) -> list[str]:
    plan = recovery_plan or {}
    if not plan.get("enabled"):
        return ["恢复计划生成功能当前未启用，Agent 不会给出恢复动作草案。"]
    if plan.get("decision") == "observe":
        return [
            "基于当前 Kubernetes 与 Prometheus 实时证据，Agent 生成了恢复计划。"
            "由于当前服务实时状态为 healthy 且 CPU 使用率较低，本次建议以观察和继续采集证据为主，不自动执行重启。"
        ]
    return [
        f"基于当前 Kubernetes 与 Prometheus 实时证据，Agent 生成了恢复计划，决策为 `{_fmt(plan.get('decision'))}`，"
        f"风险等级为 `{_fmt(plan.get('risk_level'))}`。当前计划仅用于人工复核，不会自动执行恢复命令。"
    ]


def _diagnosis_text(
    usad_result: dict[str, Any],
    kpiroot_result: dict[str, Any],
    kubernetes_evidence: dict[str, Any] | None,
    prometheus_metrics: dict[str, Any] | None,
    recovery_plan: dict[str, Any] | None,
) -> list[str]:
    stats = usad_result.get("statistics", {})
    summary = usad_result.get("summary", {})
    has_anomaly = bool(stats.get("has_anomaly"))
    top_service = kpiroot_result.get("top_service")
    top_metric = kpiroot_result.get("top_metric")
    top_errors = summary.get("top_reconstruction_error_metrics") or []
    frontend_metrics = _frontend_error_metrics(top_errors)

    if has_anomaly and top_service:
        paragraph = (
            f"Agent 首先根据 USAD 结果判断系统存在异常；随后根据 KPIRoot 排名，将 `{top_service}` 作为优先排查对象。"
            f"Top1 指标为 `{_fmt(top_metric)}`，说明异常更可能与该服务的某类资源或状态变化有关。"
            "结合异常检测和根因定位结果，Agent 建议后续优先围绕该服务收集 Pod 状态、日志、事件和 Prometheus 指标。"
        )
    elif not has_anomaly:
        paragraph = (
            "USAD 未检测到明确异常，说明当前离线数据中的异常证据不足。"
            "KPIRoot 的排序结果仍可作为人工复核线索，但不应单独作为恢复动作依据。"
        )
    else:
        paragraph = (
            "USAD 已检测到异常，但 KPIRoot 结果未解析出明确的 Top1 服务。"
            "建议优先检查 Top-K 指标对应的服务，并补充实时日志、事件和 Prometheus 证据。"
        )

    lines = [paragraph]
    if frontend_metrics and top_service and not any(top_service in metric for metric in frontend_metrics):
        lines.append(
            "USAD 重构误差较高的指标包含前端入口层指标，而 KPIRoot Top1 服务指向后端服务。"
            "这不应被视为矛盾，更合理的解释是：异常可能在入口层表现明显，"
            "但根因定位结果指向后端服务，需要进一步通过日志和 Kubernetes Event 验证。"
        )
    lines.extend(_kubernetes_diagnosis_lines(kubernetes_evidence))
    lines.extend(_prometheus_diagnosis_lines(kubernetes_evidence, prometheus_metrics))
    lines.extend(_fault_diagnosis_lines(recovery_plan))
    lines.extend(_recovery_diagnosis_lines(recovery_plan))
    return lines


def _recovery_section(recovery_plan: dict[str, Any] | None) -> list[str]:
    plan = recovery_plan or {}
    recommended_actions = plan.get("recommended_actions") or []
    suggested_commands = plan.get("suggested_commands") or []
    safety_notes = plan.get("safety_notes") or []

    lines = [
        "## 恢复建议与执行保护",
        "",
        f"- 恢复计划状态 enabled：{_bool_text(plan.get('enabled'))}",
        f"- 是否执行真实恢复命令 execute_recovery：{_bool_text(plan.get('execute_recovery'))}",
        f"- dry_run 状态：{_bool_text(plan.get('dry_run'))}",
        f"- 目标服务：`{_fmt(plan.get('service_name'))}`",
        f"- 根因指标：`{_fmt(plan.get('root_metric'))}`",
        f"- 故障类型 fault_type：`{_fmt(plan.get('fault_type'))}`",
        f"- 决策 decision：`{_fmt(plan.get('decision'))}`",
        f"- 风险等级 risk_level：`{_fmt(plan.get('risk_level'))}`",
        "",
        "当前 execute_recovery=false / dry_run=true，Agent 只生成恢复建议，不执行真实恢复命令。",
        "",
        "推荐动作：",
    ]
    lines.extend(f"- {action}" for action in recommended_actions) if recommended_actions else lines.append("- N/A")
    lines.extend(["", "建议命令："])
    if suggested_commands:
        for command in suggested_commands:
            lines.extend(_code_block(command, "powershell"))
    else:
        lines.append("- N/A")
    lines.extend(["", "安全说明："])
    lines.extend(f"- {note}" for note in safety_notes) if safety_notes else lines.append("- 当前没有额外安全说明。")
    return lines


def _operation_suggestions(namespace: str | None, service: str | None) -> list[str]:
    ns = namespace or "online-boutique"
    svc = service or "<top_service>"
    return [
        "- 查看根因服务 Pod 状态：",
        f"  ```powershell\n  kubectl get pods -n {ns} | findstr {svc}\n  ```",
        "- 查看根因服务日志：",
        f"  ```powershell\n  kubectl logs deployment/{svc} -n {ns} --tail=100\n  ```",
        "- 查看近期事件：",
        f"  ```powershell\n  kubectl get events -n {ns} --sort-by=.lastTimestamp\n  ```",
        "- 查询 Prometheus 指标：",
        f"  例如查询 `{svc}` 的 CPU、内存、请求延迟或错误率相关指标。",
        "- 如确认服务异常，再考虑：",
        f"  ```powershell\n  kubectl rollout restart deployment/{svc} -n {ns}\n  ```",
    ]


def generate_report(
    config: dict[str, Any],
    project_root: Path,
    usad_result: dict[str, Any],
    kpiroot_result: dict[str, Any],
    kubernetes_evidence: dict[str, Any] | None = None,
    prometheus_metrics: dict[str, Any] | None = None,
    recovery_plan: dict[str, Any] | None = None,
) -> Path:
    """Generate a Markdown diagnosis report and return its path."""

    output_path = _resolve_path(project_root, config.get("agent", {}).get("output_report"))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    system = config.get("system", {})
    stats = usad_result.get("statistics", {})
    summary = usad_result.get("summary", {})
    enable_recovery = bool(config.get("agent", {}).get("enable_recovery", False))
    namespace = system.get("namespace")
    top_service = kpiroot_result.get("top_service")

    lines = [
        "# AIOps Agent 智能运维诊断报告",
        "",
        "## 1. 基本信息",
        "",
        f"- 系统名称：{_fmt(system.get('name'))}",
        f"- namespace：{_fmt(namespace)}",
        f"- 运行模式：{_fmt(config.get('display_mode') or config.get('mode'))}（离线算法结果 + 在线运行证据）",
        "- Agent 类型：规则编排型 AIOps Agent",
        "- 数据来源：USAD 输出文件 + KPIRoot 输出文件 + Kubernetes 只读查询 + Prometheus 实时指标",
        "- 当前阶段：第三阶段，已加入 Kubernetes 只读证据查询与 Prometheus 实时指标查询。",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 2. 异常检测结果（USAD）",
        "",
        "USAD 的作用是判断当前 KPI 时间序列中是否存在异常窗口，它解决的是“是否异常”的问题。",
        "",
        f"- 使用的数据集：{_fmt(usad_result.get('dataset_name'))}",
        f"- anomaly_scores.csv 路径：`{_fmt(usad_result.get('paths', {}).get('anomaly_scores'))}`",
        f"- metrics_summary.txt 路径：`{_fmt(usad_result.get('paths', {}).get('metrics_summary'))}`",
        f"- total_windows：{_fmt(stats.get('total_windows'), digits=0)}",
        f"- anomaly_windows：{_fmt(stats.get('anomaly_windows'), digits=0)}",
        f"- max_anomaly_score：{_fmt(stats.get('max_anomaly_score'))}",
        f"- mean_anomaly_score：{_fmt(stats.get('mean_anomaly_score'))}",
        f"- threshold：{_fmt(stats.get('threshold'))}",
        f"- precision / recall / f1：{_fmt(summary.get('precision'))} / {_fmt(summary.get('recall'))} / {_fmt(summary.get('f1'))}",
        f"- tp / fp / fn / tn：{_fmt(summary.get('tp'))} / {_fmt(summary.get('fp'))} / {_fmt(summary.get('fn'))} / {_fmt(summary.get('tn'))}",
        f"- 初步判断：是否检测到异常：{_bool_text(stats.get('has_anomaly'))}",
        "",
        "Top reconstruction-error metrics：",
    ]

    top_errors = summary.get("top_reconstruction_error_metrics") or []
    if top_errors:
        for item in top_errors:
            lines.append(f"- `{item.get('metric')}`: {_fmt(item.get('value'))}")
    else:
        lines.append("- N/A")

    lines.extend(
        [
            "",
            "## 3. 根因定位结果（KPIRoot）",
            "",
            "KPIRoot 的作用是在异常发生后对候选 KPI 和服务进行排序，它解决的是“异常可能在哪里”的问题。",
            "",
            f"- 使用的 scenario：{_fmt(kpiroot_result.get('scenario'))}",
            f"- summary.csv 路径：`{_fmt(kpiroot_result.get('paths', {}).get('summary_csv'))}`",
            f"- ranking.csv 路径：`{_fmt(kpiroot_result.get('paths', {}).get('ranking_csv'))}`",
            f"- Top1 根因指标：`{_fmt(kpiroot_result.get('top_metric'))}`",
            f"- Top1 根因服务：`{_fmt(top_service)}`",
            f"- Top1 得分：{_fmt(kpiroot_result.get('top_score'))}",
            "",
            "Top5 候选根因：",
            *_top_candidates_markdown(kpiroot_result.get("top_candidates", [])),
            "",
            "## 4. 证据链分析",
            "",
            *_evidence_chain_lines(usad_result, kpiroot_result),
            "",
            *_fault_context_section(config, kpiroot_result, recovery_plan),
            "",
            *_kubernetes_section(kubernetes_evidence),
            "",
            *_prometheus_section(prometheus_metrics),
            "",
            "## 5. Agent 综合诊断",
            "",
            *_diagnosis_text(usad_result, kpiroot_result, kubernetes_evidence, prometheus_metrics, recovery_plan),
            "",
            *_recovery_section(recovery_plan),
            "",
            "## 6. 建议的下一步运维动作",
            "",
            *_operation_suggestions(namespace, top_service),
            "",
        ]
    )

    if not enable_recovery:
        lines.append("当前配置 enable_recovery=false，Agent 不会执行真实恢复命令。")
    else:
        lines.append("当前配置 enable_recovery=true，但本离线版本仍不会自动执行恢复命令，执行前必须人工确认。")

    lines.extend(
        [
            "",
            "## 7. 当前版本局限",
            "",
            "- 当前 Agent 仍以离线 USAD 和 KPIRoot 输出为核心输入。",
            "- 当前 Agent 只执行 Kubernetes 只读查询，不会修改集群状态。",
            "- 当前 Agent 通过 kubectl exec 只读查询 Prometheus API，不会修改 Prometheus 或业务服务状态。",
            "- 当前 Agent 不会执行真实恢复命令。",
            "- 当前 Agent 暂不依赖 kube-state-metrics，主要使用 cAdvisor/container 指标。",
            "- USAD 与 KPIRoot 的离线故障场景仍需要在最终演示中进一步对齐。",
        ]
    )

    warnings = (
        (usad_result.get("warnings") or [])
        + (kpiroot_result.get("warnings") or [])
        + ((kubernetes_evidence or {}).get("warnings") or [])
        + ((prometheus_metrics or {}).get("warnings") or [])
    )
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return output_path
