from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProfileName = Literal["safe", "balanced", "max"]


class BudgetProfile(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: ProfileName
    hard_limit: int = Field(gt=0)


class Settings(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    root: Path
    default_profile: ProfileName = "balanced"
    safety_margin: int = Field(default=256, ge=0)


_LIMITS: dict[ProfileName, int] = {"safe": 30_000, "balanced": 18_000, "max": 10_000}


def budget_profile(settings: Settings, name: ProfileName | None = None) -> BudgetProfile:
    selected = name or settings.default_profile
    return BudgetProfile(name=selected, hard_limit=_LIMITS[selected])
