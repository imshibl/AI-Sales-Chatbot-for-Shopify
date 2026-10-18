import pytest

from app.ai.factory import MockProvider
from app.api.v1.chat import service as chat_service


@pytest.fixture(autouse=True)
def use_mock_provider_for_api_tests(monkeypatch):
    monkeypatch.setattr(chat_service, "llm_provider", MockProvider())
    monkeypatch.setattr(chat_service, "use_llm", False)
