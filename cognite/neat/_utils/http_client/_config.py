import functools
import platform

from cognite.neat._utils.auxiliary import get_current_neat_version


@functools.lru_cache(maxsize=1)
def get_user_agent() -> str:
    neat_version = f"CogniteNeat/{get_current_neat_version()}"
    python_version = (
        f"{platform.python_implementation()}/{platform.python_version()} "
        f"({platform.python_build()};{platform.python_compiler()})"
    )
    os_version_info = [platform.release(), platform.machine(), platform.architecture()[0]]
    os_version_info = [s for s in os_version_info if s]  # Ignore empty strings
    os_version_info_str = "-".join(os_version_info)
    operating_system = f"{platform.system()}/{os_version_info_str}"

    return f"{neat_version} {python_version} {operating_system}"
