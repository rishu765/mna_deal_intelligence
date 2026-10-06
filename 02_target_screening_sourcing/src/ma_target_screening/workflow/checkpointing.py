"""Checkpoint serialization for the local, trusted-process M6 default."""

from __future__ import annotations

import pickle
from typing import Any


class TrustedLocalSerializer:
    """Preserve immutable domain models in an in-process checkpoint store.

    Pickle must only read bytes written by this trusted application process. A
    deployment using a durable or shared store should inject a checkpointer with
    an appropriately secured, deployment-specific serializer.
    """

    _TYPE = "mats-trusted-local-pickle-v1"

    def dumps_typed(self, obj: Any) -> tuple[str, bytes]:
        return self._TYPE, pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)

    def loads_typed(self, data: tuple[str, bytes]) -> Any:
        kind, payload = data
        if kind != self._TYPE:
            raise ValueError(f"unsupported local checkpoint payload type: {kind}")
        return pickle.loads(payload)  # noqa: S301 - trusted in-process checkpoint only
