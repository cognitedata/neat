import importlib.util
from abc import ABC, abstractmethod

from .env_vars import AVAILABLE_LOGIN_FLOWS, AVAILABLE_PROVIDERS, LoginFlow, Provider


class InteractiveFlow(ABC):
    @staticmethod
    def _create_question(env_file_name: str) -> str:
        return f"Would you like to create a new {env_file_name!r} file with the required environment variables?"

    @staticmethod
    def _provider_question() -> str:
        return "Which provider would you like to use?"

    @staticmethod
    def _login_flow_question() -> str:
        return "Which login flow would you like to use?"

    @abstractmethod
    def create_env_file(self, env_file_name: str) -> bool: ...

    @abstractmethod
    def provider(self) -> Provider: ...

    @abstractmethod
    def login_flow(self) -> LoginFlow: ...


def get_interactive_flow() -> InteractiveFlow:
    try:
        importlib.util.find_spec("IPython")
        importlib.util.find_spec("ipywidgets")

        return NotebookFlow()
    except ImportError:
        return NoDependencyFlow()


class NoDependencyFlow(InteractiveFlow):
    def create_env_file(self, env_file_name: str) -> bool:
        answer = input(f"{self._create_question(env_file_name)} [y/N]: ")
        return answer.strip().lower() == "y"

    def provider(self) -> Provider:
        for i, provider in enumerate(AVAILABLE_PROVIDERS, start=1):
            print(f"{i}. {provider}")
        question = f"{self._provider_question()} [1-{len(AVAILABLE_PROVIDERS)}]: "
        while True:
            answer = input(question)
            if answer.isdigit():
                index = int(answer)
                if 1 <= index <= len(AVAILABLE_PROVIDERS):
                    return AVAILABLE_PROVIDERS[index - 1]
            print(f"Invalid input. Please enter a number between 1 and {len(AVAILABLE_PROVIDERS)}.")

    def login_flow(self) -> LoginFlow:
        for i, flow in enumerate(AVAILABLE_LOGIN_FLOWS, start=1):
            print(f"{i}. {flow}")
        question = f"{self._login_flow_question()} [1-{len(AVAILABLE_LOGIN_FLOWS)}]: "
        while True:
            answer = input(question)
            if answer.isdigit():
                index = int(answer)
                if 1 <= index <= len(AVAILABLE_LOGIN_FLOWS):
                    return AVAILABLE_LOGIN_FLOWS[index - 1]
            print(f"Invalid input. Please enter a number between 1 and {len(AVAILABLE_LOGIN_FLOWS)}.")


class NotebookFlow(InteractiveFlow):
    def create_env_file(self, env_file_name: str) -> bool:
        raise NotImplementedError

    def provider(self) -> Provider:
        raise NotImplementedError

    def login_flow(self) -> LoginFlow:
        raise NotImplementedError
