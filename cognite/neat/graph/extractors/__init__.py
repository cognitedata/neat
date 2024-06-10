from ._classic_cdf._assets import AssetsExtractor
from ._classic_cdf._events import EventsExtractor
from ._classic_cdf._files import FilesExtractor
from ._classic_cdf._labels import LabelsExtractor
from ._classic_cdf._relationships import RelationshipsExtractor
from ._classic_cdf._sequences import SequencesExtractor
from ._classic_cdf._timeseries import TimeSeriesExtractor
from ._mock_graph_generator import MockGraphGenerator
from ._rdf_file import RdfFileExtractor

__all__ = [
    "AssetsExtractor",
    "MockGraphGenerator",
    "RelationshipsExtractor",
    "TimeSeriesExtractor",
    "SequencesExtractor",
    "EventsExtractor",
    "FilesExtractor",
    "LabelsExtractor",
    "RdfFileExtractor",
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
)
