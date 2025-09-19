from ._base import BaseLoader, CDFLoader
from ._rdf2dms import DMSLoader
from ._rdf_to_instance_space import InstanceSpaceLoader

__all__ = ["BaseLoader", "CDFLoader", "DMSLoader", "InstanceSpaceLoader"]


def _repr_html_() -> str:
    import pandas as pd

    table = pd.DataFrame(  # type: ignore[operator]
        [
            {
                "Loader": name,
                "Description": (
                    globals()[name].__doc__.strip().split("\n")[0] if globals()[name].__doc__ else "Missing"
                ),
            }
            for name in __all__
            if name not in ("BaseLoader", "CDFLoader")
        ]
    )._repr_html_()

    return f"<strong>Loader</strong> A loader writes data from Neat's triple storage into a target system<br />{table}"
