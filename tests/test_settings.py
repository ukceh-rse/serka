from pathlib import Path

import pytest

from serka.settings import Settings

STAGE_FIELDS = [
	"models_classify",
	"models_plan_keyword",
	"models_plan_insight",
	"models_execute_insight",
	"models_synthesize_keyword",
	"models_synthesize_insight",
	"models_evaluate",
]


def test_region_defaults_to_eu_west_2() -> None:
	assert Settings(_env_file=None).aws_region == "eu-west-2"  # type: ignore[call-arg]


def test_usage_limit_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
	for field in Settings.model_fields:
		monkeypatch.delenv(field.upper(), raising=False)
	settings = Settings(_env_file=None)  # type: ignore[call-arg]
	assert settings.usage_ip_daily_limit == 30
	assert settings.usage_global_daily_limit == 500
	assert settings.usage_insight_daily_limit == 100
	assert settings.trusted_proxy_hops == 0
	assert settings.chat_enabled is False


@pytest.mark.parametrize("field", STAGE_FIELDS)
def test_env_var_overrides_only_its_stage(field: str, monkeypatch: pytest.MonkeyPatch) -> None:
	defaults = Settings(_env_file=None)  # type: ignore[call-arg]
	monkeypatch.setenv(field.upper(), "custom.model-v1:0")
	settings = Settings(_env_file=None)  # type: ignore[call-arg]
	assert getattr(settings, field) == "custom.model-v1:0"
	for other in STAGE_FIELDS:
		if other != field:
			assert getattr(settings, other) == getattr(defaults, other)


def test_env_example_loads(monkeypatch: pytest.MonkeyPatch) -> None:
	for field in Settings.model_fields:
		monkeypatch.delenv(field.upper(), raising=False)
	settings = Settings(_env_file=Path(__file__).parent.parent / ".env.example")  # type: ignore[call-arg]
	assert settings.aws_region == "eu-west-2"
	assert settings.models_classify == "amazon.nova-lite-v1:0"
	assert not hasattr(settings, "models_llm")
