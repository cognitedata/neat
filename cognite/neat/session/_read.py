from pathlib import Path
from typing import Any

from cognite.client import CogniteClient

from cognite.neat._graph import extractors
from cognite.neat._issues import IssueList
from cognite.neat._rules import importers
from cognite.neat._rules._shared import ReadRules
from cognite.neat.store import NeatGraphStore

from ._state import SessionState
from ._wizard import NeatObjectType, RDFFileType, object_wizard, rdf_dm_wizard


class ReadAPI:
    def __init__(self, state: SessionState, client: CogniteClient | None, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.cdf = CDFReadAPI(state, client)

    def excel(self, io: Any) -> IssueList:
        filepath = self._return_filepath(io)
        input_rules: ReadRules = importers.ExcelImporter(filepath).to_rules()
        self._store_rules(io, input_rules, "Excel")
        return input_rules.issues

    def rdf(
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

    def _inference(self, io: Any) -> IssueList:
        if isinstance(io, NeatGraphStore):
            importer = importers.InferenceImporter.from_graph_store(io)
        else:
            importer = importers.InferenceImporter.from_file(self._return_filepath(io))

        input_rules: ReadRules = importer.to_rules()
        self._store_rules(io, input_rules, "Inference")
        return input_rules.issues

    def _return_filepath(self, io: Any) -> Path:
        if isinstance(io, str):
            return Path(io)
        elif isinstance(io, Path):
            return io
        else:
            raise ValueError(f"Expected str or Path, got {type(io)}")

    def _store_rules(self, io: Any, input_rules: ReadRules, source: str) -> None:
        if input_rules.rules:
            self._state.input_rules.append(input_rules)
            if self._verbose:
                if input_rules.issues.has_errors:
                    print(f"{source} {type(io)} {io} read failed")
                else:
                    print(f"{source} {type(io)} {io} read successfully")


class CDFReadAPI:
    def __init__(self, state: SessionState, client: CogniteClient | None) -> None:
        self._state = state
        self._client = client
