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

    table = pd.DataFrame(  # type: ignore[operator]
        [
            {
                "Exporter": name,
                "Description": globals()[name].__doc__.strip().split("\n")[0] if globals()[name].__doc__ else "Missing",
            }
            for name in __all__
            if name not in ("BaseExporter", "CDFExporter", "GraphExporter")
        ]
    )._repr_html_()

    return (
        "<strong>Exporter</strong> An exporter converts Neat's representation of a data model called <em>Rules</em>"
        f" into a schema/data model for a target format.<br />{table}"
    )
