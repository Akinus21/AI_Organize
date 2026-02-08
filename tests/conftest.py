import sys
import types
import numpy as np
import pytest


@pytest.fixture(autouse=True)
def stub_akinus_modules(monkeypatch):
    """
    Prevent tests from importing the real 'akinus' package,
    which has optional dependencies like newspaper3k.
    """

    # ---- Create fake submodules ----
    fake_ollama = types.ModuleType("akinus.ai.ollama")
    fake_ollama.cosine_similarity = lambda a, b: 1.0
    fake_ollama.embed_with_ollama = lambda *_: np.ones(10)
    
    async def fake_ollama_query(*args, **kwargs):
        return "Docs\nArchive"

    fake_ollama.ollama_query = fake_ollama_query


    fake_ai = types.ModuleType("akinus.ai")
    fake_ai.ollama = fake_ollama

    fake_utils_logger = types.ModuleType("akinus.utils.logger")
    fake_utils_logger.log = lambda *args, **kwargs: None

    fake_app_details = types.ModuleType("akinus.utils.app_details")
    fake_app_details.PROJECT_ROOT = None
    fake_app_details.APP_NAME = "AI_Organize"

    fake_utils = types.ModuleType("akinus.utils")
    fake_utils.logger = fake_utils_logger
    fake_utils.app_details = fake_app_details

    fake_akinus = types.ModuleType("akinus")
    fake_akinus.ai = fake_ai
    fake_akinus.utils = fake_utils

    # ---- Inject into sys.modules ----
    monkeypatch.setitem(sys.modules, "akinus", fake_akinus)
    monkeypatch.setitem(sys.modules, "akinus.ai", fake_ai)
    monkeypatch.setitem(sys.modules, "akinus.ai.ollama", fake_ollama)
    monkeypatch.setitem(sys.modules, "akinus.utils", fake_utils)
    monkeypatch.setitem(sys.modules, "akinus.utils.logger", fake_utils_logger)
    monkeypatch.setitem(sys.modules, "akinus.utils.app_details", fake_app_details)
