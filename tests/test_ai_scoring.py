from backend.ai.schemas import ProviderSignals
from backend.ai.scoring import score_importance


def test_score_importance_bounds_and_python_calculation():
    low = ProviderSignals(summary="A. B.", reason="r", urgency="low", impact="low", novelty="low")
    high = ProviderSignals(summary="A. B.", reason="r", urgency="high", impact="high", novelty="high")
    assert score_importance(low) == 1
    assert score_importance(high) == 10
    mid = ProviderSignals(summary="A. B.", reason="r", urgency="medium", impact="high", novelty="low")
    assert 1 <= score_importance(mid) <= 10
