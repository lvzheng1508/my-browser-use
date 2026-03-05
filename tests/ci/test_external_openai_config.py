"""Tests for the ExternalOpenAIConfig model."""

from browser_use.llm.openai.chat import ChatOpenAI
from browser_use.llm.openai.external_config import ExternalOpenAIConfig


def test_official_openai_config():
	"""Test creating config for official OpenAI."""
	config = ExternalOpenAIConfig(
		provider='openai',
		api_key='sk-test-key',
		model='gpt-4o',
	)

	llm = config.to_chat_openai()

	assert isinstance(llm, ChatOpenAI)
	assert llm.model == 'gpt-4o'
	assert llm.api_key == 'sk-test-key'
	assert llm.base_url is None
	# Default behavior for official OpenAI: do not force structured output skipping
	assert llm.dont_force_structured_output is False


def test_openai_compatible_config_default_no_schema():
	"""Test creating config for an OpenAI-compatible provider (defaults to no schema support)."""
	config = ExternalOpenAIConfig(
		provider='openai_compatible',
		api_key='sk-custom-key',
		model='meta-llama/Llama-2-70b-chat-hf',
		base_url='https://api.together.xyz/v1',
	)

	llm = config.to_chat_openai()

	assert isinstance(llm, ChatOpenAI)
	assert llm.model == 'meta-llama/Llama-2-70b-chat-hf'
	assert llm.api_key == 'sk-custom-key'
	assert llm.base_url == 'https://api.together.xyz/v1'
	# Automatically assumes no schema support for compatible providers unless specified
	assert llm.dont_force_structured_output is True


def test_openai_compatible_config_with_schema_support():
	"""Test creating config for an OpenAI-compatible provider that supports JSON schema."""
	config = ExternalOpenAIConfig(
		provider='openai_compatible',
		api_key='test-key',
		model='custom-model',
		base_url='https://custom.endpoint.com/v1',
		supports_json_schema=True,  # Explicitly state schema support
	)

	llm = config.to_chat_openai()

	assert isinstance(llm, ChatOpenAI)
	# Since it supports JSON schema, it shouldn't disable structured output forcing
	assert llm.dont_force_structured_output is False


def test_explicit_dont_force_structured_output():
	"""Test explicit dont_force_structured_output overrides everything."""
	config = ExternalOpenAIConfig(
		provider='openai',
		api_key='test',
		model='gpt-4o',
		dont_force_structured_output=True,
	)

	llm = config.to_chat_openai()
	assert llm.dont_force_structured_output is True
