"""Centralized configuration for CortexAgent. Loads from .env via pydantic-settings."""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All CortexAgent configuration. Loads from .env file in project root."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === LLM Provider Keys ===
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    gemini_api_key: str = Field(..., description="Google Gemini API key")
    groq_api_key: str = Field(
        ...,
        description="Groq API key for Llama/Mixtral inference fallback",
    )

    # === SEC EDGAR Identity ===
    sec_identity: str = Field(
        ...,
        description="Format: 'Name email@example.com' — required by SEC EDGAR",
    )

    # === Per-Agent Model Routing ===
    researcher_model: str = Field(default="gemini-2.5-flash-lite")
    analyst_model: str = Field(default="gemini-2.5-flash-lite")
    writer_model: str = Field(default="claude-haiku-4-5")
    critic_model: str = Field(default="claude-sonnet-4-5")
    selfrag_model: str = Field(default="gemini-2.5-flash-lite")
    ragas_judge_model: str = Field(default="claude-sonnet-4-5")
    groq_primary_model: str = Field(default="llama-3.3-70b-versatile")
    groq_fast_model: str = Field(default="llama-3.1-8b-instant")

    # === Embedding Model (local sentence-transformers) ===
    embedding_model: str = Field(default="all-MiniLM-L6-v2")

    # === Storage ===
    chroma_persist_dir: str = Field(default="./chroma_db")
    postgres_url: str = Field(
        default="postgresql://cortex:cortex@localhost:5432/cortexagent"
    )
    redis_url: str = Field(default="redis://localhost:6379")

    # === RAGAS Quality Thresholds ===
    ragas_faithfulness_threshold: float = Field(default=0.40, ge=0.0, le=1.0)
    ragas_answer_relevance_threshold: float = Field(default=0.20, ge=0.0, le=1.0)
    ragas_context_precision_threshold: float = Field(default=0.25, ge=0.0, le=1.0)

    # === Logging ===
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # === Validators ===
    @field_validator("sec_identity")
    @classmethod
    def sec_identity_must_have_email(cls, v: str) -> str:
        if "@" not in v or " " not in v:
            raise ValueError(
                "SEC_IDENTITY must be in format 'Name email@example.com' "
                "(name space email, with @ in email)"
            )
        return v

    @field_validator("anthropic_api_key", "gemini_api_key", "groq_api_key")
    @classmethod
    def keys_must_not_be_placeholder(cls, v: str) -> str:
        placeholders = ("your_", "xxx", "placeholder", "<", "changeme")
        if any(p in v.lower() for p in placeholders) or len(v) < 20:
            raise ValueError(
                "API key looks like a placeholder. Please set a real key in .env"
            )
        return v

    # === Convenience methods ===
    def model_for_agent(self, agent_name: str) -> str:
        mapping = {
            "researcher": self.researcher_model,
            "analyst": self.analyst_model,
            "writer": self.writer_model,
            "critic": self.critic_model,
            "selfrag": self.selfrag_model,
            "ragas_judge": self.ragas_judge_model,
        }
        if agent_name not in mapping:
            raise ValueError(f"Unknown agent: {agent_name}")
        return mapping[agent_name]

    def provider_for_model(self, model_name: str) -> Literal["anthropic", "gemini", "groq"]:
        if model_name.startswith("claude"):
            return "anthropic"
        if model_name.startswith("gemini"):
            return "gemini"
        if model_name.startswith(("llama", "mixtral", "qwen", "gemma", "deepseek")):
            return "groq"
        raise ValueError(f"Cannot determine provider for model: {model_name}")


# Singleton instance — import this everywhere
settings = Settings()


def validate_settings() -> bool:
    """Run health checks on settings. Returns True if all good. Prints clear errors."""
    print("=" * 60)
    print("CortexAgent Settings Validation")
    print("=" * 60)

    try:
        s = Settings()
    except Exception as e:
        print(f"\n[FAIL] Settings failed to load:\n{e}\n")
        print("Make sure you have a .env file in the project root.")
        print("Copy .env.example to .env and fill in your real API keys.")
        return False

    checks = [
        ("Anthropic API key", bool(s.anthropic_api_key) and len(s.anthropic_api_key) > 20),
        ("Gemini API key", bool(s.gemini_api_key) and len(s.gemini_api_key) > 20),
        ("Groq API key", bool(s.groq_api_key) and len(s.groq_api_key) > 20),
        ("SEC identity", "@" in s.sec_identity and " " in s.sec_identity),
        (
            "Researcher model",
            s.researcher_model.startswith(
                ("claude", "gemini", "llama", "mixtral", "qwen", "gemma", "deepseek")
            ),
        ),
        (
            "Writer model",
            s.writer_model.startswith(
                ("claude", "gemini", "llama", "mixtral", "qwen", "gemma", "deepseek")
            ),
        ),
        ("Embedding model set", bool(s.embedding_model)),
        ("Faithfulness threshold valid", 0 <= s.ragas_faithfulness_threshold <= 1),
    ]

    all_pass = True
    for name, passed in checks:
        symbol = "[OK]" if passed else "[FAIL]"
        print(f"  {symbol} {name}")
        if not passed:
            all_pass = False

    print("\n" + "=" * 60)
    if all_pass:
        print("[SUCCESS] All settings valid. Ready to build.")
        print(f"  Researcher  -> {s.researcher_model}")
        print(f"  Analyst     -> {s.analyst_model}")
        print(f"  Writer      -> {s.writer_model}")
        print(f"  Critic      -> {s.critic_model}")
        print(f"  Self-RAG    -> {s.selfrag_model}")
        print(f"  RAGAS Judge -> {s.ragas_judge_model}")
        print(f"  Embeddings  -> {s.embedding_model} (local)")
    else:
        print("[FAIL] Some settings invalid. Fix .env and retry.")
    print("=" * 60)
    return all_pass


if __name__ == "__main__":
    import sys

    sys.exit(0 if validate_settings() else 1)
