from functools import lru_cache

from openai import AzureOpenAI

from app.core.config import get_settings


@lru_cache
def get_whisper_client() -> AzureOpenAI:
    """AzureOpenAI client configured for the Whisper deployment."""
    settings = get_settings()
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_whisper_endpoint,
        api_version=settings.azure_openai_whisper_api_version,
    )


@lru_cache
def get_gpt_client() -> AzureOpenAI:
    """AzureOpenAI client configured for the GPT deployment."""
    settings = get_settings()
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_gpt_endpoint,
        api_version=settings.azure_openai_gpt_api_version,
    )
