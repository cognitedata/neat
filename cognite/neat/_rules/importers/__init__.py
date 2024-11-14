from ._base import BaseImporter
from ._dms2rules import DMSImporter
from ._dtdl2rules import DTDLImporter
from ._rdf._imf2rules import IMFImporter
from ._rdf._inference2rules import InferenceImporter
from ._rdf._owl2rules import OWLImporter
from ._spreadsheet2rules import ExcelImporter, GoogleSheetImporter
from ._yaml2rules import YAMLImporter

__all__ = [
    "BaseImporter",
    "OWLImporter",
    "IMFImporter",
    "DMSImporter",
    "ExcelImporter",
    "GoogleSheetImporter",
    "DTDLImporter",
    "YAMLImporter",
    "InferenceImporter",
]

RulesImporters = (
    OWLImporter
    | IMFImporter
    | DMSImporter
    | ExcelImporter
    | GoogleSheetImporter
    | DTDLImporter
    | YAMLImporter
    | InferenceImporter
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
        f" and converts it into Neat's representation of a data model called <em>Rules</em>.<br />{table}"
    )
