import numpy as np
import pytest
from ml.metrics import choose_threshold, evaluate


def test_known_curve_confusion_and_threshold():
    labels, scores = [0, 1, 0, 1], [.1, .9, .8, .2]
    threshold = choose_threshold(labels, scores)
    assert threshold == .2
    result = evaluate(labels, scores, threshold)
    assert result["confusion"] == {"tn": 1, "fp": 1, "fn": 0, "tp": 2}
    assert result["pr_auc"] == pytest.approx(19/24)
    assert result["average_precision"] == pytest.approx(5/6)
    assert result["roc_auc"] == .75
    assert result["f1"] == .8
    assert result["brier"] == pytest.approx(.325)


def test_reliability_includes_score_one_and_no_empty_bin_rate():
    result = evaluate([0, 1], [0., 1.], .5)
    assert result["reliability"][-1]["n"] == 1
    assert result["reliability"][1]["observed_rate"] is None
    with pytest.raises(ValueError):
        evaluate([0, 1], [np.nan, .2], .5)

