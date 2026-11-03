"""Per-stage model configuration for the chat pipeline."""

from dataclasses import dataclass, fields

from pydantic_ai.models import Model
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.providers.bedrock import BedrockProvider

from serka.settings import Settings


@dataclass
class StageModels:
	"""One model per model-backed stage. Tests construct this directly with TestModel/FunctionModel."""

	classify: Model
	plan_keyword: Model
	plan_insight: Model
	execute_insight: Model
	synthesize_keyword: Model
	synthesize_insight: Model
	evaluate: Model

	def ids(self) -> dict[str, str]:
		"""Stage name -> model identifier, as reported in RUN_METADATA."""
		return {f.name: getattr(self, f.name).model_name for f in fields(self)}


def build_stage_models(settings: Settings) -> StageModels:
	"""Builds Bedrock models for every stage, all bound explicitly to settings.aws_region."""
	provider = BedrockProvider(region_name=settings.aws_region)

	def model(model_id: str) -> Model:
		return BedrockConverseModel(model_id, provider=provider)

	return StageModels(
		classify=model(settings.models_classify),
		plan_keyword=model(settings.models_plan_keyword),
		plan_insight=model(settings.models_plan_insight),
		execute_insight=model(settings.models_execute_insight),
		synthesize_keyword=model(settings.models_synthesize_keyword),
		synthesize_insight=model(settings.models_synthesize_insight),
		evaluate=model(settings.models_evaluate),
	)
