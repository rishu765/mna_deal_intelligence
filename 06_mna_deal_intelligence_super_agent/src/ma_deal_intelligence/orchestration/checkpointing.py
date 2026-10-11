"""Trusted process-local serialization for Project 6 milestone checkpoints."""

from __future__ import annotations

import pickle
from typing import Any


class TrustedLocalSerializer:
    """Preserve frozen domain objects inside one trusted application process."""

    _TYPE = "madi-project6-trusted-local-pickle-v1"

    def dumps_typed(self, obj: Any) -> tuple[str, bytes]:
        return self._TYPE, pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)

    def loads_typed(self, data: tuple[str, bytes]) -> Any:
        kind, payload = data
        if kind != self._TYPE:
            raise ValueError(f"unsupported local checkpoint payload type: {kind}")
        return pickle.loads(payload)  # noqa: S301 - trusted same-process checkpoints only
