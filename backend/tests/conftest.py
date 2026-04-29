import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Must be set before any app module is imported so pydantic-settings can load.
_DUMMY_AZURE: dict[str, str] = {
    "AZURE_OPENAI_API_KEY": "test-key",
    "AZURE_OPENAI_WHISPER_ENDPOINT": "https://test.example.cognitiveservices.azure.com",
    "AZURE_OPENAI_WHISPER_DEPLOYMENT": "whisper-test",
    "AZURE_OPENAI_GPT_ENDPOINT": "https://test.example.cognitiveservices.azure.com",
    "AZURE_OPENAI_GPT_DEPLOYMENT": "gpt-test",
}
for _k, _v in _DUMMY_AZURE.items():
    os.environ.setdefault(_k, _v)

# Import after env vars are set.
from app.api import inspections as _insp_module  # noqa: E402
from app.main import app  # noqa: E402
from app.storage.local import LocalStorage  # noqa: E402


@pytest.fixture()
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    _insp_module._REGISTRY.clear()
    app.dependency_overrides[LocalStorage] = lambda: LocalStorage(tmp_path / "var")
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()
    _insp_module._REGISTRY.clear()
