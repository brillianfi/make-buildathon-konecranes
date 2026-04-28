from functools import lru_cache

from openai import AzureOpenAI

from app.core.config import get_settings


@lru_cache
def get_azure_client() -> AzureOpenAI:
    """Single Azure OpenAI client for both Whisper and GPT deployments."""
    settings = get_settings()
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )
