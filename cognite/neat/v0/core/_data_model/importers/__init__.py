from ._base import BaseImporter
from ._dict2data_model import DictImporter
from ._dms2data_model import DMSImporter
from ._graph2data_model import GraphImporter
from ._rdf import InferenceImporter, OWLImporter, SubclassInferenceImporter
from ._spreadsheet2data_model import ExcelImporter

__all__ = [
    "BaseImporter",
    "DMSImporter",
    "DictImporter",
    "ExcelImporter",
    "GraphImporter",
    "InferenceImporter",
    "OWLImporter",
    "SubclassInferenceImporter",
]

DataModelImporters = (
    OWLImporter
    | DMSImporter
    | ExcelImporter
    | DictImporter
    | InferenceImporter
    | SubclassInferenceImporter
    | GraphImporter
)


def _repr_html_() -> str:
    import pandas as pd

    table = pd.DataFrame(  # type: ignore[operator]
        [
            {
                "Importer": name,
                "Description": (
                    globals()[name].__doc__.strip().split("\n")[0] if globals()[name].__doc__ else "Missing"
                ),
            }
            for name in __all__
            if name != "BaseImporter"
        ]
    )._repr_html_()

    return (
        "<strong>Importer</strong> An importer reads data/schema/data model from a source"
        f" and converts it into Neat's representation of a data model.<br />{table}"
    )
