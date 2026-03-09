from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IGameEnvironment(ABC):
    """Game runtime boundary for periodic host."""

    @abstractmethod
    def is_running(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def launch(self, logger=None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_tutorial_text(self) -> tuple[str, str]:
        raise NotImplementedError

