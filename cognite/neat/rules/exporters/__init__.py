from ._base import BaseExporter, CDFExporter
from ._rules2dms import DMSExporter
from ._rules2excel import ExcelExporter
from ._rules2ontology import GraphExporter, OWLExporter, SemanticDataModelExporter, SHACLExporter
from ._rules2yaml import YAMLExporter

__all__ = [
    "BaseExporter",
    "DMSExporter",
    "CDFExporter",
    "SemanticDataModelExporter",
    "OWLExporter",
    "GraphExporter",
    "SHACLExporter",
    "ExcelExporter",
    "YAMLExporter",
]


def _repr_html_() -> str:
    import pandas as pd

    return pd.DataFrame(  # type: ignore[operator]
        [
            {
                "Exporter": name,
                "Description": globals()[name].__doc__.strip().split("\n")[0] if globals()[name].__doc__ else "Missing",
            }
            for name in __all__
            if name not in ("BaseExporter", "CDFExporter")
        ]
    )._repr_html_()
