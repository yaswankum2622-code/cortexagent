"""In-memory cost tracking for the FastAPI server. Aggregates tokens/USD per model."""

from threading import Lock
from typing import Any, Dict


MODEL_PRICING = {
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-opus-4-5": (15.00, 75.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 10.00),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
}


class CostTracker:
    """Process-global cost tracker. Thread-safe."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._total_input = 0
        self._total_output = 0
        self._by_model: Dict[str, Dict[str, Any]] = {}
        self._queries = 0

    def record(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record one model call and accumulate its token/price totals."""
        with self._lock:
            self._total_input += input_tokens
            self._total_output += output_tokens
            bucket = self._by_model.setdefault(
                model,
                {"input_tokens": 0, "output_tokens": 0, "usd": 0.0},
            )
            bucket["input_tokens"] += input_tokens
            bucket["output_tokens"] += output_tokens
            in_price, out_price = MODEL_PRICING.get(model, (0.0, 0.0))
            bucket["usd"] += (input_tokens / 1_000_000) * in_price
            bucket["usd"] += (output_tokens / 1_000_000) * out_price

    def record_query(self) -> None:
        """Increment the count of served API research queries."""
        with self._lock:
            self._queries += 1

    def summary(self) -> Dict[str, Any]:
        """Return the current aggregate cost snapshot."""
        with self._lock:
            total_usd = sum(bucket.get("usd", 0.0) for bucket in self._by_model.values())
            return {
                "total_input_tokens": self._total_input,
                "total_output_tokens": self._total_output,
                "estimated_usd": round(total_usd, 4),
                "by_model": {
                    model: {**bucket, "usd": round(bucket["usd"], 4)}
                    for model, bucket in self._by_model.items()
                },
                "queries_served": self._queries,
            }


cost_tracker = CostTracker()
