import os
from decimal import Decimal

from dotenv import load_dotenv

from app.db import connect

load_dotenv()


def estimate_cost(input_tokens: int, output_tokens: int, purpose: str = "vision") -> Decimal:
    """Estimated dollars for one call, using the per-million prices from .env."""
    price_name = "PRICE_EMBED_PER_M" if purpose == "embedding" else "PRICE_INPUT_PER_M"
    price_in = Decimal(os.environ.get(price_name, "0"))
    price_out = Decimal(os.environ.get("PRICE_OUTPUT_PER_M", "0"))
    return (Decimal(input_tokens) * price_in + Decimal(output_tokens) * price_out) / Decimal(1_000_000)


def log_call(*, image_id, purpose, model, input_tokens, output_tokens,
             latency_ms, status, error=None) -> Decimal:
    """Write one row to ai_calls. Uses its own connection so it is saved even if the caller fails."""
    cost = estimate_cost(input_tokens, output_tokens, purpose)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO ai_calls
                (image_id, purpose, model, input_tokens, output_tokens,
                 cost_usd, latency_ms, status, error)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (image_id, purpose, model, input_tokens, output_tokens,
             cost, latency_ms, status, error),
        )
    return cost
