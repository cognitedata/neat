"""This is a script that can be used to profile the time spent in each dependency of the neat.

You use it by importing the profile_dependencies context manager and wrapping the imports of the neat in it.
For example in the __init__.py file of the neat you can do the following:

```python
from scripts.dependency_profiler import profile_dependencies

with profile_dependencies():
    from ._session import NeatSession
from ._utils.auth import get_cognite_client
from ._version import __version__
```

This will print out the total time spent in each dependency of the neat package when importing the NeatSession.
"""
from collections import defaultdict
from pathlib import Path
import contextlib
import sys
import cProfile
import pstats

this_file = Path(__file__).resolve(strict=True)
neat_location = this_file.parent.parent / "cognite" / "neat"

site_packages = Path(sys.executable).parent.parent / "Lib" / "site-packages"
builtin_path = Path(sys.base_prefix) / "lib"


@contextlib.contextmanager
def profile_dependencies() -> None:
    pr = cProfile.Profile()
    pr.enable()
    yield
    pr.disable()
    sortby = "cumulative"
    ps = pstats.Stats(pr).sort_stats(sortby)
    dependency_times = defaultdict(float)
    for func, (cc, nc, tt, ct, callers) in ps.stats.items():
        filepath = Path(func[0])
        if filepath == Path("~"):
            module_name = "~"
        elif filepath.is_relative_to(neat_location):
            module_name = "neat"
        elif filepath.is_relative_to(site_packages):
            module_name = filepath.relative_to(site_packages).parts[0]
        elif filepath.is_relative_to(builtin_path):
            module_name = filepath.relative_to(builtin_path).parts[0]
        elif func[0].startswith("<") and func[0].endswith(">"):
            module_name = func[0][1:-1]
        elif "PyCharm" in func[0]:
            module_name = "PyCharm"
        elif filepath == Path("."):
            module_name = "."
        elif filepath.is_relative_to(this_file):
            continue
        else:
            raise FileNotFoundError(filepath)
        dependency_times[module_name] += tt

    total = ps.total_tt
    print(f"Profiling results (total time spent {total:.4f} seconds):")
    for module, time_spent in sorted(dependency_times.items(), key=lambda x: x[1], reverse=True):
        print(f"Total time spent in {module}: {time_spent:.4f} seconds ({time_spent / total:.2%})")
