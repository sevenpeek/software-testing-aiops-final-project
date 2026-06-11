import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from usad_numpy import Standardizer, USADNumpy, make_windows


def draw_line_plot(path: Path, values: np.ndarray, labels: np.ndarray, threshold: float, title: str) -> None:
    width, height = 1200, 520
    margin = 64
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((margin, 24), title, fill=(20, 35, 55), font=font)

    ymin, ymax = float(values.min()), float(max(values.max(), threshold))
    pad = (ymax - ymin) * 0.08 + 1e-9
    ymin -= pad
    ymax += pad

    def xy(i: int, y: float) -> tuple[float, float]:
        x = margin + i * (width - 2 * margin) / max(1, len(values) - 1)
        yy = height - margin - (y - ymin) * (height - 2 * margin) / (ymax - ymin)
        return x, yy

    for i, label in enumerate(labels):
        if label:
            x, _ = xy(i, ymin)
            draw.rectangle((x - 1, margin, x + 1, height - margin), fill=(255, 230, 230))

    draw.line((margin, height - margin, width - margin, height - margin), fill=(130, 140, 150), width=1)
    draw.line((margin, margin, margin, height - margin), fill=(130, 140, 150), width=1)
    pts = [xy(i, float(v)) for i, v in enumerate(values)]
    draw.line(pts, fill=(32, 96, 180), width=2)
    th = xy(0, threshold)[1]
    draw.line((margin, th, width - margin, th), fill=(210, 65, 65), width=2)
    draw.text((width - margin - 160, th - 18), f"threshold={threshold:.4f}", fill=(170, 40, 40), font=font)
    img.save(path)


def draw_error_bars(path: Path, metric_names: list[str], errors: np.ndarray) -> None:
    width, height = 1100, 540
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((50, 22), "Average reconstruction error by metric", fill=(20, 35, 55), font=font)
    max_err = float(errors.max()) + 1e-9
    x0, y0 = 300, 70
    bar_h = 24
    gap = 16
    for i, (name, err) in enumerate(zip(metric_names, errors)):
        y = y0 + i * (bar_h + gap)
        draw.text((50, y + 4), name[:34], fill=(40, 40, 40), font=font)
        w = int((width - x0 - 90) * float(err) / max_err)
        draw.rectangle((x0, y, x0 + w, y + bar_h), fill=(60, 120, 190))
        draw.text((x0 + w + 8, y + 4), f"{err:.4f}", fill=(40, 40, 40), font=font)
    img.save(path)


def classification_report(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", default="outputs")
    parser.add_argument("--window", type=int, default=12)
    parser.add_argument("--epochs", type=int, default=180)
    parser.add_argument("--train-ratio", type=float, default=0.35)
    parser.add_argument("--title", default="USAD anomaly score on microservice metrics")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input)
    label = df["label"].to_numpy(dtype=int) if "label" in df.columns else np.zeros(len(df), dtype=int)
    metadata_cols = {"timestamp", "label", "sample_index", "fault_active"}
    metric_cols = [c for c in df.columns if c not in metadata_cols]
    values = df[metric_cols].ffill().bfill().to_numpy(dtype=np.float64)

    train_end = int(len(values) * args.train_ratio)
    normal_train = values[:train_end]
    scaler = Standardizer.fit(normal_train)
    scaled = scaler.transform(values)

    windows = make_windows(scaled, args.window)
    window_labels = np.asarray([label[i : i + args.window].max() for i in range(len(windows))])
    train_windows = windows[: max(20, train_end - args.window + 1)]

    latent_dim = max(4, min(24, windows.shape[1] // 3))
    model = USADNumpy(input_dim=windows.shape[1], latent_dim=latent_dim, lr=3e-4)
    history = model.fit(train_windows, epochs=args.epochs)

    scores = model.score(windows)
    threshold = float(np.quantile(model.score(train_windows), 0.995))
    pred = (scores >= threshold).astype(int)
    report = classification_report(window_labels, pred)

    result = pd.DataFrame(
        {
            "index": np.arange(len(scores)),
            "anomaly_score": scores,
            "threshold": threshold,
            "label": window_labels,
            "predicted_anomaly": pred,
        }
    )
    result.to_csv(out_dir / "anomaly_scores.csv", index=False)

    w1, _ = model.reconstruct(windows)
    abs_err = np.abs(windows - w1).reshape(len(windows), args.window, len(metric_cols)).mean(axis=(0, 1))

    draw_line_plot(out_dir / "anomaly_score.png", scores, window_labels, threshold, args.title)
    draw_error_bars(out_dir / "reconstruction_error.png", metric_cols, abs_err)

    summary = [
        "USAD reproduction summary",
        f"input: {args.input}",
        f"rows: {len(df)}",
        f"metrics: {len(metric_cols)}",
        f"window_size: {args.window}",
        f"train_windows: {len(train_windows)}",
        f"epochs: {args.epochs}",
        f"final_train_loss: {history[-1]:.6f}",
        f"threshold: {threshold:.6f}",
        f"precision: {report['precision']:.4f}",
        f"recall: {report['recall']:.4f}",
        f"f1: {report['f1']:.4f}",
        f"tp/fp/fn/tn: {report['tp']}/{report['fp']}/{report['fn']}/{report['tn']}",
        "",
        "top reconstruction-error metrics:",
    ]
    for name, err in sorted(zip(metric_cols, abs_err), key=lambda x: x[1], reverse=True)[:5]:
        summary.append(f"- {name}: {err:.6f}")
    (out_dir / "metrics_summary.txt").write_text("\n".join(summary), encoding="utf-8")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
