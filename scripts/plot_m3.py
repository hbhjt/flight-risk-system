"""Publication-ready static plots of verified real metrics; no model fitting."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    result = json.loads(Path("results/m3/metrics.json").read_text(encoding="utf-8"))
    verification = json.loads(Path("results/m3/verification.json").read_text(encoding="utf-8"))
    assert verification["passed"]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none"})
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.6), layout="constrained")
    colours = {"B0": "#9AA6B2", "B1": "#4178AE", "B2": "#26A7A3", "B3": "#E39433"}
    values = result["test"]
    prevalence = values["B0"]["prevalence"]
    bars = axes[0].bar(list(values), [item["pr_auc"] for item in values.values()], color=list(colours.values()), width=.6)
    for bar, item in zip(bars, values.values()):
        axes[0].text(bar.get_x()+bar.get_width()/2, bar.get_height()+.008, f"{item['pr_auc']:.4f}", ha="center", fontsize=9)
    axes[0].axhline(prevalence, color="#718096", linestyle="--", linewidth=1, label=f"Prevalence {prevalence:.3f}")
    axes[0].set(ylabel="PR-AUC (full-curve trapezoidal area)", ylim=(0, max(.5, max(item["pr_auc"] for item in values.values())+.06)), title="(a) Held-out ranking performance")
    axes[0].legend(frameon=False, loc="upper left", fontsize=8)
    for code, item in values.items():
        curve = item["pr_curve"]
        axes[1].plot([p["recall"] for p in curve], [p["precision"] for p in curve], color=colours[code], linewidth=1.5, label=code)
        valid = [row for row in item["reliability"] if row["n"]]
        axes[2].plot([row["mean_score"] for row in valid], [row["observed_rate"] for row in valid], color=colours[code], linewidth=1.2, marker="o", markersize=3)
    axes[1].axhline(prevalence, color="#718096", linestyle="--", linewidth=1)
    axes[1].set(xlabel="Recall", ylabel="Precision", xlim=(0, 1), ylim=(0, 1), title="(b) Precision–recall curves")
    axes[1].legend(frameon=False, fontsize=8)
    axes[2].plot([0, 1], [0, 1], color="#718096", linestyle="--", linewidth=1)
    axes[2].set(xlabel="Mean estimated score", ylabel="Observed delay rate", xlim=(0, 1), ylim=(0, 1), title="(c) Reliability: 10 equal-width bins")
    for axis in axes:
        axis.grid(axis="y", alpha=.16, linewidth=.6)
        axis.set_axisbelow(True)
    fig.suptitle(f"June 2024 historical backtest · n = {verification['test_rows']:,} · thresholds chosen on May only", fontsize=11)
    output = Path("docs/images")
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / "m3-evaluation.png", dpi=180, facecolor="white")
    fig.savefig(output / "m3-evaluation.svg", facecolor="white")
    plt.close(fig)
    print("Saved verified M3 scientific plots (PNG and SVG)")


if __name__ == "__main__":
    main()
