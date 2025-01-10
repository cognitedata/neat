from collections.abc import Iterable

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import DataModelId
from rdflib import Namespace

from cognite.neat._rules.models import DMSRules, InformationRules, DMSInputRules, InformationInputRules
from cognite.neat._rules.models.information import InformationInputMetadata
from cognite.neat._rules.models.dms import DMSInputMetadata
from cognite.neat._shared import Triple

from ._base import KnowledgeGraphExtractor
from ._dms import DMSExtractor

class DMSGraphExtractor(KnowledgeGraphExtractor):
    def __init__(self, dms_rules: DataModel, client: CogniteClient, namespace: Namespace | None = None) -> None:
        self._namespace = namespace
        _ =  self._client.data_modeling.data_models.retrieve(self._data_model_id, inline_views=True).latest_version()
        self._info = InformationInputRules(InformationInputMetadata(
            space=data_model_id.space, external_id=data_model_id.external_id, version=data_model_id.version, creator="Unknown"
        ), [], [])
        self._dms = DMSInputRules(DMSInputMetadata(
            space=data_model_id.space, external_id=data_model_id.external_id, version=data_model_id.version, creator="Unknown",
        ), [], [])

    @classmethod
    def from_data_model_id(cls, data_model_id: DataModelId, client: CogniteClient, namespace: Namespace | None = None) -> "DMSGraphExtractor":
        raise NotImplementedError()

    @classmethod
    def from_data_model


    def extract(self) -> Iterable[Triple]:

        yield from DMSExtractor.from_views(self._client, [view], limit=None).extract()

    def get_information_rules(self) -> InformationRules:
        """Returns the information rules that the extractor uses."""
        return self._info.as_verified_rules()

    def get_dms_rules(self) -> DMSRules:
        """Returns the DMS rules that the extractor uses."""
        return self._dms.as_verified_rules()
