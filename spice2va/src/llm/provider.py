from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel

class LLMProvider(ABC):
    """
    Abstract base class for LLM Providers.
    """
    @abstractmethod
    def generate_structured(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        """
        Generate a structured response adhering to the given Pydantic schema.
        """
        pass
