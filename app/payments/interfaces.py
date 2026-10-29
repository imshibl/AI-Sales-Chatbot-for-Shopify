from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PaymentProvider(ABC):
    @abstractmethod
    def create_payment_link(self, order: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_payment_status(self, payment_reference: str) -> str:
        raise NotImplementedError

    def simulate_success(self, payment_reference: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def simulate_failure(self, payment_reference: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def reset(self, payment_reference: str) -> str:
        raise NotImplementedError
