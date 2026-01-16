"""Baseline purple agent for DeepMind Control Suite evaluation.

This agent is designed to be evaluated by the green DMC evaluator agent.
It responds to JSON messages of the form:

  {"kind": "dmc_init", ...}
  {"kind": "dmc_step", "observation": ..., "action_spec": {...}, ...}

On each dmc_step it returns a JSON string:

  {"action": [...]}

where the action matches the action_spec shape.

Implementation goal: be minimal, robust, and deterministic.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from typing import Any

from a2a.server.tasks import TaskUpdater
from a2a.types import Message
from a2a.utils import get_message_text, new_agent_text_message


def _safe_json_loads(text: str) -> Any:
    """Parse JSON, forgiving common code-fence wrappers."""
    s = (text or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
        lines = s.splitlines()
        # Remove optional language label.
        if lines and lines[0].strip().isalpha():
            s = "\n".join(lines[1:])
    return json.loads(s)


def _get_nested(x: Any, path: list[int]) -> Any:
    """Best-effort index into nested lists/tuples; return None on mismatch."""
    cur = x
    for i in path:
        if isinstance(cur, (list, tuple)) and 0 <= i < len(cur):
            cur = cur[i]
        else:
            return None
    return cur


@dataclass
class ActionSpec:
    shape: list[int]
    minimum: Any | None = None
    maximum: Any | None = None

    @staticmethod
    def from_payload(d: Any) -> "ActionSpec":
        if not isinstance(d, dict):
            return ActionSpec(shape=[])
        shape = d.get("shape", [])
        if not isinstance(shape, list) or not all(isinstance(i, int) for i in shape):
            shape = []
        return ActionSpec(
            shape=shape,
            minimum=d.get("minimum"),
            maximum=d.get("maximum"),
        )

    def bounds_for(self, path: list[int]) -> tuple[float | None, float | None]:
        """Return (min, max) for a particular element index path."""
        lo = _get_nested(self.minimum, path)
        hi = _get_nested(self.maximum, path)
        # If nested lookup fails, fall back to scalar bounds if provided.
        if lo is None and isinstance(self.minimum, (int, float)):
            lo = self.minimum
        if hi is None and isinstance(self.maximum, (int, float)):
            hi = self.maximum
        try:
            lo_f = float(lo) if lo is not None and math.isfinite(float(lo)) else None
        except Exception:
            lo_f = None
        try:
            hi_f = float(hi) if hi is not None and math.isfinite(float(hi)) else None
        except Exception:
            hi_f = None
        return lo_f, hi_f


@dataclass
class ContextState:
    rng: random.Random
    spec: ActionSpec
    prev_action: Any | None = None


class Agent:
    """A minimal random-action baseline agent."""

    def __init__(self):
        # Per-conversation state keyed by A2A context_id.
        self._state: dict[str, ContextState] = {}

    def _get_or_create_state(self, message: Message, payload: dict[str, Any]) -> ContextState:
        context_id = message.context_id or "__no_context__"
        st = self._state.get(context_id)
        if st is not None:
            return st

        seed = 0
        # Prefer explicit seed if provided by evaluator.
        if isinstance(payload.get("seed"), int):
            seed = int(payload["seed"])
        # Otherwise derive a stable seed from task string.
        task = payload.get("task")
        if isinstance(task, str):
            seed ^= (hash(task) & 0xFFFFFFFF)

        spec = ActionSpec.from_payload(payload.get("action_spec"))
        st = ContextState(rng=random.Random(seed), spec=spec, prev_action=None)
        self._state[context_id] = st
        return st

    def _sample_action(self, st: ContextState) -> Any:
        """Sample an action with optional low-pass smoothing."""
        shape = st.spec.shape
        if not shape:
            # If spec is missing, return a scalar 0.
            return 0.0

        def rec(dim: int, path: list[int]) -> Any:
            if dim == len(shape):
                lo, hi = st.spec.bounds_for(path)
                if lo is None or hi is None:
                    # Unbounded: small gaussian.
                    return float(st.rng.gauss(0.0, 0.1))
                if hi < lo:
                    lo, hi = hi, lo
                if hi == lo:
                    return float(lo)
                return float(st.rng.uniform(lo, hi))
            return [rec(dim + 1, path + [i]) for i in range(shape[dim])]

        raw = rec(0, [])

        # Smooth with previous action for a slightly more stable baseline.
        if st.prev_action is None:
            st.prev_action = raw
            return raw

        def blend(a: Any, b: Any) -> Any:
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                return 0.9 * float(a) + 0.1 * float(b)
            if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
                return [blend(ai, bi) for ai, bi in zip(a, b)]
            return b

        mixed = blend(st.prev_action, raw)
        st.prev_action = mixed
        return mixed

    async def run(self, message: Message, updater: TaskUpdater) -> None:
        text = get_message_text(message)

        # If input isn't JSON, just respond with a small usage hint.
        try:
            payload = _safe_json_loads(text)
        except Exception:
            await updater.complete(
                new_agent_text_message(
                    "Send JSON messages of kind 'dmc_init' or 'dmc_step'. "
                    "On 'dmc_step' I will respond with JSON {\"action\": [...]}"
                )
            )
            return

        if not isinstance(payload, dict):
            await updater.complete(new_agent_text_message("Input JSON must be an object."))
            return

        kind = payload.get("kind")
        if kind == "dmc_init":
            # Initialize (or reset) per-context state.
            context_id = message.context_id or "__no_context__"
            seed = int(payload.get("seed", 0)) if isinstance(payload.get("seed"), int) else 0
            task = payload.get("task") if isinstance(payload.get("task"), str) else ""
            spec = ActionSpec.from_payload(payload.get("action_spec"))
            self._state[context_id] = ContextState(rng=random.Random(seed ^ (hash(task) & 0xFFFFFFFF)), spec=spec)
            await updater.complete(new_agent_text_message(json.dumps({"ok": True})))
            return

        if kind == "dmc_step":
            st = self._get_or_create_state(message, payload)
            # Update action spec if provided on each step (evaluator includes it).
            if isinstance(payload.get("action_spec"), dict):
                st.spec = ActionSpec.from_payload(payload.get("action_spec"))
            action = self._sample_action(st)
            await updater.complete(new_agent_text_message(json.dumps({"action": action})))
            return

        # Fallback: echo unrecognized JSON.
        await updater.complete(new_agent_text_message(json.dumps({"received": payload})))
