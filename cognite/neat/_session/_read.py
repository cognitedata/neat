from pathlib import Path
from typing import Any

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import DataModelIdentifier

from cognite.neat._graph import examples as instances_examples
from cognite.neat._graph import extractors
from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules import importers
from cognite.neat._rules._shared import ReadRules

from ._state import SessionState
from ._wizard import NeatObjectType, RDFFileType, object_wizard, rdf_dm_wizard
from .exceptions import intercept_session_exceptions


@intercept_session_exceptions
class ReadAPI:
    def __init__(self, state: SessionState, client: CogniteClient | None, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.cdf = CDFReadAPI(state, client, verbose)
        self.rdf = RDFReadAPI(state, client, verbose)
        self.excel = ExcelReadAPI(state, client, verbose)


@intercept_session_exceptions
class BaseReadAPI:
    def __init__(self, state: SessionState, client: CogniteClient | None, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self._client = client

    def _store_rules(self, io: Any, input_rules: ReadRules, source: str) -> None:
        if input_rules.rules:
            self._state.input_rules.append(input_rules)
            if self._verbose:
                if input_rules.issues.has_errors:
                    print(f"{source} {type(io)} {io} read failed")
                else:
                    print(f"{source} {type(io)} {io} read successfully")

    def _return_filepath(self, io: Any) -> Path:
        if isinstance(io, str):
            return Path(io)
        elif isinstance(io, Path):
            return io
        else:
            raise NeatValueError(f"Expected str or Path, got {type(io)}")


@intercept_session_exceptions
class CDFReadAPI(BaseReadAPI):
    def __init__(self, state: SessionState, client: CogniteClient | None, verbose: bool) -> None:
        super().__init__(state, client, verbose)
        self.classic = CDFClassicAPI(state, client, verbose)

    @property
    def _get_client(self) -> CogniteClient:
        if self._client is None:
            raise NeatValueError("No client provided. Please provide a client to read a data model.")
        return self._client

    def data_model(self, data_model_id: DataModelIdentifier) -> IssueList:
        importer = importers.DMSImporter.from_data_model_id(self._get_client, data_model_id)
        input_rules = importer.to_rules()
        self._store_rules(data_model_id, input_rules, "CDF")
        return input_rules.issues


@intercept_session_exceptions
class CDFClassicAPI(BaseReadAPI):
    @property
    def _get_client(self) -> CogniteClient:
        if self._client is None:
            raise ValueError("No client provided. Please provide a client to read a data model.")
        return self._client

    def assets(self, root_asset_external_id: str) -> None:
        extractor = extractors.AssetsExtractor.from_hierarchy(self._get_client, root_asset_external_id)
        self._state.store.write(extractor)
        if self._verbose:
            print(f"Asset hierarchy {root_asset_external_id} read successfully")


@intercept_session_exceptions
class ExcelReadAPI(BaseReadAPI):
    def __call__(self, io: Any) -> IssueList:
        filepath = self._return_filepath(io)
        input_rules: ReadRules = importers.ExcelImporter(filepath).to_rules()
        self._store_rules(io, input_rules, "Excel")
        return input_rules.issues


@intercept_session_exceptions
class RDFReadAPI(BaseReadAPI):
    def __init__(self, state: SessionState, client: CogniteClient | None, verbose: bool) -> None:
        super().__init__(state, client, verbose)
        self.examples = RDFExamples(state)

    def _ontology(self, io: Any) -> IssueList:
        filepath = self._return_filepath(io)
        input_rules: ReadRules = importers.OWLImporter.from_file(filepath).to_rules()
        self._store_rules(io, input_rules, "Ontology")
        return input_rules.issues

    def _imf(self, io: Any) -> IssueList:
        filepath = self._return_filepath(io)
        input_rules: ReadRules = importers.IMFImporter.from_file(filepath).to_rules()
        self._store_rules(io, input_rules, "IMF Types")
        return input_rules.issues

    def __call__(
        self,
        io: Any,
        type: NeatObjectType | None = None,
        source: RDFFileType | None = None,
    ) -> IssueList:
        if type is None:
            type = object_wizard()

        if type.lower() == "Data Model".lower():
            source = source or rdf_dm_wizard("What type of data model is the RDF?")
            if source == "Ontology":
                return self._ontology(io)
            elif source == "IMF":
                return self._imf(io)
            else:
                raise ValueError(f"Expected ontology, imf or instances, got {source}")

        elif type.lower() == "Instances".lower():
            self._state.store.write(extractors.RdfFileExtractor(self._return_filepath(io)))
            return IssueList()
        else:
            raise ValueError(f"Expected data model or instances, got {type}")


class RDFExamples:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    @property
    def nordic44(self) -> IssueList:
        self._state.store.write(extractors.RdfFileExtractor(instances_examples.nordic44_knowledge_graph))
        return IssueList()
