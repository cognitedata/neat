import re
import warnings
from typing import Any, Literal, cast

from cognite.client.data_classes.data_modeling import DataModelId, DataModelIdentifier
from cognite.client.utils.useful_types import SequenceNotStr
from rdflib import URIRef

from cognite.neat.v0.core._client import NeatClient
from cognite.neat.v0.core._constants import (
    CLASSIC_CDF_NAMESPACE,
    NAMED_GRAPH_NAMESPACE,
    get_default_prefixes_and_namespaces,
)
from cognite.neat.v0.core._data_model import catalog, importers
from cognite.neat.v0.core._data_model._constants import SPACE_COMPLIANCE_REGEX
from cognite.neat.v0.core._data_model.importers import BaseImporter
from cognite.neat.v0.core._data_model.models.entities._single_value import ViewEntity
from cognite.neat.v0.core._data_model.transformers import ClassicPrepareCore
from cognite.neat.v0.core._data_model.transformers._converters import (
    ToEnterpriseModel,
    _SubsetEditableCDMPhysicalDataModel,
)
from cognite.neat.v0.core._instances import examples as instances_examples
from cognite.neat.v0.core._instances import extractors
from cognite.neat.v0.core._instances.extractors._classic_cdf._base import InstanceIdPrefix
from cognite.neat.v0.core._instances.transformers import (
    ConvertLiteral,
    LiteralToEntity,
    Transformers,
)
from cognite.neat.v0.core._instances.transformers._prune_graph import (
    AttachPropertyFromTargetToSource,
    PruneDeadEndEdges,
    PruneInstancesOfUnknownType,
    PruneTypes,
)
from cognite.neat.v0.core._issues import IssueList
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._issues.warnings import MissingCogniteClientWarning
from cognite.neat.v0.core._utils.reader import NeatReader
from cognite.neat.v0.session._experimental import ExperimentalFlags

from ._state import SessionState
from ._wizard import NeatObjectType, RDFFileType, XMLFileType, object_wizard, rdf_dm_wizard, xml_format_wizard
from .engine import import_engine
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class ReadAPI:
    """Read from a data source into NeatSession graph store."""

    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.cdf = CDFReadAPI(state, verbose)
        self.rdf = RDFReadAPI(state, verbose)
        self.excel = ExcelReadAPI(state, verbose)
        self.csv = CSVReadAPI(state, verbose)
        self.yaml = YamlReadAPI(state, verbose)
        self.xml = XMLReadAPI(state, verbose)
        self.examples = Examples(state)

    def session(self, io: Any) -> None:
        """Reads a Neat Session from a zip file.

        Args:
            io: file path to the Neat Session

        Example:
            ```python
            neat.read.session("path_to_neat_session")
            ```
        """
        reader = NeatReader.create(io)
        path = reader.materialize_path()

        self._state.instances.store.write(extractors.RdfFileExtractor.from_zip(path))


@session_class_wrapper
class BaseReadAPI:
    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose


@session_class_wrapper
class CDFReadAPI(BaseReadAPI):
    """Reads from CDF Data Models.
    Use the `.data_model()` method to load a CDF Data Model to the knowledge graph.

    """

    def __init__(self, state: SessionState, verbose: bool) -> None:
        super().__init__(state, verbose)
        self.classic = CDFClassicAPI(state, verbose)

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

        self._state._raise_exception_if_condition_not_met(
            "Read data model from CDF",
            empty_data_model_store_required=True,
            client_required=True,
        )

        importer = importers.DMSImporter.from_data_model_id(cast(NeatClient, self._state.client), data_model_id)
        return self._state.data_model_import(importer)

    def core_data_model(self, concepts: str | list[str]) -> IssueList:
        """Subset the data model to the desired concepts.

        Args:
            concepts: The concepts to subset the data model to

        Returns:
            IssueList: A list of issues that occurred during the transformation.

        Example:
            Read the CogniteCore data model and reduce the data model to only the 'CogniteAsset' concept.
            ```python
            neat = NeatSession(CogniteClient())

            neat.subset.data_model.core_data_model(concepts=["CogniteAsset", "CogniteEquipment"])
            ```

        !!! note "Bundle of actions"
            This method is a helper method that bundles the following actions:
            - Imports the latest version of Cognite's Core Data Model (CDM)
            - Makes editable copy of the CDM concepts
            - Subsets the copy to the desired concepts to desired set of concepts
        """

        concepts = concepts if isinstance(concepts, list | set) else [concepts]

        self._state._raise_exception_if_condition_not_met(
            "Subset Core Data Model",
            empty_data_model_store_required=True,
            client_required=True,
        )

        warnings.filterwarnings("default")
        ExperimentalFlags.core_data_model_subsetting.warn()

        cdm_v1 = DataModelId.load(("cdf_cdm", "CogniteCore", "v1"))
        importer: importers.DMSImporter = importers.DMSImporter.from_data_model_id(
            cast(NeatClient, self._state.client), cdm_v1
        )
        issues = self._state.data_model_import(importer)

        if issues.has_errors:
            return issues

        cdm_data_model = self._state.data_model_store.last_verified_data_model

        issues.extend(
            self._state.data_model_transform(
                ToEnterpriseModel(
                    new_model_id=("my_space", "MyCDMSubset", "v1"),
                    org_name="CopyOf",
                    dummy_property="GUID",
                    move_connections=True,
                )
            )
        )

        if issues.has_errors:
            return issues

        issues.extend(
            self._state.data_model_transform(
                _SubsetEditableCDMPhysicalDataModel(
                    views={
                        ViewEntity(
                            space=cdm_v1.space,
                            externalId=concept,
                            version=cast(str, cdm_v1.version),
                        )
                        for concept in concepts
                    }
                )
            )
        )

        if cdm_data_model and not issues.has_errors:
            self._state.last_reference = cdm_data_model

        return issues

    def graph(
        self,
        data_model_id: DataModelIdentifier,
        instance_space: str | SequenceNotStr[str] | None = None,
        skip_cognite_views: bool = True,
    ) -> IssueList:
        """Reads a knowledge graph from Cognite Data Fusion (CDF).

        Args:
            data_model_id: Tuple of strings with the id of a CDF Data Model.
            instance_space: The instance spaces to extract. If None, all instance spaces are extracted.
            skip_cognite_views: If True, all Cognite Views are skipped. For example, if you have the CogniteAsset
                view in you data model, it will ont be used to extract instances.

        Returns:
            IssueList: A list of issues that occurred during the extraction.

        """
        self._state._raise_exception_if_condition_not_met(
            "Read DMS Graph",
            empty_data_model_store_required=True,
            empty_instances_store_required=True,
            client_required=True,
        )
        return self._graph(data_model_id, instance_space, skip_cognite_views, unpack_json=False)

    def _graph(
        self,
        data_model_id: DataModelIdentifier,
        instance_space: str | SequenceNotStr[str] | None = None,
        skip_cognite_views: bool = True,
        unpack_json: bool = False,
        str_to_ideal_type: bool = False,
    ) -> IssueList:
        extractor = extractors.DMSGraphExtractor.from_data_model_id(
            # We are skipping the Cognite Views
            data_model_id,
            cast(NeatClient, self._state.client),
            instance_space=instance_space,
            skip_cognite_views=skip_cognite_views,
            unpack_json=unpack_json,
            str_to_ideal_type=str_to_ideal_type,
        )
        return self._state.write_graph(extractor)

    def raw(
        self,
        db_name: str,
        table_name: str,
        type: str | None = None,
        foreign_keys: str | SequenceNotStr[str] | None = None,
        unpack_json: bool = False,
        str_to_ideal_type: bool = False,
    ) -> IssueList:
        """Reads a raw table from CDF to the knowledge graph.

        Args:
            db_name: The name of the database
            table_name: The name of the table, this will be assumed to be the type of the instances.
            type: The type of instances in the table. If None, the table name will be used.
            foreign_keys: The name of the columns that are foreign keys. If None, no foreign keys are used.
            unpack_json: If True, the JSON objects will be unpacked into the graph.
            str_to_ideal_type: If True, the string values will be converted to ideal types.

        Returns:
            IssueList: A list of issues that occurred during the extraction.

        Example:
            ```python
            neat.read.cdf.raw("my_db", "my_table", "Asset")
            ```

        """
        self._state._raise_exception_if_condition_not_met(
            "Read RAW",
            client_required=True,
        )

        extractor = extractors.RAWExtractor(
            cast(NeatClient, self._state.client),
            db_name=db_name,
            table_name=table_name,
            table_type=type,
            foreign_keys=foreign_keys,
            unpack_json=unpack_json,
            str_to_ideal_type=str_to_ideal_type,
        )
        return self._state.instances.store.write(extractor)


