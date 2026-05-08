from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: Optional[str] = None, **kwargs) -> str: ...
