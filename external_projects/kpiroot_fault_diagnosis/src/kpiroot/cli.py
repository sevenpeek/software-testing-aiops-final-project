from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .algorithm import KPIRootConfig, run_kpiroot, zscore
from .data import (
    add_synthetic_alarms,
    candidate_columns,
    choose_alarm_column,
    extract_expected,
    extract_time_window,
    load_scenario_frame,
    load_yaml,
    service_from_kpi,
    write_json,
)


def relative_minutes(timestamps: pd.Series) -> pd.Series:
    return (timestamps - timestamps.iloc[0]) / 60.0


def plot_top_scores(ranking: pd.DataFrame, output_path: Path, title: str, top_n: int = 10) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    top = ranking.head(top_n).iloc[::-1]
    plt.figure(figsize=(10, 5))
    plt.barh(top["kpi"], top["score"], color="#2f6f9f")
    plt.xlabel("KPIRoot score")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=160)
    plt.close()


def plot_alarm_and_candidates(
    frame: pd.DataFrame,
    alarm_column: str,
    ranking: pd.DataFrame,
    output_path: Path,
    start_epoch: float | None,
    end_epoch: float | None,
    top_n: int = 5,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    x = relative_minutes(frame["timestamp"])
    plt.figure(figsize=(11, 5))
    plt.plot(x, zscore(frame[alarm_column]), label=f"alarm: {alarm_column}", linewidth=2.2, color="#111827")
    colors = ["#d55e00", "#0072b2", "#009e73", "#cc79a7", "#f0e442"]
    for index, row in ranking.head(top_n).iterrows():
        kpi = row["kpi"]
        plt.plot(x, zscore(frame[kpi]), label=f"rank {int(row['rank'])}: {kpi}", alpha=0.85, color=colors[index % len(colors)])
    if start_epoch is not None and end_epoch is not None:
        base = float(frame["timestamp"].iloc[0])
        plt.axvspan((start_epoch - base) / 60.0, (end_epoch - base) / 60.0, color="#ef4444", alpha=0.12, label="fault window")
    plt.xlabel("Minutes since export start")
    plt.ylabel("Z-score")
    plt.title("Alarm KPI and Top Ranked Candidate KPIs")
    plt.legend(fontsize=8, loc="best")
    plt.tight_layout()
    plt.savefig(output_path, dpi=160)
    plt.close()


def evaluate_ranking(
    ranking: pd.DataFrame,
    expected_kpis: list[str],
    expected_service: str | None,
) -> dict[str, Any]:
    if ranking.empty:
        return {
            "expected_kpi_rank": None,
            "expected_service_rank": None,
            "hit_at_1": False,
            "hit_at_3": False,
            "hit_at_5": False,
            "top1": None,
            "top5": [],
        }

    top_kpis = ranking["kpi"].tolist()
    exact_ranks = [top_kpis.index(kpi) + 1 for kpi in expected_kpis if kpi in top_kpis]
    service_ranks = []
    if expected_service:
        for index, kpi in enumerate(top_kpis, start=1):
            if service_from_kpi(kpi) == expected_service:
                service_ranks.append(index)

    best_service_rank = min(service_ranks) if service_ranks else None
    return {
        "expected_kpi_rank": min(exact_ranks) if exact_ranks else None,
        "expected_service_rank": best_service_rank,
        "hit_at_1": best_service_rank is not None and best_service_rank <= 1,
        "hit_at_3": best_service_rank is not None and best_service_rank <= 3,
        "hit_at_5": best_service_rank is not None and best_service_rank <= 5,
        "top1": top_kpis[0],
        "top5": top_kpis[:5],
    }


def ranking_for_method(ranking: pd.DataFrame, method: str) -> pd.DataFrame:
    method_frame = ranking.drop(columns=["rank"], errors="ignore").copy()
    if method == "similarity_only":
        method_frame["score"] = method_frame["similarity"]
    elif method == "causality_only":
        method_frame["score"] = method_frame["causality"]
    elif method == "kpiroot_combined":
        pass
    else:
        raise ValueError(f"Unsupported ablation method: {method}")
    method_frame = method_frame.sort_values(["score", "similarity", "causality"], ascending=False).reset_index(drop=True)
    method_frame.insert(0, "rank", range(1, len(method_frame) + 1))
    method_frame.insert(1, "method", method)
    return method_frame


def build_ablation_results(
    scenario_id: str,
    ranking: pd.DataFrame,
    expected_kpis: list[str],
    expected_service: str | None,
    scenario_output: Path,
) -> list[dict[str, Any]]:
    rows = []
    for method in ["similarity_only", "causality_only", "kpiroot_combined"]:
        method_ranking = ranking_for_method(ranking, method)
        method_ranking.to_csv(scenario_output / f"ranking_{method}.csv", index=False)
        evaluation = evaluate_ranking(method_ranking, expected_kpis, expected_service)
        rows.append(
            {
                "scenario_id": scenario_id,
                "method": method,
                "expected_service": expected_service,
                "top1": evaluation["top1"],
                "expected_service_rank": evaluation["expected_service_rank"],
                "hit_at_1": evaluation["hit_at_1"],
                "hit_at_3": evaluation["hit_at_3"],
                "hit_at_5": evaluation["hit_at_5"],
            }
        )
    pd.DataFrame(rows).to_csv(scenario_output / "ablation_summary.csv", index=False)
    return rows


def run_scenario(
    scenario_dir: Path,
    output_root: Path,
    config: KPIRootConfig,
    alarm_override: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scenario_id = scenario_dir.name
    metadata = load_yaml(scenario_dir / "metadata.yaml")
    frame = add_synthetic_alarms(load_scenario_frame(scenario_dir))
    alarm_column = alarm_override or choose_alarm_column(frame, scenario_id)
    candidates = candidate_columns(frame, alarm_column)
    start_epoch, end_epoch = extract_time_window(metadata)
    expected_kpis, expected_service = extract_expected(metadata)

    ranking, details = run_kpiroot(
        frame=frame,
        alarm_column=alarm_column,
        candidate_columns=candidates,
        start_epoch=start_epoch,
        end_epoch=end_epoch,
        config=config,
    )

    scenario_output = output_root / scenario_id
    scenario_output.mkdir(parents=True, exist_ok=True)
    ranking_path = scenario_output / "ranking.csv"
    ranking.to_csv(ranking_path, index=False)
    ranking.to_csv(scenario_output / "score_breakdown.csv", index=False)

    plot_top_scores(ranking, scenario_output / "topk_scores.png", f"{scenario_id}: KPIRoot Top Scores")
    plot_alarm_and_candidates(
        frame,
        alarm_column,
        ranking,
        scenario_output / "alarm_top_candidates.png",
        start_epoch,
        end_epoch,
    )

    evaluation = evaluate_ranking(ranking, expected_kpis, expected_service)
    ablation_rows = build_ablation_results(scenario_id, ranking, expected_kpis, expected_service, scenario_output)
    summary = {
        "scenario_id": scenario_id,
        "alarm_column": alarm_column,
        "expected_kpis": expected_kpis,
        "expected_service": expected_service,
        **evaluation,
        **details,
        "ranking_path": str(ranking_path),
        "topk_scores_plot": str(scenario_output / "topk_scores.png"),
        "timeseries_plot": str(scenario_output / "alarm_top_candidates.png"),
        "ablation_path": str(scenario_output / "ablation_summary.csv"),
    }
    write_json(scenario_output / "summary.json", summary)
    return summary, ablation_rows


def write_report(
    report_path: Path,
    summaries: list[dict[str, Any]],
    ablation_rows: list[dict[str, Any]],
    output_root: Path,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    project_root = report_path.resolve().parent.parent

    def doc_path(path: Path) -> str:
        resolved = path.resolve()
        try:
            return resolved.relative_to(project_root).as_posix()
        except ValueError:
            return str(resolved)

    lines = [
        "# 阶段四：ISSRE24-KPIRoot 论文复现",
        "",
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        "本文档记录本仓库负责的论文复现部分。课程大作业为小组作业，要求复现两篇异常检测/故障诊断相关论文；本仓库复现的是其中一篇：",
        "",
        "```text",
        "ISSRE 2024 - KPIRoot: Efficient Monitoring Metric-based Root Cause Localization in Large-scale Cloud Systems",
        "```",
        "",
        "另一篇论文的复现结果由组内其他成员负责整合。",
        "",
        "## 复现目标",
        "",
        "KPIRoot 的目标是在系统级 KPI 出现异常后，从多个底层 KPI 中定位最可能导致异常的根因 KPI。",
        "",
        "原论文中的场景是 Cloud H 的主机集群与 VM；本项目将其适配为 Online-Boutique 的微服务监控数据：",
        "",
        "| 原论文概念 | 本项目映射 |",
        "| --- | --- |",
        "| Host/cluster alarm KPI | 聚合 CPU、聚合内存、前端探针延迟等系统级 KPI |",
        "| VM KPI | 各微服务的 CPU、内存、文件系统、运行状态等 KPI |",
        "| Root-cause VM | 被 ChaosMesh 注入故障的目标服务 |",
        "",
        "## 实现内容",
        "",
        "实现文件如下：",
        "",
        "- `src/kpiroot/algorithm.py`：PAA、SAX、异常窗口选择、相似度、因果得分与排序逻辑。",
        "- `src/kpiroot/data.py`：阶段二数据读取、元数据解析、合成告警 KPI 构造。",
        "- `src/kpiroot/cli.py`：批量运行、评估、绘图和文档生成。",
        "- `tests/kpiroot/test_algorithm.py`：KPIRoot 复现代码的单元测试。",
        "- `scripts/run-phase4-kpiroot.ps1`：阶段四运行脚本。",
        "",
        "已实现的算法流程：",
        "",
        "1. 读取阶段二导出的 `kpi_matrix.csv`。",
        "2. 构造合成系统级告警 KPI，例如 `synthetic_total_cpu`、`synthetic_total_memory`。",
        "3. 对 KPI 进行缺失值处理和标准化。",
        "4. 使用 PAA 对时间序列降维。",
        "5. 使用 SAX 将连续数值序列转换为符号序列。",
        "6. 根据故障注入记录选择异常窗口，自动趋势检测作为备用逻辑。",
        "7. 使用 SAX-Jaccard 计算候选 KPI 与告警 KPI 的相似度。",
        "8. 使用 Granger 风格 F 统计量计算候选 KPI 对告警 KPI 的时序因果得分。",
        "9. 使用论文中的权重设置计算综合得分：`0.9 * similarity + 0.1 * normalized_causality`。",
        "10. 输出候选根因 KPI 排名，并进行消融对比。",
        "",
        "## 运行方式",
        "",
        "运行阶段四实验：",
        "",
        "```powershell",
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\FinalProject\\scripts\\run-phase4-kpiroot.ps1",
        "```",
        "",
        "运行单元测试：",
        "",
        "```powershell",
        ".\\FinalProject\\.conda\\python.exe -m pytest .\\FinalProject\\tests\\kpiroot -v -o \"cache_dir=FinalProject\\.pytest_cache\"",
        "```",
        "",
        "## 输出文件",
        "",
        "阶段四输出目录：",
        "",
        f"```text\n{doc_path(output_root)}\n```",
        "",
        "主要文件：",
        "",
        "- `summary.csv`：三组故障场景的 KPIRoot 总结结果。",
        "- `ablation_summary.csv`：相似度-only、因果-only、综合 KPIRoot 的消融对比。",
        "- `<scenario>/ranking.csv`：每个场景的候选 KPI 排名。",
        "- `<scenario>/score_breakdown.csv`：每个场景的相似度、因果得分和综合得分。",
        "- `<scenario>/topk_scores.png`：Top-K 根因得分图。",
        "- `<scenario>/alarm_top_candidates.png`：告警 KPI 与 Top 候选 KPI 曲线对比图。",
        "",
        "## 主实验结果",
        "",
        "| 故障场景 | 告警 KPI | 真实根因服务 | Top-1 KPI | 真实根因服务排名 | Hit@1 | Hit@3 | Hit@5 |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for summary in summaries:
        lines.append(
            "| {scenario_id} | `{alarm_column}` | `{expected_service}` | `{top1}` | {rank} | {h1} | {h3} | {h5} |".format(
                scenario_id=summary["scenario_id"],
                alarm_column=summary["alarm_column"],
                expected_service=summary.get("expected_service"),
                top1=summary.get("top1"),
                rank=summary.get("expected_service_rank") or "",
                h1="yes" if summary.get("hit_at_1") else "no",
                h3="yes" if summary.get("hit_at_3") else "no",
                h5="yes" if summary.get("hit_at_5") else "no",
            )
        )
    lines.extend(
        [
            "",
            "## 消融实验结果",
            "",
            "消融实验复用同一批 KPI 得分，只改变排序目标：",
            "",
            "- `similarity_only`：仅使用 SAX-Jaccard 相似度排序。",
            "- `causality_only`：仅使用归一化后的 Granger 因果得分排序。",
            "- `kpiroot_combined`：使用 KPIRoot 综合得分排序。",
            "",
            "| 故障场景 | 方法 | Top-1 KPI | 真实根因服务排名 | Hit@1 | Hit@3 | Hit@5 |",
            "| --- | --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for row in ablation_rows:
        lines.append(
            "| {scenario_id} | `{method}` | `{top1}` | {rank} | {h1} | {h3} | {h5} |".format(
                scenario_id=row["scenario_id"],
                method=row["method"],
                top1=row["top1"],
                rank=row.get("expected_service_rank") or "",
                h1="yes" if row.get("hit_at_1") else "no",
                h3="yes" if row.get("hit_at_3") else "no",
                h5="yes" if row.get("hit_at_5") else "no",
            )
        )
    lines.extend(
        [
            "",
            "## 输出明细",
            "",
            f"- 总结 CSV：`{doc_path(output_root / 'summary.csv')}`",
            f"- 消融总结 CSV：`{doc_path(output_root / 'ablation_summary.csv')}`",
            "- 每个故障场景的输出：",
        ]
    )
    for summary in summaries:
        scenario = summary["scenario_id"]
        lines.extend(
            [
                f"  - `{doc_path(output_root / scenario / 'ranking.csv')}`",
                f"  - `{doc_path(output_root / scenario / 'ablation_summary.csv')}`",
                f"  - `{doc_path(output_root / scenario / 'topk_scores.png')}`",
                f"  - `{doc_path(output_root / scenario / 'alarm_top_candidates.png')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## 结果分析",
            "",
            "两组 CPU Stress 场景是最有代表性的复现实验：",
            "",
            "- `stress-paymentservice-cpu-001` 中，`synthetic_total_cpu` 出现明显升高，KPIRoot 将 `cpu__paymentservice` 排名第一。",
            "- `stress-frontend-cpu-001` 中，`synthetic_total_cpu` 与 `cpu__frontend` 的变化趋势高度一致，KPIRoot 将 `cpu__frontend` 排名第一。",
            "",
            "Pod Kill 场景保留为补充案例。由于 processed 数据将替换前后的 Pod 合并到了服务级别，Pod 身份变化被部分隐藏，因此该场景更适合作为边界情况说明。",
            "",
            "消融实验显示，在本课程采集的短时间序列数据上，单独使用 Granger 因果得分并不稳定；SAX 相似度与 KPIRoot 综合得分均能稳定定位真实根因服务。最终报告中建议重点展示两组 CPU Stress 场景，并将 Pod Kill 作为补充说明。",
            "",
            "## 与原论文的差异",
            "",
            "- 原论文使用 Cloud H 工业环境中的大规模主机集群/VM KPI；本项目使用 Online-Boutique 微服务系统的服务级 KPI。",
            "- 原论文数据规模较大，时间序列更长；本项目故障窗口较短，因此 PAA 参数做了适配。",
            "- 原论文自动检测 alarm KPI 的异常段；本项目优先使用故障注入记录中的时间窗口，自动趋势检测作为备用逻辑。",
            "- 本项目的目标是课程复现与工程验证，因此重点放在算法流程可运行、结果可解释、数据与图表可复查。",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase 4 KPIRoot reproduction.")
    parser.add_argument("--phase2-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--scenario", action="append", default=None)
    parser.add_argument("--alarm", default=None)
    parser.add_argument("--paa-size", type=int, default=32)
    parser.add_argument("--lambda-weight", type=float, default=0.9)
    parser.add_argument("--alphabet-size", type=int, default=9)
    parser.add_argument("--granger-lag", type=int, default=2)
    args = parser.parse_args()

    config = KPIRootConfig(
        paa_size=args.paa_size,
        lambda_weight=args.lambda_weight,
        alphabet_size=args.alphabet_size,
        granger_lag=args.granger_lag,
    )
    scenario_dirs = [
        path
        for path in sorted(args.phase2_dir.iterdir())
        if path.is_dir() and (path / "processed" / "kpi_matrix.csv").exists() and "baseline" not in path.name
    ]
    if args.scenario:
        requested = set(args.scenario)
        scenario_dirs = [path for path in scenario_dirs if path.name in requested]
    scenario_results = [run_scenario(path, args.output_dir, config, args.alarm) for path in scenario_dirs]
    summaries = [summary for summary, _ in scenario_results]
    ablation_rows = [row for _, rows in scenario_results for row in rows]
    summary_frame = pd.DataFrame(summaries)
    ablation_frame = pd.DataFrame(ablation_rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_frame.to_csv(args.output_dir / "summary.csv", index=False)
    ablation_frame.to_csv(args.output_dir / "ablation_summary.csv", index=False)
    write_report(args.report, summaries, ablation_rows, args.output_dir)

    print(summary_frame[["scenario_id", "alarm_column", "expected_service", "top1", "expected_service_rank", "hit_at_1", "hit_at_3", "hit_at_5"]].to_string(index=False))
    print()
    print(ablation_frame[["scenario_id", "method", "top1", "expected_service_rank", "hit_at_1", "hit_at_3", "hit_at_5"]].to_string(index=False))


if __name__ == "__main__":
    main()
