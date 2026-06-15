"""Runtime settings loaded from environment / .env.

Keeps secrets out of code (PRD §9.4). Missing LLM keys degrade to the
offline provider rather than failing.

學習重點：設定集中在一個檔案，其他模組只拿 Settings 物件，
不用到處直接讀環境變數。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # optional dependency; settings still work via real env vars without it
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is best-effort
    pass


@dataclass(frozen=True)
class Settings:
    # dataclass 欄位的預設值會在建立 Settings() 時被帶入。
    # os.getenv("NAME", "default") 表示：環境變數不存在時用第二個值。
    llm_provider: str = os.getenv("LLM_PROVIDER", "offline")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    # Google Gemini (GOOGLE_API_KEY is the SDK's conventional name; accept either)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    # Ollama (local, OpenAI-compatible endpoint; no API key required)
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "gemma3")
    default_data_source: str = os.getenv("DEFAULT_DATA_SOURCE", "yfinance")
    market_index_symbol: str = os.getenv("MARKET_INDEX_SYMBOL", "^TWII")
    db_path: str = os.getenv("DB_PATH", "backtesting_copilot.sqlite")

    # Risk-engine defaults (PRD §5.6)
    max_cash_usage_rate: float = float(os.getenv("MAX_CASH_USAGE_RATE", "0.9"))
    max_drawdown_limit: float = float(os.getenv("MAX_DRAWDOWN_LIMIT", "-0.10"))
    market_ma_window: int = int(os.getenv("MARKET_MA_WINDOW", "60"))


def get_settings() -> Settings:
    # 用函式包一層，未來如果要加快取、驗證或測試替身，呼叫端不用改。
    return Settings()
