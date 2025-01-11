from collections.abc import Iterable, Sequence

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.exceptions import CogniteAPIError
from cognite.client.utils.useful_types import SequenceNotStr
from rdflib import Namespace

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._issues import IssueList, NeatIssue
from cognite.neat._issues.warnings import CDFAuthWarning, ResourceNotFoundWarning, ResourceRetrievalWarning
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._shared import Triple

from ._base import KnowledgeGraphExtractor
from ._dms import DMSExtractor


class DMSGraphExtractor(KnowledgeGraphExtractor):
    def __init__(
        self,
        data_model: dm.DataModel,
        client: CogniteClient,
        namespace: Namespace = DEFAULT_NAMESPACE,
        issues: Sequence[NeatIssue] | None = None,
        instance_space: str | SequenceNotStr[str] | None = None,
    ) -> None:
        self._client = client
        self._data_model = data_model
        self._namespace = namespace or DEFAULT_NAMESPACE
        self._issues = IssueList(issues)
        self._instance_space = instance_space

    @classmethod
    def from_data_model_id(
        cls, data_model_id: dm.DataModelId, client: CogniteClient, namespace: Namespace = DEFAULT_NAMESPACE
    ) -> "DMSGraphExtractor":
        issues: list[NeatIssue] = []
        try:
            data_model = client.data_modeling.data_models.retrieve(data_model_id)
        except CogniteAPIError as e:
            issues.append(CDFAuthWarning("retrieving data model", str(e)))
            return cls(cls._create_empty_model(data_model_id), client, namespace, issues)
        if not data_model:
            issues.append(ResourceRetrievalWarning(frozenset({data_model_id}), "data model"))
            return cls(cls._create_empty_model(data_model_id), client, namespace, issues)
        return cls(data_model.latest_version(), client, namespace, issues)

    @classmethod
    def _create_empty_model(cls, data_model_id: dm.DataModelId) -> dm.DataModel:
        return dm.DataModel(
            data_model_id.space,
            data_model_id.external_id,
            data_model_id.version or "MISSING",
            is_global=False,
            last_updated_time=0,
            created_time=0,
            description=None,
            name=None,
            views=[],
        )

    def extract(self) -> Iterable[Triple]:
        """Extracts the knowledge graph from the data model."""
        view_by_id: dict[dm.ViewId, dm.View] = {}
        if view_ids := [view_id for view_id in self._data_model.views if isinstance(view_id, dm.ViewId)]:
            try:
                retrieved = self._client.data_modeling.views.retrieve(view_ids)
            except CogniteAPIError as e:
                self._issues.append(CDFAuthWarning("retrieving views", str(e)))
            else:
                view_by_id.update({view.as_id(): view for view in retrieved})
        views: list[dm.View] = []
        data_model_id = self._data_model.as_id()
        for dm_view in self._data_model.views:
            if isinstance(dm_view, dm.View):
                views.append(dm_view)
            elif isinstance(dm_view, dm.ViewId):
                if view := view_by_id.get(dm_view):
                    views.append(view)
                else:
                    self._issues.append(ResourceNotFoundWarning(dm_view, "view", data_model_id, "data model"))
        yield from DMSExtractor.from_views(
            self._client,
            views,
            overwrite_namespace=self._namespace,
            instance_space=self._instance_space,
        ).extract()

    def get_information_rules(self) -> InformationRules:
        """Returns the information rules that the extractor uses."""
        raise NotImplementedError()

    def get_dms_rules(self) -> DMSRules:
        """Returns the DMS rules that the extractor uses."""
        raise NotImplementedError()

    def get_issues(self) -> IssueList:
        """Returns the issues that occurred during the extraction."""
        return self._issues
