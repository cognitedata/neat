from ._base import BaseLoader, CDFLoader
from ._rdf2asset import AssetLoader
from ._rdf2dms import DMSLoader

__all__ = ["BaseLoader", "CDFLoader", "DMSLoader", "AssetLoader"]


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

    return (
        "<strong>Loader</strong> A loader writes data from Neat's triple storage into a target system" f"<br />{table}"
    )
