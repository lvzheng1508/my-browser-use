from typing import Literal

from pydantic import BaseModel, ConfigDict

from browser_use.llm.openai.chat import ChatOpenAI


class ExternalOpenAIConfig(BaseModel):
	"""Unified config for OpenAI and OpenAI-compatible endpoints."""

	model_config = ConfigDict(extra='forbid')

	provider: Literal['openai', 'openai_compatible'] = 'openai'
	api_key: str
	model: str
	base_url: str | None = None  # None = Official OpenAI
	supports_json_schema: bool | None = None  # None = auto infer
	dont_force_structured_output: bool = False

	def to_chat_openai(self) -> ChatOpenAI:
		"""Convert to ChatOpenAI instance.

		For OpenAI-compatible providers, we automatically disable structured output forcing
		unless supports_json_schema is explicitly set to True.
		"""
		# Auto-infer structured output support if not explicitly set
		force_structured = self.dont_force_structured_output
		if self.provider == 'openai_compatible' and self.supports_json_schema is not True:
			# By default, assume compatible providers don't fully support OpenAI's strict structured output
			force_structured = True

		return ChatOpenAI(
			model=self.model,
			api_key=self.api_key,
			base_url=self.base_url,
			dont_force_structured_output=force_structured,
		)
