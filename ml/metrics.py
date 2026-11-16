"""Full-curve metrics with explicit PR integration and validation-only thresholds."""
import numpy as np
from sklearn.metrics import auc, average_precision_score, precision_recall_curve, roc_auc_score


def validate_arrays(labels, scores):
    labels, scores = np.asarray(labels, dtype=np.int8), np.asarray(scores, dtype=np.float64)
    if labels.ndim != 1 or labels.shape != scores.shape or not len(labels):
        raise ValueError("Expected non-empty aligned one-dimensional labels/scores")
    if not np.isin(labels, [0, 1]).all() or not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError("Invalid binary labels or probabilities")
    if len(np.unique(labels)) != 2:
        raise ValueError("Evaluation needs both outcome classes")
    return labels, scores


def choose_threshold(labels, scores):
    labels, scores = validate_arrays(labels, scores)
    precision, recall, thresholds = precision_recall_curve(labels, scores, drop_intermediate=False)
    f1 = np.divide(2 * precision[:-1] * recall[:-1], precision[:-1] + recall[:-1], out=np.zeros_like(thresholds), where=(precision[:-1] + recall[:-1]) > 0)
    return float(thresholds[np.flatnonzero(f1 == f1.max())[-1]])


def evaluate(labels, scores, threshold, bins=10):
    labels, scores = validate_arrays(labels, scores)
    precision_curve, recall_curve, thresholds = precision_recall_curve(labels, scores, drop_intermediate=False)
    prediction = scores >= threshold
    tp, fp = int(((labels == 1) & prediction).sum()), int(((labels == 0) & prediction).sum())
    fn, tn = int(((labels == 1) & ~prediction).sum()), int(((labels == 0) & ~prediction).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn)
    reliability = []
    bucket = np.minimum((scores * bins).astype(int), bins - 1)
    for index in range(bins):
        mask = bucket == index
        reliability.append({"bin": index, "lower": index / bins, "upper": (index + 1) / bins, "n": int(mask.sum()), "mean_score": float(scores[mask].mean()) if mask.any() else None, "observed_rate": float(labels[mask].mean()) if mask.any() else None})
    # Downsample display points only. Metrics above/below use the complete curve.
    indices = np.unique(np.linspace(0, len(precision_curve)-1, min(301, len(precision_curve))).astype(int))
    return {"n": len(labels), "positives": int(labels.sum()), "prevalence": float(labels.mean()),
            "pr_auc": float(auc(recall_curve, precision_curve)), "average_precision": float(average_precision_score(labels, scores)),
            "roc_auc": float(roc_auc_score(labels, scores)), "precision": precision, "recall": recall,
            "f1": 2*precision*recall/(precision+recall) if precision+recall else 0.0,
            "brier": float(((scores-labels)**2).mean()), "threshold": float(threshold),
            "confusion": {"tn": tn, "fp": fp, "fn": fn, "tp": tp}, "reliability": reliability,
            "pr_curve": [{"recall": float(recall_curve[i]), "precision": float(precision_curve[i])} for i in indices]}
