import importlib.util
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from .env_vars import AVAILABLE_LOGIN_FLOWS, AVAILABLE_PROVIDERS, LoginFlow, Provider

if TYPE_CHECKING:
    from threading import Event


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
    def __init__(self) -> None:
        import ipywidgets as widgets  # type: ignore[import-untyped]
        from IPython.display import display

        self._widgets = widgets
        self._display = display

    def _wait_for_answer(self, event: "Event") -> None:
        from threading import Event as ThreadEvent

        if isinstance(event, ThreadEvent):
            while not event.is_set():
                import time

                time.sleep(0.1)
        else:
            raise TypeError(f"Expected threading.Event, got {type(event)}")

    def create_env_file(self, env_file_name: str) -> bool:
        from threading import Event

        result: bool = False
        done_event = Event()

        label = self._widgets.Label(value=self._create_question(env_file_name))
        yes_button = self._widgets.Button(description="Yes", button_style="success")
        no_button = self._widgets.Button(description="No", button_style="danger")
        buttons = self._widgets.HBox([yes_button, no_button])
        output = self._widgets.VBox([label, buttons])

        def on_yes_click(b: Any) -> None:
            nonlocal result
            result = True
            output.close()
            done_event.set()

        def on_no_click(b: Any) -> None:
            nonlocal result
            result = False
            output.close()
            done_event.set()

        yes_button.on_click(on_yes_click)
        no_button.on_click(on_no_click)
        self._display(output)
        self._wait_for_answer(done_event)
        return result

    def provider(self) -> Provider:
        from threading import Event

        result: Provider | None = None
        done_event = Event()

        label = self._widgets.Label(value=self._provider_question())
        dropdown = self._widgets.Dropdown(
            options=list(AVAILABLE_PROVIDERS),
            value=AVAILABLE_PROVIDERS[0],
            description="Provider:",
        )
        confirm_button = self._widgets.Button(description="Confirm", button_style="primary")
        output = self._widgets.VBox([label, dropdown, confirm_button])

        def on_confirm_click(b: Any) -> None:
            nonlocal result
            result = dropdown.value
            output.close()
            done_event.set()

        confirm_button.on_click(on_confirm_click)
        self._display(output)
        self._wait_for_answer(done_event)
        if result is None:
            raise RuntimeError("No provider selected")
        return result

    def login_flow(self) -> LoginFlow:
        from threading import Event

        result: LoginFlow | None = None
        done_event = Event()

        label = self._widgets.Label(value=self._login_flow_question())
        dropdown = self._widgets.Dropdown(
            options=list(AVAILABLE_LOGIN_FLOWS),
            value=AVAILABLE_LOGIN_FLOWS[0],
            description="Login Flow:",
        )
        confirm_button = self._widgets.Button(description="Confirm", button_style="primary")
        output = self._widgets.VBox([label, dropdown, confirm_button])

        def on_confirm_click(b: Any) -> None:
            nonlocal result
            result = dropdown.value
            output.close()
            done_event.set()

        confirm_button.on_click(on_confirm_click)
        self._display(output)
        self._wait_for_answer(done_event)
        if result is None:
            raise RuntimeError("No login flow selected")
        return result
