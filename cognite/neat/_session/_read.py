from typing import Any, Literal, cast

from cognite.client.data_classes.data_modeling import DataModelId, DataModelIdentifier

from cognite.neat._client import NeatClient
from cognite.neat._graph import examples as instances_examples
from cognite.neat._graph import extractors
from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._issues.warnings import MissingCogniteClientWarning
from cognite.neat._rules import catalog, importers
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._utils.reader import NeatReader

from ._state import SessionState
from ._wizard import NeatObjectType, RDFFileType, XMLFileType, object_wizard, rdf_dm_wizard, xml_format_wizard
from .engine import import_engine
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class ReadAPI:
    """Read from a data source into NeatSession graph store."""

    def __init__(self, state: SessionState, client: NeatClient | None, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.cdf = CDFReadAPI(state, client, verbose)
        self.rdf = RDFReadAPI(state, client, verbose)
        self.excel = ExcelReadAPI(state, client, verbose)
        self.csv = CSVReadAPI(state, client, verbose)
        self.yaml = YamlReadAPI(state, client, verbose)
        self.xml = XMLReadAPI(state, client, verbose)


@session_class_wrapper
class BaseReadAPI:
    def __init__(self, state: SessionState, client: NeatClient | None, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self._client = client


@session_class_wrapper
class CDFReadAPI(BaseReadAPI):
    """Reads from CDF Data Models.
    Use the `.data_model()` method to load a CDF Data Model to the knowledge graph.

    """

    def __init__(self, state: SessionState, client: NeatClient | None, verbose: bool) -> None:
        super().__init__(state, client, verbose)
        self.classic = CDFClassicAPI(state, client, verbose)

    @property
    def _get_client(self) -> NeatClient:
        if self._client is None:
            raise NeatValueError("No client provided. Please provide a client to read a data model.")
        return self._client

    def data_model(self, data_model_id: DataModelIdentifier) -> IssueList:
        """Reads a Data Model from CDF to the knowledge graph.

        Args:
            data_model_id: Tuple of strings with the id of a CDF Data Model.
            Notation as follows (<name_of_space>, <name_of_data_model>, <data_model_version>)

        Example:
            ```python
            neat.read.cdf.data_model(("example_data_model_space", "EXAMPLE_DATA_MODEL", "v1"))
            ```
        """

        data_model_id = DataModelId.load(data_model_id)

        if not data_model_id.version:
            raise NeatSessionError("Data model version is required to read a data model.")

        importer = importers.DMSImporter.from_data_model_id(self._get_client, data_model_id)
        return self._state.rule_import(importer)


@session_class_wrapper
class CDFClassicAPI(BaseReadAPI):
    """Reads from the Classic Data Model from CDF.
    Use the `.graph()` method to load CDF core resources to the knowledge graph.

    """

    @property
    def _get_client(self) -> NeatClient:
        if self._client is None:
            raise ValueError("No client provided. Please provide a client to read a data model.")
        return self._client

    def graph(self, root_asset_external_id: str, limit_per_type: int | None = None) -> None:
        """Reads the classic knowledge graph from CDF.

        The Classic Graph consists of the following core resource type.

        !!! note "Classic Node CDF Resources"
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
            limit_per_type: The maximum number of nodes to extract per core node type. If None, all nodes are extracted.

        """
        extractor = extractors.ClassicGraphExtractor(
            self._get_client, root_asset_external_id=root_asset_external_id, limit_per_type=limit_per_type
        )

        self._state.instances.store.write(extractor)
        if self._verbose:
            print(f"Classic Graph {root_asset_external_id} read successfully")


@session_class_wrapper
class ExcelReadAPI(BaseReadAPI):
    """Reads a Neat Excel Rules sheet to the graph store. The rules sheet may stem from an Information architect,
    or a DMS Architect.

    Args:
        io: file path to the Excel sheet

    Example:
        ```python
        neat.read.excel("information_or_dms_rules_sheet.xlsx")
        ```
    """

    def __init__(self, state: SessionState, client: NeatClient | None, verbose: bool) -> None:
        super().__init__(state, client, verbose)
        self.examples = ExcelExampleAPI(state, client, verbose)

    def __call__(self, io: Any) -> IssueList:
        """Reads a Neat Excel Rules sheet to the graph store. The rules sheet may stem from an Information architect,
        or a DMS Architect.

        Args:
            io: file path to the Excel sheet
        """
        reader = NeatReader.create(io)
        path = reader.materialize_path()
        return self._state.rule_import(importers.ExcelImporter(path))


@session_class_wrapper
class ExcelExampleAPI(BaseReadAPI):
    """Used as example for reading some data model into the NeatSession."""

    @property
    def pump_example(self) -> IssueList:
        """Reads the Hello World pump example into the NeatSession."""
        importer: importers.ExcelImporter = importers.ExcelImporter(catalog.hello_world_pump)
        return self._state.rule_import(importer)


@session_class_wrapper
class YamlReadAPI(BaseReadAPI):
    def __call__(self, io: Any, format: Literal["neat", "toolkit"] = "neat") -> IssueList:
        """Reads a yaml with either neat rules, or several toolkit yaml files to import Data Model(s) into NeatSession.

        Args:
            io: File path to the Yaml file in the case of "neat" yaml, or path to a zip folder or directory with several
                Yaml files in the case of "toolkit".
            format: The format of the yaml file(s). Can be either "neat" or "toolkit".

        Example:
            ```python
            neat.read.yaml("path_to_toolkit_yamls")
            ```
        """
        reader = NeatReader.create(io)
        path = reader.materialize_path()
        importer: BaseImporter
        if format == "neat":
            importer = importers.YAMLImporter.from_file(path, source_name=f"{reader!s}")
        elif format == "toolkit":
            dms_importer = importers.DMSImporter.from_path(path, self._client)
            if dms_importer.issue_list.has_warning_type(MissingCogniteClientWarning):
                raise NeatSessionError(
                    "No client provided. You are referencing Cognite containers in your data model, "
                    "NEAT needs a client to lookup the container definitions. "
                    "Please set the client in the session, NeatSession(client=client)."
                )
            importer = dms_importer
        else:
            raise NeatValueError(f"Unsupported YAML format: {format}")
        return self._state.rule_import(importer)


@session_class_wrapper
class CSVReadAPI(BaseReadAPI):
    """Reads a csv that contains a column to use as primary key which will be the unique identifier for the type of
    data you want to read in. Ex. a csv can hold information about assets, and their identifiers are specified in
    a "ASSET_TAG" column.

    Args:
        io: file path or url to the csv
        type: string that specifies what type of data the csv contains. For instance "Asset" or "Equipment"
        primary_key: string name of the column that should be used as the unique identifier for each row of data

    Example:
        ```python
        type_described_in_table = "Turbine"
        column_with_identifier = "UNIQUE_TAG_NAME"
        neat.read.csv("url_or_path_to_csv_file", type=type_described_in_table, primary_key=column_with_identifier)
        ```
    """

    def __call__(self, io: Any, type: str, primary_key: str) -> None:
        engine = import_engine()
        engine.set.format = "csv"
        engine.set.file = NeatReader.create(io).materialize_path()
        engine.set.type = type
        engine.set.primary_key = primary_key
        extractor = engine.create_extractor()

        self._state.instances.store.write(extractor)


@session_class_wrapper
class XMLReadAPI(BaseReadAPI):
    """Reads an XML file that is either of DEXPI or AML format.

    Args:
        io: file path or url to the XML
        format: can be either "dexpi" or "aml" are the currenly supported XML source types.
    """

    def __call__(
        self,
        io: Any,
        format: XMLFileType | None = None,
    ) -> None:
        path = NeatReader.create(io).materialize_path()
        if format is None:
            format = xml_format_wizard()

        if format.lower() == "dexpi":
            return self.dexpi(path)

        if format.lower() == "aml":
            return self.aml(path)

        else:
            raise NeatValueError("Only support XML files of DEXPI format at the moment.")

    def dexpi(self, io: Any) -> None:
        """Reads a DEXPI file into the NeatSession.

        Args:
            io: file path or url to the DEXPI file

        Example:
            ```python
            neat.read.xml.dexpi("url_or_path_to_dexpi_file")
            ```
        """
        path = NeatReader.create(io).materialize_path()
        engine = import_engine()
        engine.set.format = "dexpi"
        engine.set.file = path
        extractor = engine.create_extractor()
        self._state.instances.store.write(extractor)

    def aml(self, io: Any):
        """Reads an AML file into NeatSession.

        Args:
            io: file path or url to the AML file

        Example:
            ```python
            neat.read.xml.aml("url_or_path_to_aml_file")
            ```
        """
        path = NeatReader.create(io).materialize_path()
        engine = import_engine()
        engine.set.format = "aml"
        engine.set.file = path
        extractor = engine.create_extractor()
        self._state.instances.store.write(extractor)


@session_class_wrapper
class RDFReadAPI(BaseReadAPI):
    """Reads an RDF source into NeatSession. Supported sources are "ontology" or "imf".

    Args:
        io: file path or url to the RDF source
    """

    def __init__(self, state: SessionState, client: NeatClient | None, verbose: bool) -> None:
        super().__init__(state, client, verbose)
        self.examples = RDFExamples(state)

    def ontology(self, io: Any) -> IssueList:
        """Reads an OWL ontology source into NeatSession.

        Args:
            io: file path or url to the OWL file

        Example:
            ```python
            neat.read.rdf.ontology("url_or_path_to_owl_source")
            ```
        """
        reader = NeatReader.create(io)
        importer = importers.OWLImporter.from_file(reader.materialize_path(), source_name=f"file {reader!s}")
        return self._state.rule_import(importer)

    def imf(self, io: Any) -> IssueList:
        """Reads IMF Types provided as SHACL shapes into NeatSession.

        Args:
            io: file path or url to the IMF file

        Example:
            ```python
            neat.read.rdf.imf("url_or_path_to_imf_source")
            ```
        """
        reader = NeatReader.create(io)
        importer = importers.IMFImporter.from_file(reader.materialize_path(), source_name=f"file {reader!s}")
        return self._state.rule_import(importer)

    def __call__(
        self,
        io: Any,
        type: NeatObjectType | None = None,
        source: RDFFileType | None = None,
    ) -> IssueList:
        if type is None:
            type = object_wizard()

        type = type.lower()

        if type == "data model":
            source = source or rdf_dm_wizard("What type of data model is the RDF?")
            source = cast(str, source).lower()  # type: ignore

            if source == "ontology":
                return self.ontology(io)
            elif source == "imf types":
                return self.imf(io)
            else:
                raise ValueError(f"Expected ontology, imf types or instances, got {source}")

        elif type == "instances":
            reader = NeatReader.create(io)
            self._state.instances.store.write(extractors.RdfFileExtractor(reader.materialize_path()))
            return IssueList()
        else:
            raise NeatSessionError(f"Expected data model or instances, got {type}")


@session_class_wrapper
class RDFExamples:
    """Used as example for reading some triples into the NeatSession knowledge grapgh."""

    def __init__(self, state: SessionState) -> None:
        self._state = state

    @property
    def nordic44(self) -> IssueList:
        """Reads the Nordic 44 knowledge graph into the NeatSession graph store."""
        self._state.instances.store.write(extractors.RdfFileExtractor(instances_examples.nordic44_knowledge_graph))
        return IssueList()
