"""Estimate API-equivalent cost when a harness reports tokens but no dollars."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from quetzal.models import TokenUsage

_PRICING_ENV = "QUETZAL_PRICING"
DEFAULT_PRICING_PATH = Path(__file__).with_name("pricing.json")


@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok: float
    output_per_mtok: float
    cached_input_per_mtok: float | None = None

    def cost_usd(self, usage: TokenUsage) -> float:
        cached = min(usage.cached_input_tokens, usage.input_tokens)
        fresh = usage.input_tokens - cached
        cached_rate = self.input_per_mtok if self.cached_input_per_mtok is None else self.cached_input_per_mtok
        return (
            fresh * self.input_per_mtok + cached * cached_rate + usage.output_tokens * self.output_per_mtok
        ) / 1_000_000


class PriceBook:
    def __init__(self, prices: dict[str, ModelPrice] | None = None, source: Path | None = None):
        self._prices = prices or {}
        self.source = source

    @classmethod
    def load(cls, path: str | Path | None = None) -> PriceBook:
        resolved = cls._resolve_path(path)
        if resolved is None:
            return cls()
        try:
            raw = json.loads(resolved.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read pricing file {resolved}: {exc}") from exc
        models = raw.get("models", raw) if isinstance(raw, dict) else None
        if not isinstance(models, dict):
            raise ValueError(f"Pricing file {resolved} must be a JSON object of model rates.")
        prices: dict[str, ModelPrice] = {}
        for model, rates in models.items():
            if model.startswith("_") or not isinstance(rates, dict):
                continue
            try:
                prices[model] = ModelPrice(
                    input_per_mtok=float(rates["input_per_mtok"]),
                    output_per_mtok=float(rates["output_per_mtok"]),
                    cached_input_per_mtok=(
                        float(rates["cached_input_per_mtok"])
                        if rates.get("cached_input_per_mtok") is not None
                        else None
                    ),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid pricing entry '{model}' in {resolved}: {exc}") from exc
        return cls(prices, resolved)

    def estimate(self, model: str, usage: TokenUsage) -> float | None:
        price = self._match(model)
        return price.cost_usd(usage) if price else None

    def _match(self, model: str) -> ModelPrice | None:
        candidate = model
        while candidate:
            if candidate in self._prices:
                return self._prices[candidate]
            prefixes = [key for key in self._prices if candidate.startswith(key)]
            if prefixes:
                return self._prices[max(prefixes, key=len)]
            _, separator, candidate = candidate.partition("/")
            if not separator:
                break
        return None

    @staticmethod
    def _resolve_path(path: str | Path | None) -> Path | None:
        value = path or os.environ.get(_PRICING_ENV)
        resolved = Path(value).expanduser() if value else DEFAULT_PRICING_PATH
        if value and not resolved.is_file():
            raise ValueError(f"Pricing file not found: {resolved}")
        return resolved if resolved.is_file() else None
