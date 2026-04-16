from abc import ABC, abstractmethod
from typing import Iterable

from prometheus_client import Metric

try:
    from prometheus_client.registry import Collector
except ImportError:
    class _Collector(ABC):
        @abstractmethod
        def collect(self) -> Iterable[Metric]:
            pass

    Collector = _Collector  # type: ignore
