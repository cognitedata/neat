from cognite.neat._session._usage_analytics._collector import Collector
from cognite.neat._session._wrappers import session_wrapper
from cognite.neat._store import NeatStore


@session_wrapper
class Opt:
    """For the user to decide if they want their usage of neat to be collected or not. We do not collect personal
    information like name etc. only usage.
    """

    def __init__(self, store: NeatStore) -> None:
        self._collector = Collector()
        self._display()
        self._store = store

    def _display(self) -> None:
        if self._collector.is_opted_in or self._collector.is_opted_out:
            return
        print(
            "For Neat to improve, we need to collect usage information. "
            "You acknowledge and agree that neat may collect usage information."
            "To remove this message run 'neat.opt.in_() "
            "or to stop collecting usage information run 'neat.opt.out()'."
        )

    def in_(self) -> None:
        """Consent to collection of neat user insights."""
        self._collector.enable()
        print("You have successfully opted in to data collection.")

    def out(self) -> None:
        """Opt out of allowing usage of neat to be collected from current user."""
        self._collector.disable()
        print("You have successfully opted out of data collection.")
