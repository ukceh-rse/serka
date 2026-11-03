from dataclasses import fields, replace

from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.models.test import TestModel

from serka.chat.models import StageModels, build_stage_models
from serka.settings import Settings


def _settings() -> Settings:
	return Settings(_env_file=None)  # type: ignore[call-arg]


def test_every_stage_model_targets_eu_west_2() -> None:
	models = build_stage_models(_settings())
	for f in fields(models):
		model = getattr(models, f.name)
		assert isinstance(model, BedrockConverseModel)
		assert model.client.meta.region_name == "eu-west-2"


def test_ids_reflect_settings() -> None:
	settings = _settings()
	ids = build_stage_models(settings).ids()
	assert ids["classify"] == settings.models_classify
	assert ids["evaluate"] == settings.models_evaluate
	assert len(ids) == 7


def test_stage_can_be_substituted_with_test_model() -> None:
	test_model = TestModel()
	models = replace(build_stage_models(_settings()), evaluate=test_model)
	assert models.evaluate is test_model
	assert isinstance(models.classify, BedrockConverseModel)


def test_all_stages_can_be_test_models() -> None:
	models = StageModels(**{f.name: TestModel() for f in fields(StageModels)})
	assert set(models.ids().values()) == {"test"}