@session_class_wrapper
class CDFClassicAPI(BaseReadAPI):
    """Reads from the Classic Data Model from CDF.
    Use the `.graph()` method to load CDF core resources to the knowledge graph.

    """

    def graph(
        self,
        root_asset_external_id: str,
        limit_per_type: int | None = None,
        identifier: Literal["id", "externalId"] = "id",
    ) -> IssueList:
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
            identifier: The identifier to use for the core nodes. Note selecting "id" can cause issues if the external
                ID of the core nodes is missing. Default is "id".

        Returns:
            IssueList: A list of issues that occurred during the extraction.

        Example:
            ```python
            neat.read.cdf.graph("root_asset_external_id")
            ```
        """
        self._state._raise_exception_if_condition_not_met(
            "Read classic graph",
            empty_data_model_store_required=True,
            empty_instances_store_required=True,
            client_required=True,
        )

        return self._graph(
            root_asset_external_id, limit_per_type, identifier, reference_timeseries=False, reference_files=False
        )

    def _graph(
        self,
        root_asset_external_id: str,
        limit_per_type: int | None = None,
        identifier: Literal["id", "externalId"] = "id",
        reference_timeseries: bool = False,
        reference_files: bool = False,
        unpack_metadata: bool = False,
        skip_sequence_rows: bool = False,
    ) -> IssueList:
        namespace = CLASSIC_CDF_NAMESPACE
        extractor = extractors.ClassicGraphExtractor(
            cast(NeatClient, self._state.client),
            root_asset_external_id=root_asset_external_id,
            limit_per_type=limit_per_type,
            namespace=namespace,
            prefix="Classic",
            identifier=identifier,
            unpack_metadata=unpack_metadata,
            skip_sequence_rows=skip_sequence_rows,
        )
        self._state.instances.neat_prefix_by_predicate_uri.update(extractor.neat_prefix_by_predicate_uri)
        self._state.instances.neat_prefix_by_type_uri.update(extractor.neat_prefix_by_type_uri)
        extract_issues = self._state.write_graph(extractor)
        if identifier == "externalId":
            self._state.quoted_source_identifiers = True

        self._state.instances.store.transform(
            ConvertLiteral(
                namespace["ClassicTimeSeries"],
                namespace["isString"],
                lambda is_string: "string" if is_string else "numeric",
            )
        )
        self._state.instances.store.transform(
            LiteralToEntity(None, namespace["source"], "ClassicSourceSystem", "name"),
        )
        # The above transformations creates a new type, so we need to update
        self._state.instances.neat_prefix_by_type_uri.update({namespace["ClassicSourceSystem"]: "ClassicSourceSystem_"})
        # Updating the information model.
        prepare_issues = self._state.data_model_store.transform(
            ClassicPrepareCore(namespace, reference_timeseries, reference_files)
        )

        all_issues = IssueList(extract_issues + prepare_issues)
        # Update the provenance with all issue.
        object.__setattr__(self._state.instances.store.provenance[-1].target_entity, "issues", all_issues)
        all_issues.action = "Read Classic Graph"
        if all_issues:
            print("Use the .inspect.issues() for more details")

        return all_issues

    def time_series(self, data_set_external_id: str, identifier: Literal["id", "externalId"] = "id") -> IssueList:
        """Read the time series from CDF into NEAT.

        Args:
            data_set_external_id: The external id of the data set
            identifier: The identifier to use for the time series. Note selecting "id" can cause issues if the external
                ID of the time series is missing. Default is "id".

        Returns:
            IssueList: A list of issues that occurred during the extraction.

        Example:
            ```python
            neat.read.cdf.time_series("data_set_external_id")
            ```

        """
        namespace = CLASSIC_CDF_NAMESPACE
        self._state._raise_exception_if_condition_not_met(
            "Read time series",
            empty_data_model_store_required=True,
            empty_instances_store_required=True,
            client_required=True,
        )
        extractor = extractors.TimeSeriesExtractor.from_dataset(
            cast(NeatClient, self._state.client),
            data_set_external_id=data_set_external_id,
            namespace=namespace,
            identifier=identifier,
            prefix="Classic",
            skip_connections=True,
        )
        self._state.instances.neat_prefix_by_predicate_uri.update(
            {
                namespace["dataSetId"]: InstanceIdPrefix.data_set,
                namespace["assetId"]: InstanceIdPrefix.asset,
            }
        )
        self._state.instances.neat_prefix_by_type_uri.update(
            {namespace[f"Classic{extractor._default_rdf_type}"]: InstanceIdPrefix.time_series}
        )
        extract_issues = self._state.instances.store.write(extractor)

        if identifier == "externalId":
            self._state.quoted_source_identifiers = True

        self._state.instances.store.transform(
            ConvertLiteral(
                namespace["ClassicTimeSeries"],
                namespace["isString"],
                lambda is_string: "string" if is_string else "numeric",
            )
        )

        return extract_issues

    def file_metadata(self, data_set_external_id: str, identifier: Literal["id", "externalId"] = "id") -> IssueList:
        """Read the file metadata from CDF into NEAT.

        Note all files that have InstanceId set will be silently skipped. This method is for extracting
        non-contextualized file medata only. If you want to include the potential connection from file metadata
        to assets, use the `neat.read.cdf.graph()` method instead and select the asset hierarchy connected to this file.

        Args:
            data_set_external_id: The external id of the data set
            identifier: The identifier to use for the file metadata. Note selecting "id" can cause issues
                if the external ID of the file metadata is missing. Default is "id".

        Returns:
            IssueList: A list of issues that occurred during the extraction.

        Example:
            ```python
            neat.read.cdf.time_series("data_set_external_id")
            ```
        """
        namespace = CLASSIC_CDF_NAMESPACE
        self._state._raise_exception_if_condition_not_met(
            "Read time series",
            empty_data_model_store_required=True,
            empty_instances_store_required=True,
            client_required=True,
        )
        extractor = extractors.FilesExtractor.from_dataset(
            cast(NeatClient, self._state.client),
            data_set_external_id=data_set_external_id,
            namespace=namespace,
            identifier=identifier,
            prefix="Classic",
            skip_connections=True,
        )
        self._state.instances.neat_prefix_by_predicate_uri.update(
            {
                namespace["dataSetId"]: InstanceIdPrefix.data_set,
                namespace["assetId"]: InstanceIdPrefix.asset,
            }
        )
        self._state.instances.neat_prefix_by_type_uri.update(
            {namespace[f"Classic{extractor._default_rdf_type}"]: InstanceIdPrefix.time_series}
        )
        extract_issues = self._state.instances.store.write(extractor)

        if identifier == "externalId":
            self._state.quoted_source_identifiers = True

        self._state.instances.store.transform(
            LiteralToEntity(None, namespace["source"], "ClassicSourceSystem", "name"),
        )
        # The above transformations creates a new type, so we need to update
        self._state.instances.neat_prefix_by_type_uri.update({namespace["ClassicSourceSystem"]: "ClassicSourceSystem_"})

        return extract_issues


@session_class_wrapper
class ExcelReadAPI(BaseReadAPI):
    """Reads a Neat Excel Data Model to the data model store.
    The data model spreadsheets may contain conceptual or physical data model definitions.

    Args:
        io: file path to the Excel sheet

    Example:
        ```python
        neat.read.excel("conceptual_or_physical_data_model.xlsx")
        ```
    """

    def __init__(self, state: SessionState, verbose: bool) -> None:
        super().__init__(state, verbose)

    def __call__(self, io: Any, enable_manual_edit: bool = False) -> IssueList:
        """Reads a Neat Excel Data Model to the data model store.
        The data model spreadsheets may contain conceptual or physical data model definitions.

            Args:
                io: file path to the Excel sheet
                enable_manual_edit: If True, the user will be able to re-import data model
                    which where edit outside NeatSession

            !!! note "Manual Edit Warning"
                This is an alpha feature and is subject to change without notice.
                It is expected to have some limitations and may not work as expected in all cases.
        """
        reader = NeatReader.create(io)
        path = reader.materialize_path()

        if enable_manual_edit:
            warnings.filterwarnings("default")
            ExperimentalFlags.manual_data_model_edit.warn()
        else:
            self._state._raise_exception_if_condition_not_met(
                "Read Excel Data Model",
                empty_data_model_store_required=True,
            )

        return self._state.data_model_import(importers.ExcelImporter(path), enable_manual_edit)


@session_class_wrapper
class YamlReadAPI(BaseReadAPI):
    def __call__(self, io: Any, format: Literal["neat", "toolkit"] = "neat") -> IssueList:
        """Reads a yaml with either neat data mode, or several toolkit yaml files to
        import Data Model(s) into NeatSession.

        Args:
            io: File path to the Yaml file in the case of "neat" yaml, or path to a zip folder or directory with several
                Yaml files in the case of "toolkit".
            format: The format of the yaml file(s). Can be either "neat" or "toolkit".

        Example:
            ```python
            neat.read.yaml("path_to_toolkit_yamls")
            ```
        """
        self._state._raise_exception_if_condition_not_met(
            "Read YAML data model",
            empty_data_model_store_required=True,
        )
        reader = NeatReader.create(io)
        path = reader.materialize_path()
        importer: BaseImporter
        if format == "neat":
            importer = importers.DictImporter.from_yaml_file(path, source_name=f"{reader!s}")
        elif format == "toolkit":
            dms_importer = importers.DMSImporter.from_path(path, self._state.client)
            if dms_importer.issue_list.has_warning_type(MissingCogniteClientWarning):
                raise NeatSessionError(
                    "No client provided. You are referencing Cognite containers in your data model, "
                    "NEAT needs a client to lookup the container definitions. "
                    "Please set the client in the session, NeatSession(client=client)."
                )
            importer = dms_importer
        else:
            raise NeatValueError(f"Unsupported YAML format: {format}")
        return self._state.data_model_import(importer)


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

    !!! note "Method read.csv requires NEATEngine plug-in"
    """

    def __call__(self, io: Any, type: str, primary_key: str) -> None:
        warnings.filterwarnings("default")
        ExperimentalFlags.csv_read.warn()

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
        """Reads a DEXPI file into the NeatSession and executes set of predefined transformations.

        Args:
            io: file path or url to the DEXPI file

        Example:
            ```python
            neat.read.xml.dexpi("url_or_path_to_dexpi_file")
            ```

        !!! note "Method read.xml.dexpi requires NEATEngine plug-in"

        !!! note "This method bundles several graph transformers which"
            - attach values of generic attributes to nodes
            - create associations between nodes
            - remove unused generic attributes
            - remove associations between nodes that do not exist in the extracted graph
            - remove edges to nodes that do not exist in the extracted graph
        """
        warnings.filterwarnings("default")
        ExperimentalFlags.dexpi_read.warn()

        self._state._raise_exception_if_condition_not_met(
            "Read DEXPI file",
            empty_data_model_store_required=True,
            empty_instances_store_required=True,
        )

        path = NeatReader.create(io).materialize_path()
        engine = import_engine()
        engine.set.format = "dexpi"
        engine.set.file = path
        extractor = engine.create_extractor()
        self._state.instances.store.write(extractor)

        DEXPI = get_default_prefixes_and_namespaces()["dexpi"]

        transformers = [
            # Remove any instance which type is unknown
            PruneInstancesOfUnknownType(),
            # Directly connect generic attributes
            AttachPropertyFromTargetToSource(
                target_property=DEXPI.Value,
                target_property_holding_new_property=DEXPI.Name,
                target_node_type=DEXPI.GenericAttribute,
                delete_target_node=True,
            ),
            # Directly connect associations
            AttachPropertyFromTargetToSource(
                target_property=DEXPI.ItemID,
                target_property_holding_new_property=DEXPI.Type,
                target_node_type=DEXPI.Association,
                delete_target_node=True,
            ),
            # Remove unused generic attributes and associations
            PruneTypes([DEXPI.GenericAttribute, DEXPI.Association]),
            # Remove edges to nodes that do not exist in the extracted graph
            PruneDeadEndEdges(),
        ]

        for transformer in transformers:
            self._state.instances.store.transform(cast(Transformers, transformer))

    def aml(self, io: Any) -> None:
        """Reads an AML file into NeatSession and executes a set of predefined transformations.

        Args:
            io: file path or url to the AML file

        Example:
            ```python
            neat.read.xml.aml("url_or_path_to_aml_file")
            ```

        !!! note "Method read.xml.aml requires NEATEngine plug-in"

        !!! note "This method bundles several graph transformers which"
            - attach values of attributes to nodes
            - remove unused attributes
            - remove edges to nodes that do not exist in the extracted graph
        """
        warnings.filterwarnings("default")
        ExperimentalFlags.aml_read.warn()

        self._state._raise_exception_if_condition_not_met(
            "Read AML file",
            empty_data_model_store_required=True,
            empty_instances_store_required=True,
        )

        path = NeatReader.create(io).materialize_path()
        engine = import_engine()
        engine.set.format = "aml"
        engine.set.file = path
        extractor = engine.create_extractor()
        self._state.instances.store.write(extractor)

        AML = get_default_prefixes_and_namespaces()["aml"]

        transformers = [
            # Remove any instance which type is unknown
            PruneInstancesOfUnknownType(),
            # Directly connect generic attributes
            AttachPropertyFromTargetToSource(
                target_property=AML.Value,
                target_property_holding_new_property=AML.Name,
                target_node_type=AML.Attribute,
                delete_target_node=True,
            ),
            # Prune unused attributes
            PruneTypes([AML.Attribute]),
            # # Remove edges to nodes that do not exist in the extracted graph
            PruneDeadEndEdges(),
        ]

        for transformer in transformers:
            self._state.instances.store.transform(cast(Transformers, transformer))


