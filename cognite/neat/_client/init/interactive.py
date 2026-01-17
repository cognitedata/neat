from abc import ABC, abstractmethod

from .env_vars import LoginFlow, Provider


class InteractiveFlow(ABC):
    @abstractmethod
    def create_env_file(self) -> bool: ...

    @abstractmethod
    def provider(self) -> Provider: ...

    @abstractmethod
    def login_flow(self) -> LoginFlow: ...


def get_interactive_flow() -> InteractiveFlow:
    raise NotImplementedError()
