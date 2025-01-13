from collections.abc import Iterable, Sequence

from cognite.client import data_modeling as dm
from cognite.client.exceptions import CogniteAPIError
from cognite.client.utils.useful_types import SequenceNotStr
from rdflib import Namespace, URIRef

from cognite.neat._client import NeatClient
from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._issues import IssueList, NeatIssue, catch_warnings
from cognite.neat._issues.warnings import CDFAuthWarning, ResourceNotFoundWarning, ResourceRetrievalWarning
from cognite.neat._rules.importers import DMSImporter
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.transformers import DMSToInformation, VerifyDMSRules
from cognite.neat._shared import Triple

from ._base import KnowledgeGraphExtractor
from ._dms import DMSExtractor


class DMSGraphExtractor(KnowledgeGraphExtractor):
    def __init__(
        self,
        data_model: dm.DataModel[dm.View],
        client: NeatClient,
        namespace: Namespace = DEFAULT_NAMESPACE,
        issues: Sequence[NeatIssue] | None = None,
        instance_space: str | SequenceNotStr[str] | None = None,
    ) -> None:
        self._client = client
        self._data_model = data_model
        self._namespace = namespace or DEFAULT_NAMESPACE
        self._issues = IssueList(issues)
        self._instance_space = instance_space

        self._views: list[dm.View] | None = None
        self._information_rules: InformationRules | None = None
        self._dms_rules: DMSRules | None = None

    @classmethod
    def from_data_model_id(
        cls,
        data_model_id: dm.DataModelIdentifier,
        client: NeatClient,
        namespace: Namespace = DEFAULT_NAMESPACE,
        instance_space: str | SequenceNotStr[str] | None = None,
    ) -> "DMSGraphExtractor":
        issues: list[NeatIssue] = []
        try:
            data_model = client.data_modeling.data_models.retrieve(data_model_id, inline_views=True)
        except CogniteAPIError as e:
            issues.append(CDFAuthWarning("retrieving data model", str(e)))
            return cls(
                cls._create_empty_model(dm.DataModelId.load(data_model_id)), client, namespace, issues, instance_space
            )
        if not data_model:
            issues.append(ResourceRetrievalWarning(frozenset({data_model_id}), "data model"))
            return cls(
                cls._create_empty_model(dm.DataModelId.load(data_model_id)), client, namespace, issues, instance_space
            )
        return cls(data_model.latest_version(), client, namespace, issues, instance_space)

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

    @property
    def _model_views(self) -> list[dm.View]:
        if self._views is None:
            self._views = self._get_views()
        return self._views

    @property
    def description(self) -> str:
        return "Extracts a data model with nodes and edges."

    @property
    def source_uri(self) -> URIRef:
        space, external_id, version = self._data_model.as_id().as_tuple()
        return DEFAULT_NAMESPACE[f"{self._client.config.project}/{space}/{external_id}/{version}"]

    def extract(self) -> Iterable[Triple]:
        """Extracts the knowledge graph from the data model."""
        views = self._model_views
        yield from DMSExtractor.from_views(
            self._client,
            views,
            overwrite_namespace=self._namespace,
            instance_space=self._instance_space,
        ).extract()

    def _get_views(self) -> list[dm.View]:
        view_by_id: dict[dm.ViewId, dm.View] = {}
        if view_ids := [view_id for view_id in self._data_model.views if isinstance(view_id, dm.ViewId)]:
            try:
                # MyPy does not understand the isinstance check above.
                retrieved = self._client.data_modeling.views.retrieve(ids=view_ids)  #  type: ignore[arg-type]
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
        return views

    def get_information_rules(self) -> InformationRules:
        """Returns the information rules that the extractor uses."""
        if self._information_rules is None:
            self._information_rules, self._dms_rules = self._create_rules()
        return self._information_rules

    def get_dms_rules(self) -> DMSRules:
        """Returns the DMS rules that the extractor uses."""
        if self._dms_rules is None:
            self._information_rules, self._dms_rules = self._create_rules()
        return self._dms_rules

    def get_issues(self) -> IssueList:
        """Returns the issues that occurred during the extraction."""
        return self._issues

    def _create_rules(self) -> tuple[InformationRules, DMSRules]:
        # The DMS and Information rules must be created together to link them property.
        importer = DMSImporter.from_data_model(self._client, self._data_model)
        unverified_dms = importer.to_rules()
        with catch_warnings() as issues:
            # Any errors occur will be raised and caught outside the extractor.
            verified_dms = VerifyDMSRules(client=self._client).transform(unverified_dms)
            information_rules = DMSToInformation(self._namespace).transform(verified_dms)
        self._issues.extend(issues)
        return information_rules, verified_dms