@session_class_wrapper
class RDFReadAPI(BaseReadAPI):
    """Reads an RDF source into NeatSession. Supported sources are "ontology" or "imf".

    Args:
        io: file path or url to the RDF source
    """

    def __init__(self, state: SessionState, verbose: bool) -> None:
        super().__init__(state, verbose)

    def ontology(self, io: Any) -> IssueList:
        """Reads an OWL ontology source into NeatSession.

        Args:
            io: file path or url to the OWL file

        Example:
            ```python
            neat.read.rdf.ontology("url_or_path_to_owl_source")
            ```
        """
        warnings.filterwarnings("default")
        ExperimentalFlags.ontology_read.warn()

        self._state._raise_exception_if_condition_not_met(
            "Read Ontology file",
            empty_data_model_store_required=True,
        )

        reader = NeatReader.create(io)
        importer = importers.OWLImporter.from_file(reader.materialize_path(), source_name=f"file {reader!s}")
        return self._state.data_model_import(importer)

    def instances(self, io: Any, named_graph: str | None = None) -> IssueList:
        self._state._raise_exception_if_condition_not_met(
            "Read RDF Instances",
            empty_data_model_store_required=True,
        )
        reader = NeatReader.create(io)

        # validate and convert named_graph to URI
        named_graph_uri: URIRef | None = None
        if named_graph:
            if not re.match(SPACE_COMPLIANCE_REGEX, named_graph):
                raise NeatValueError(f"Named graph '{named_graph}' does not comply with naming requirements. ")
            named_graph_uri = NAMED_GRAPH_NAMESPACE[named_graph]

        self._state.instances.store.write(extractors.RdfFileExtractor(reader.materialize_path()), named_graph_uri)
        return IssueList()

    def __call__(
        self,
        io: Any,
        type: NeatObjectType | None = None,
        source: RDFFileType | None = None,
        named_graph: str | URIRef | None = None,
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
            return self.instances(io, named_graph=named_graph)

        else:
            raise NeatSessionError(f"Expected data model or instances, got {type}")


@session_class_wrapper
class Examples:
    """Used as example for reading various sources into NeatSession."""

    def __init__(self, state: SessionState) -> None:
        self._state = state

    def nordic44(self) -> IssueList:
        """Reads the Nordic 44 knowledge graph into the NeatSession graph store."""

        self._state._raise_exception_if_condition_not_met(
            "Read Nordic44 graph example",
            empty_instances_store_required=True,
            empty_data_model_store_required=True,
        )

        self._state.instances.store.write(extractors.RdfFileExtractor(instances_examples.nordic44_knowledge_graph))
        return IssueList()

    def pump_example(self) -> IssueList:
        """Reads the Hello World pump example into the NeatSession."""

        self._state._raise_exception_if_condition_not_met(
            "Read Pump Data Model example",
            empty_data_model_store_required=True,
        )

        importer: importers.ExcelImporter = importers.ExcelImporter(catalog.hello_world_pump)
        return self._state.data_model_import(importer)

    def core_data_model(self) -> IssueList:
        """Reads the core data model example into the NeatSession."""

        self._state._raise_exception_if_condition_not_met(
            "Read Core Data Model example",
            empty_data_model_store_required=True,
            client_required=True,
        )

        cdm_v1 = DataModelId.load(("cdf_cdm", "CogniteCore", "v1"))
        importer: importers.DMSImporter = importers.DMSImporter.from_data_model_id(
            cast(NeatClient, self._state.client), cdm_v1
        )
        return self._state.data_model_import(importer)
