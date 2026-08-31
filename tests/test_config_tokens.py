from pathlib import Path

import pytest
from pydantic import ValidationError

from comptext_conductor_max.config import Settings, budget_profile
from comptext_conductor_max.tokens import estimate_tokens


def test_settings_requires_root():
    with pytest.raises(ValidationError):
        Settings()


def test_budget_profiles_have_required_hard_limits(tmp_path: Path):
    settings = Settings(root=tmp_path)
    assert budget_profile(settings, "safe").hard_limit == 30_000
    assert budget_profile(settings, "balanced").hard_limit == 18_000
    assert budget_profile(settings, "max").hard_limit == 10_000


def test_token_fallback_is_explicitly_estimated():
    count = estimate_tokens("alpha beta gamma")
    assert count.value > 0
    assert count.metric == "estimated_tokens"
    assert count.exact is False
