"""Centralized logging configuration. Quiets noisy third-party libraries while keeping our own logs visible."""

import logging
import os
import warnings


def configure_logging(level: str = "INFO") -> None:
    """
    Configure Python logging so our modules log cleanly and third-party libs are quiet.
    Call this once at app startup (main scripts, orchestrator demo, API main, etc.).
    """
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

    warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")
    warnings.filterwarnings("ignore", category=FutureWarning)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(handler)

    noisy_loggers = [
        "httpx",
        "httpcore",
        "urllib3",
        "sentence_transformers",
        "sentence_transformers.SentenceTransformer",
        "transformers",
        "transformers.modeling_utils",
        "chromadb",
        "chromadb.telemetry",
        "google_genai",
        "google.genai",
        "langchain",
        "langsmith",
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)
