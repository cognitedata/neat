import importlib.util
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .env_vars import AVAILABLE_LOGIN_FLOWS, AVAILABLE_PROVIDERS, LoginFlow, Provider, create_env_file_content


class InteractiveFlow(ABC):
    def __init__(self, env_path: Path):
        self.env_path = env_path

    @abstractmethod
    def run(self) -> None: ...

    def create_env_file(self, provider: Provider, login_flow: LoginFlow) -> None:
        env_content = create_env_file_content(provider, login_flow)
        self.env_path.write_text(env_content, encoding="utf-8", newline="\n")


def get_interactive_flow(env_file_path: Path) -> InteractiveFlow:
    try:
        importlib.util.find_spec("IPython")
        importlib.util.find_spec("ipywidgets")
        if not _is_in_notebook():
            return NoDependencyFlow(env_file_path)
        return NotebookFlow(env_file_path)
    except ImportError:
        return NoDependencyFlow(env_file_path)


def _is_in_notebook() -> bool:
    try:
        from IPython import get_ipython

        if "IPKernelApp" not in get_ipython().config:
            return False
    except ImportError:
        return False
    except AttributeError:
        return False
    return True


class NoDependencyFlow(InteractiveFlow):
    def run(self) -> None:
        if not self.should_create_env_file():
            return None
        provider = self.provider()
        login_flow: LoginFlow
        if provider != "cdf":
            login_flow = self.login_flow()
        else:
            login_flow = "client_credentials"
        self.create_env_file(provider, login_flow)
        print(f"Created environment file at {self.env_path!r}.")
        return None

    def should_create_env_file(self) -> bool:
        env_file_name = self.env_path.name
        answer = input(
            f"Would you like to create a new {env_file_name!r} file with the required environment variables? [y/N]: "
        )
        return answer.strip().lower() == "y"

    @classmethod
    def provider(cls) -> Provider:
        index = cls._prompt_choice(AVAILABLE_PROVIDERS, "Select provider:")
        return AVAILABLE_PROVIDERS[index]

    @classmethod
    def login_flow(cls) -> LoginFlow:
        index = cls._prompt_choice(AVAILABLE_LOGIN_FLOWS, "Select login flow:")
        return AVAILABLE_LOGIN_FLOWS[index]

    @classmethod
    def _prompt_choice(cls, options: tuple[str, ...], prompt: str) -> int:
        for i, option in enumerate(options, start=1):
            print(f"{i}. {option}")
        question = f"{prompt} [1-{len(options)}]: "
        while True:
            answer = input(question)
            if answer.isdigit():
                index = int(answer)
                if 1 <= index <= len(options):
                    return index - 1
            print(f"Invalid input. Please enter a number between 1 and {len(options)}.")


class NotebookFlow(InteractiveFlow):
    def __init__(self, env_path: Path):
        super().__init__(env_path)
        import ipywidgets as widgets  # type: ignore[import-untyped]
        from IPython.display import display

        self._widgets = widgets
        self._display = display

    def run(self) -> None:
        dropdown_providers = self._widgets.Dropdown(
            options=list(AVAILABLE_PROVIDERS),
            value=AVAILABLE_PROVIDERS[0],
            description="Provider:",
        )
        dropdown_login_flows = self._widgets.Dropdown(
            options=list(AVAILABLE_LOGIN_FLOWS),
            value=AVAILABLE_LOGIN_FLOWS[0],
            description="Login Flow:",
        )
        confirm_button = self._widgets.Button(description="Create template .env file", button_style="primary")
        dropdowns = self._widgets.HBox([dropdown_providers, dropdown_login_flows])
        output = self._widgets.Output()
        container = self._widgets.VBox([dropdowns, confirm_button, output])

        self._display(container)

        def on_confirm_clicked(b: Any) -> None:
            with output:
                provider = dropdown_providers.value
                login_flow = dropdown_login_flows.value
                if provider == "cdf" and login_flow != "client_credentials":
                    print(
                        "Warning: 'cdf' provider only supports 'client_credentials' login flow. Overriding selection."
                    )
                    login_flow = "client_credentials"
                is_existing = self.env_path.exists()
                self.create_env_file(provider, login_flow)
                if is_existing:
                    print(f"Overwrote existing environment file at {self.env_path!r}.")
                else:
                    print(f"Created environment file at {self.env_path!r}.")

        confirm_button.on_click(on_confirm_clicked)
