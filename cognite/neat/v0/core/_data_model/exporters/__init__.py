from ._base import BaseExporter, CDFExporter
from ._data_model2dms import DMSExporter
from ._data_model2excel import ExcelExporter
from ._data_model2instance_template import InstanceTemplateExporter
from ._data_model2semantic_model import GraphExporter, OWLExporter, SHACLExporter
from ._data_model2yaml import YAMLExporter

__all__ = [
    "BaseExporter",
    "CDFExporter",
    "DMSExporter",
    "ExcelExporter",
    "GraphExporter",
    "InstanceTemplateExporter",
    "OWLExporter",
    "SHACLExporter",
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
        "<strong>Exporter</strong> An exporter converts Neat's representation of a data model"
        f" into a schema/data model for a target format.<br />{table}"
    )
