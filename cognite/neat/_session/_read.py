import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from cognite.client.data_classes.data_modeling import DataModelId, DataModelIdentifier

from cognite.neat._client import NeatClient
from cognite.neat._constants import COGNITE_SPACES
from cognite.neat._graph import examples as instances_examples
from cognite.neat._graph import extractors
from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules import importers
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._store._provenance import Activity as ProvenanceActivity
from cognite.neat._store._provenance import Change
from cognite.neat._store._provenance import Entity as ProvenanceEntity
from cognite.neat._utils.reader import GitHubReader, NeatReader, PathReader

from ._state import SessionState
from ._wizard import NeatObjectType, RDFFileType, object_wizard, rdf_dm_wizard
from .engine import import_engine
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class ReadAPI:
    def __init__(self, state: SessionState, client: NeatClient | None, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.cdf = CDFReadAPI(state, client, verbose)
        self.rdf = RDFReadAPI(state, client, verbose)
        self.excel = ExcelReadAPI(state, client, verbose)
        self.csv = CSVReadAPI(state, client, verbose)
        self.yaml = YamlReadAPI(state, client, verbose)


@session_class_wrapper
class BaseReadAPI:
    def __init__(self, state: SessionState, client: NeatClient | None, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self._client = client

    def _store_rules(self, rules: ReadRules, change: Change) -> IssueList:
        if self._verbose:
            if rules.issues.has_errors:
                print("Data model read failed")
            else:
                print("Data model read passed")

        if rules.rules:
            self._state.data_model.write(rules, change)

        return rules.issues

    def _return_filepath(self, io: Any) -> Path:
        if isinstance(io, str):
            return Path(io)
        elif isinstance(io, Path):
            return io
        else:
            raise NeatValueError(f"Expected str or Path, got {type(io)}")


@session_class_wrapper
class CDFReadAPI(BaseReadAPI):
    def __init__(self, state: SessionState, client: NeatClient | None, verbose: bool) -> None:
        super().__init__(state, client, verbose)
        self.classic = CDFClassicAPI(state, client, verbose)

    @property
    def _get_client(self) -> NeatClient:
        if self._client is None:
            raise NeatValueError("No client provided. Please provide a client to read a data model.")
        return self._client

    def data_model(self, data_model_id: DataModelIdentifier) -> IssueList:
        data_model_id = DataModelId.load(data_model_id)

        if not data_model_id.version:
            raise NeatSessionError("Data model version is required to read a data model.")

        # actual reading of data model
        start = datetime.now(timezone.utc)
        importer = importers.DMSImporter.from_data_model_id(self._get_client, data_model_id)
        rules = importer.to_rules()
        end = datetime.now(timezone.utc)

        # provenance information
        source_entity = ProvenanceEntity.from_data_model_id(data_model_id)
        agent = importer.agent
        activity = ProvenanceActivity(
            was_associated_with=agent,
            ended_at_time=end,
            used=source_entity,
            started_at_time=start,
        )
        target_entity = ProvenanceEntity.from_rules(rules, agent, activity)
        change = Change(
            source_entity=source_entity,
            agent=agent,
            activity=activity,
            target_entity=target_entity,
            description=f"DMS Data model {data_model_id.as_tuple()} read as unverified data model",
        )

        return self._store_rules(rules, change)


@session_class_wrapper
class CDFClassicAPI(BaseReadAPI):
    @property
    def _get_client(self) -> NeatClient:
        if self._client is None:
            raise ValueError("No client provided. Please provide a client to read a data model.")
        return self._client

    def graph(self, root_asset_external_id: str) -> None:
        """Reads the classic knowledge graph from CDF.

        The Classic Graph consists of the following core resource type.

        Classic Node CDF Resources:
         - Assets
         - TimeSeries
         - Sequences
         - Events
         - Files

        All the classic node CDF resources can have one or more connections to one or more assets. This
        will match a direct relationship in the data modeling of CDF.

        In addition, you have relationships between the classic node CDF resources. This matches an edge
        in the data modeling of CDF.

        Finally, you have labels and data sets that to organize the graph. In which data sets have a similar,
        but different, role as a space in data modeling. While labels can be compared to node types in data modeling,
        used to quickly filter and find nodes/edges.

        This extractor will extract the classic CDF graph into Neat starting from either a data set or a root asset.

        It works as follows:

        1. Extract all core nodes (assets, time series, sequences, events, files) filtered by the given data set or
           root asset.
        2. Extract all relationships starting from any of the extracted core nodes.
        3. Extract all core nodes that are targets of the relationships that are not already extracted.
        4. Extract all labels that are connected to the extracted core nodes/relationships.
        5. Extract all data sets that are connected to the extracted core nodes/relationships.

        Args:
            root_asset_external_id: The external id of the root asset

        """
        extractor = extractors.ClassicGraphExtractor(self._get_client, root_asset_external_id=root_asset_external_id)

        self._state.instances.store.write(extractor)
        if self._verbose:
            print(f"Classic Graph {root_asset_external_id} read successfully")


@session_class_wrapper
class ExcelReadAPI(BaseReadAPI):
    def __call__(self, io: Any) -> IssueList:
        reader = NeatReader.create(io)
        start = datetime.now(timezone.utc)
        if not isinstance(reader, PathReader):
            raise NeatValueError("Only file paths are supported for Excel files")
        importer: importers.ExcelImporter = importers.ExcelImporter(reader.path)
        input_rules: ReadRules = importer.to_rules()
        end = datetime.now(timezone.utc)

        if input_rules.rules:
            change = Change.from_rules_activity(
                input_rules,
                importer.agent,
                start,
                end,
                description=f"Excel file {reader!s} read as unverified data model",
            )
            self._store_rules(input_rules, change)
        self._state.data_model.issue_lists.append(input_rules.issues)
        return input_rules.issues


@session_class_wrapper
class YamlReadAPI(BaseReadAPI):
    def __call__(self, io: Any, format: Literal["neat", "toolkit"] = "neat") -> IssueList:
        reader = NeatReader.create(io)
        if not isinstance(reader, PathReader):
            raise NeatValueError("Only file paths are supported for YAML files")
        start = datetime.now(timezone.utc)
        importer: BaseImporter
        if format == "neat":
            importer = importers.YAMLImporter.from_file(reader.path)
        elif format == "toolkit":
            if reader.path.is_file():
                dms_importer = importers.DMSImporter.from_zip_file(reader.path)
            elif reader.path.is_dir():
                dms_importer = importers.DMSImporter.from_directory(reader.path)
            else:
                raise NeatValueError(f"Unsupported YAML format: {format}")
            ref_containers = dms_importer.root_schema.referenced_container()
            if system_container_ids := [
                container_id for container_id in ref_containers if container_id.space in COGNITE_SPACES
            ]:
                if self._client is None:
                    raise NeatSessionError(
                        "No client provided. You are referencing Cognite containers in your data model, "
                        "NEAT needs a client to lookup the container definitions. "
                        "Please set the client in the session, NeatSession(client=client)."
                    )
                system_containers = self._client.loaders.containers.retrieve(system_container_ids)
                dms_importer.update_referenced_containers(system_containers)

            importer = dms_importer
        else:
            raise NeatValueError(f"Unsupported YAML format: {format}")
        input_rules: ReadRules = importer.to_rules()

        end = datetime.now(timezone.utc)

        if input_rules.rules:
            change = Change.from_rules_activity(
                input_rules,
                importer.agent,
                start,
                end,
                description=f"YAML file {reader!s} read as unverified data model",
            )
            self._store_rules(input_rules, change)

        return input_rules.issues


@session_class_wrapper
class CSVReadAPI(BaseReadAPI):
    def __call__(self, io: Any, type: str, primary_key: str) -> None:
        reader = NeatReader.create(io)
        if isinstance(reader, GitHubReader):
            path = Path(tempfile.gettempdir()).resolve() / reader.name
            path.write_text(reader.read_text())
        elif isinstance(reader, PathReader):
            path = reader.path
        else:
            raise NeatValueError("Only file paths are supported for CSV files")
        engine = import_engine()
        engine.set.source = ".csv"
        engine.set.file = path
        engine.set.type = type
        engine.set.primary_key = primary_key
        extractor = engine.create_extractor()

        self._state.instances.store.write(extractor)


@session_class_wrapper
class RDFReadAPI(BaseReadAPI):
    def __init__(self, state: SessionState, client: NeatClient | None, verbose: bool) -> None:
        super().__init__(state, client, verbose)
        self.examples = RDFExamples(state)

    def ontology(self, io: Any) -> IssueList:
        start = datetime.now(timezone.utc)
        reader = NeatReader.create(io)
        if not isinstance(reader, PathReader):
            raise NeatValueError("Only file paths are supported for RDF files")
        importer = importers.OWLImporter.from_file(reader.path)
        input_rules: ReadRules = importer.to_rules()
        end = datetime.now(timezone.utc)

        if input_rules.rules:
            change = Change.from_rules_activity(
                input_rules,
                importer.agent,
                start,
                end,
                description=f"Ontology file {reader!s} read as unverified data model",
            )
            self._store_rules(input_rules, change)

        return input_rules.issues

    def imf(self, io: Any) -> IssueList:
        start = datetime.now(timezone.utc)
        reader = NeatReader.create(io)
        if not isinstance(reader, PathReader):
            raise NeatValueError("Only file paths are supported for RDF files")
        importer = importers.IMFImporter.from_file(reader.path)
        input_rules: ReadRules = importer.to_rules()
        end = datetime.now(timezone.utc)

        if input_rules.rules:
            change = Change.from_rules_activity(
                input_rules,
                importer.agent,
                start,
                end,
                description=f"IMF Types file {reader!s} read as unverified data model",
            )
            self._store_rules(input_rules, change)

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
                return self.ontology(io)
            elif source == "IMF":
                return self.imf(io)
            else:
                raise ValueError(f"Expected ontology, imf or instances, got {source}")

        elif type.lower() == "Instances".lower():
            reader = NeatReader.create(io)
            if not isinstance(reader, PathReader):
                raise NeatValueError("Only file paths are supported for RDF files")

            self._state.instances.store.write(extractors.RdfFileExtractor(reader.path))
            return IssueList()
        else:
            raise NeatSessionError(f"Expected data model or instances, got {type}")


class RDFExamples:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    @property
    def nordic44(self) -> IssueList:
        self._state.instances.store.write(extractors.RdfFileExtractor(instances_examples.nordic44_knowledge_graph))
        return IssueList()
