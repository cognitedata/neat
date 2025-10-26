from pyparsing import ABC

from cognite.neat._data_model.exporters._base import DMSExporter
from cognite.neat._data_model.models.dms import RequestSchema


class DMSAPIExporter(DMSExporter[RequestSchema], ABC): ...
