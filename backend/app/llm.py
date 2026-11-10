"""Gemini（Vertex AI）呼び出し。失敗・無効の時は None を返し、呼び出し側が固定文に戻す。"""
from __future__ import annotations

import json
import logging
from typing import Protocol

from . import config

log = logging.getLogger("llm")


class LLM(Protocol):
    def generate_json(self, prompt: str, timeout_ms: int | None = None) -> dict | None: ...


class NullLLM:
    def generate_json(self, prompt: str, timeout_ms: int | None = None) -> dict | None:
        return None


class VertexLLM:
    def __init__(self) -> None:
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(
            vertexai=True,
            project=config.gcp_project() or None,
            location=config.gcp_location(),
            http_options=types.HttpOptions(timeout=config.gemini_timeout_ms()),
        )

    def _config(self, thinking: bool, timeout_ms: int | None = None):
        kw = dict(response_mime_type="application/json", temperature=0.7, max_output_tokens=4096)
        if thinking:
            try:  # 古いSDKなど thinking_level が無い場合は付けない
                kw["thinking_config"] = self._types.ThinkingConfig(thinking_level="low")
            except Exception as e:
                log.warning("thinking_config unavailable: %s %s", type(e).__name__, str(e)[:200])
        if timeout_ms:  # この呼び出しだけ上書き（質問生成は5秒）
            kw["http_options"] = self._types.HttpOptions(timeout=timeout_ms)
        return self._types.GenerateContentConfig(**kw)

    def _call(self, prompt: str, thinking: bool, timeout_ms: int | None = None):
        return self._client.models.generate_content(
            model=config.gemini_model(), contents=prompt, config=self._config(thinking, timeout_ms)
        )

    def generate_json(self, prompt: str, timeout_ms: int | None = None) -> dict | None:
        try:
            try:
                resp = self._call(prompt, True, timeout_ms)
            except Exception as e:
                if "thinking" not in str(e).lower():
                    raise
                log.warning("gemini retry without thinking_config: %s", str(e)[:200])
                resp = self._call(prompt, False, timeout_ms)
            data = json.loads(resp.text)
            return data if isinstance(data, dict) else None
        except Exception as e:  # 通信・認証・JSON不正など。体験は止めない
            log.warning("gemini failed: %s %s", type(e).__name__, str(e)[:200])
            return None


_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = VertexLLM() if config.gemini_enabled() else NullLLM()
    return _llm


def set_llm(x: LLM | None) -> None:  # テスト用
    global _llm
    _llm = x
