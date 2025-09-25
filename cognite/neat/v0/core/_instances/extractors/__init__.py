from cognite.neat.v0.session.engine._interface import Extractor as EngineExtractor

from ._base import BaseExtractor, KnowledgeGraphExtractor
from ._classic_cdf._assets import AssetsExtractor
from ._classic_cdf._classic import ClassicGraphExtractor
from ._classic_cdf._data_sets import DataSetExtractor
from ._classic_cdf._events import EventsExtractor
from ._classic_cdf._files import FilesExtractor
from ._classic_cdf._labels import LabelsExtractor
from ._classic_cdf._relationships import RelationshipsExtractor
from ._classic_cdf._sequences import SequencesExtractor
from ._classic_cdf._timeseries import TimeSeriesExtractor
from ._dict import DictExtractor
from ._dms import DMSExtractor
from ._dms_graph import DMSGraphExtractor
from ._mock_graph_generator import MockGraphGenerator
from ._raw import RAWExtractor
from ._rdf_file import RdfFileExtractor

__all__ = [
    "AssetsExtractor",
    "BaseExtractor",
    "ClassicGraphExtractor",
    "DMSExtractor",
    "DMSGraphExtractor",
    "DataSetExtractor",
    "DictExtractor",
    "EventsExtractor",
    "FilesExtractor",
    "KnowledgeGraphExtractor",
    "LabelsExtractor",
    "MockGraphGenerator",
    "RAWExtractor",
    "RdfFileExtractor",
    "RelationshipsExtractor",
    "SequencesExtractor",
    "TimeSeriesExtractor",
]


TripleExtractors = (
    AssetsExtractor
    | MockGraphGenerator
    | RelationshipsExtractor
    | TimeSeriesExtractor
    | SequencesExtractor
    | EventsExtractor
    | FilesExtractor
    | LabelsExtractor
    | RdfFileExtractor
    | DMSExtractor
    | ClassicGraphExtractor
    | DataSetExtractor
    | EngineExtractor
    | DMSGraphExtractor
)


def _repr_html_() -> str:
    import pandas as pd

    table = pd.DataFrame(  # type: ignore[operator]
        [
            {
                "Extractor": name,
                "Description": globals()[name].__doc__.strip().split("\n")[0] if globals()[name].__doc__ else "Missing",
            }
            for name in __all__
            if name != "BaseExtractor"
        ]
    )._repr_html_()

    return (
        "<strong>Extractor</strong> An extractor is used to read data from "
        f"a source into Neat's internal triple storage. <br />{table}"
    )
