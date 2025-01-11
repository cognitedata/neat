from collections.abc import Iterable

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import DataModel, DataModelId
from rdflib import Namespace

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._issues import IssueList
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._shared import Triple

from ._base import KnowledgeGraphExtractor


class DMSGraphExtractor(KnowledgeGraphExtractor):
    def __init__(
        self,
        data_model: DataModel,
        client: CogniteClient,
        namespace: Namespace = DEFAULT_NAMESPACE,
        issues: IssueList | None = None,
    ) -> None:
        self._client = client
        self._data_model = data_model
        self._namespace = namespace or DEFAULT_NAMESPACE
        self._issues = issues or IssueList()

    @classmethod
    def from_data_model_id(
        cls, data_model_id: DataModelId, client: CogniteClient, namespace: Namespace = DEFAULT_NAMESPACE
    ) -> "DMSGraphExtractor":
        raise NotImplementedError

    def extract(self) -> Iterable[Triple]:
        """Extracts the knowledge graph from the data model."""

        raise NotImplementedError()

    def get_information_rules(self) -> InformationRules:
        """Returns the information rules that the extractor uses."""
        raise NotImplementedError()

    def get_dms_rules(self) -> DMSRules:
        """Returns the DMS rules that the extractor uses."""
        raise NotImplementedError()

    def get_issues(self) -> IssueList:
        """Returns the issues that occurred during the extraction."""
        return self._issues
