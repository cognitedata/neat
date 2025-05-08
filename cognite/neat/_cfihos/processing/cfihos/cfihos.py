import pathlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

import numpy as np
import pandas as pd

from cognite.neat._cfihos.common.generic_classes import DataSource, EntityStructure, PropertyStructure, Relations
from cognite.neat._cfihos.common.utils import read_input_sheet
from cognite.neat._cfihos.processing.base_model_interpreter import (
    BaseModelInterpreter,
)
from cognite.neat._cfihos.processing.cfihos import constants

from ..cfihos.data_sheets_column_mappings import (
    ENTITY_CDM_EXTENSION_MAPPING,
    ENTITY_COLUMN_MAPPING,
    ENTITY_EDGE_COLUMN_MAPPING,
    ENTITY_EDGE_REVERSE_COLUMN_MAPPING,
    ENTITY_PROPERTY_METADATA_MAPPING,
    ENTITY_RAW_COLUMN_MAPPING,
    ENTITY_RELEVANT_PROPERTY_COLUMNS,
    TAG_OR_EQUIPMENT_PROPERTY_METADATA_MAPPING,
    TagOrEquipment,
)


@dataclass
class cfihosTypeTag:
    """Class for CFIHOS Tag type."""

    entities_abs_fpath: str = field(default="", init=False)
    entities_attrib_abs_fpath: str = field(default="", init=False)
    property_metadata_abs_fpath: str = field(default="", init=False)

    # file containing the first class citizens properties' attributes
    entity_first_class_attributes_fpath: str = field(default="", init=False)

    data_folder_abs_fpath: str
    entities_fname: str
    entities_attrib_fname: str
    property_metadata_fname: str

    # If the system extends CFIHOS, the CFIHOS base files should be provided
    base_folder_abs_fpath: str = ""
    base_entities_attrib_fname: str = ""
    base_property_metadata_fname: str = ""

    type: str = constants.CFIHOS_TYPE_TAG
    type_prefix: str = constants.CFIHOS_TYPE_TAG_PREFIX
    type_id_prefix: str = constants.CFIHOS_ID_TAG_PREFIX
    id_prefix: str = constants.CFIHOS_ID_PREFIX
    id_prefix_replacement: str = "_"

    def __post_init__(self):
        """Sets the absolute file paths for the entities, entities attributes and property metadata files."""
        self.entities_abs_fpath = self.data_folder_abs_fpath + self.entities_fname
        self.entities_attrib_abs_fpath = self.data_folder_abs_fpath + self.entities_attrib_fname
        self.property_metadata_abs_fpath = self.data_folder_abs_fpath + self.property_metadata_fname
        self.base_entities_attrib_abs_fpath = ""
        self.base_property_metadata_abs_fpath = ""
        if self.base_folder_abs_fpath and self.base_entities_attrib_fname:
            self.base_entities_attrib_abs_fpath = self.base_folder_abs_fpath + self.base_entities_attrib_fname
        if self.base_folder_abs_fpath and self.base_property_metadata_fname:
            self.base_property_metadata_abs_fpath = self.base_folder_abs_fpath + self.base_property_metadata_fname


@dataclass
class cfihosTypeEquipment:
    """Class for CFIHOS Equipment type."""

    entities_abs_fpath: str = field(default="", init=False)
    entities_attrib_abs_fpath: str = field(default="", init=False)
    property_metadata_abs_fpath: str = field(default="", init=False)

    # file containing the first class citizens properties' attributes
    entity_first_class_attributes_fpath: str = field(default="", init=False)

    data_folder_abs_fpath: str
    entities_fname: str
    entities_attrib_fname: str
    property_metadata_fname: str

    # If the system extends CFIHOS, the CFIHOS base files should be provided
    base_folder_abs_fpath: str = ""
    base_entities_attrib_fname: str = ""
    base_property_metadata_fname: str = ""

    type: str = constants.CFIHOS_TYPE_EQUIPMENT
    type_prefix: str = constants.CFIHOS_TYPE_EQUIPMENT_PREFIX
    type_id_prefix: str = constants.CFIHOS_ID_EQUIPMENT_PREFIX
    id_prefix: str = constants.CFIHOS_ID_PREFIX
    id_prefix_replacement: str = "_"

    def __post_init__(self):
        """Sets the absolute file paths for the entities, entities attributes and property metadata files."""
        self.entities_abs_fpath = self.data_folder_abs_fpath + self.entities_fname
        self.entities_attrib_abs_fpath = self.data_folder_abs_fpath + self.entities_attrib_fname
        self.property_metadata_abs_fpath = self.data_folder_abs_fpath + self.property_metadata_fname
        self.base_entities_attrib_abs_fpath = ""
        self.base_property_metadata_abs_fpath = ""
        if self.base_folder_abs_fpath and self.base_entities_attrib_fname:
            self.base_entities_attrib_abs_fpath = self.base_folder_abs_fpath + self.base_entities_attrib_fname
        if self.base_folder_abs_fpath and self.base_property_metadata_fname:
            self.base_property_metadata_abs_fpath = self.base_folder_abs_fpath + self.base_property_metadata_fname


@dataclass
class cfihosTypeEntity:
    """Class for CFIHOS Entity type."""

    entities_abs_fpath: str = field(default="", init=False)
    entities_attrib_abs_fpath: str = field(default="", init=False)
    entities_attrib_relation_abs_fpath: str = field(default="", init=False)

    # file containing the first class citizens properties' attributes
    entity_first_class_attributes_fpath: str = field(default="", init=False)

    # file containing the edges
    entities_edges_abs_fpath: str = field(default="", init=False)

    # file containing entities implementing core models
    entities_core_model_abs_fpath: str = field(default="", init=False)

    data_folder_abs_fpath: str
    entities_fname: str
    entities_attrib_fname: str
    entities_attrib_relation_fname: str

    entities_edges: str = ""  # added for edge
    entities_core_model: str = ""  # added for core_model

    # If the system extends CFIHOS, the CFIHOS base files should be provided
    base_folder_abs_fpath: str = ""
    base_entities_attrib_fname: str = ""
    base_tag_attrib_fname: str = ""

    type: str = constants.CFIHOS_TYPE_ENTITY
    type_prefix: str = constants.CFIHOS_TYPE_ENTITY_PREFIX
    type_id_prefix: str = constants.CFIHOS_ID_ENTITY_PREFIX
    id_prefix: str = constants.CFIHOS_ID_PREFIX
    id_prefix_replacement: str = "_"

    def __post_init__(self):
        """Sets the absolute file paths for the entities, entities attributes and property metadata files.

        If entities_edges and entities_core_model are provided, set the absolute file paths for these files as well.
        """
        self.entities_abs_fpath = self.data_folder_abs_fpath + self.entities_fname
        self.entities_attrib_abs_fpath = self.data_folder_abs_fpath + self.entities_attrib_fname
        self.entities_attrib_relation_abs_fpath = self.data_folder_abs_fpath + self.entities_attrib_relation_fname
        self.base_entities_attrib_abs_fpath = ""
        self.base_tag_attrib_abs_fpath = ""
        if self.entities_edges:
            self.entities_edges_abs_fpath = self.data_folder_abs_fpath + self.entities_edges  # added for edge
        if self.entities_core_model:
            self.entities_core_model_abs_fpath = (
                self.data_folder_abs_fpath + self.entities_core_model
            )  # added for core_model
        if self.base_folder_abs_fpath and self.base_entities_attrib_fname:
            self.base_entities_attrib_abs_fpath = self.base_folder_abs_fpath + self.base_entities_attrib_fname
        if self.base_folder_abs_fpath and self.base_tag_attrib_fname:
            self.base_tag_attrib_abs_fpath = self.base_folder_abs_fpath + self.base_tag_attrib_fname


@dataclass
class CfihosProcessor(BaseModelInterpreter):
    """Class for processing CFIHOS data and returning it in a generic format."""

    # Which CFIHOS entity types are included in the model
    included_cfihos_types_config: list[dict]

    includes_cfihos_types: list[cfihosTypeEntity | cfihosTypeEquipment | cfihosTypeEquipment] = field(
        default_factory=list, init=False
    )

    # TODO consider this one
    abs_fpath_model_raw_data_folder: str

    # File containing all model entity types, is used to generate mapping table
    rdl_master_objects_fname: str
    rdl_master_object_id_col_name: str
    rdl_master_object_name_col_name: str

    # Dictionary
    cfihos_type_metadata: dict = field(default_factory=dict, init=False)

    # ID prefix filters #TODO: this must contain the set of filters and create a replace filter function
    id_prefix_replace_filters: dict[str, str] = field(default_factory=dict, init=False)

    _CFIHOS_ENTITY = constants.CFIHOS_TYPE_ENTITY
    _CFIHOS_EQUIPMENT = constants.CFIHOS_TYPE_EQUIPMENT
    _CFIHOS_TAG = constants.CFIHOS_TYPE_TAG

    _map_cfihos_type_to_object: ClassVar[dict] = {
        "cfihosTypeEntity": cfihosTypeEntity,
        "cfihosTypeEquipment": cfihosTypeEquipment,
        "cfihosTypeTag": cfihosTypeTag,
    }

    # entities
    _entities: dict[str, dict] = field(default_factory=dict, init=False)

    # Name of the model processor (from the config file)
    processor_config_name: str

    model_interpreter_name = "CfihosProcessor"
    interpreting_model_name: str = "CFIHOS"

    source: DataSource = field(default=DataSource.default())

    _supported_cfihos_types: ClassVar[set] = set([_CFIHOS_ENTITY, _CFIHOS_EQUIPMENT, _CFIHOS_TAG])

    _map_entity_id_to_dms_id: dict[str, str] = field(default_factory=dict, init=False)
    _map_dms_id_to_entity_id: dict[str, str] = field(default_factory=dict, init=False)
    _map_entity_name_to_entity_id: dict[str, str] = field(default_factory=dict, init=False)

    def __post_init__(self):
        """Setup cifhos included type object."""
        for init_config in self.included_cfihos_types_config:
            cfihos_type = init_config.pop("type")
            type_obj = self._map_cfihos_type_to_object.get(cfihos_type)
            if type_obj is None:
                raise KeyError(
                    f"Provided CFIHOS type {cfihos_type} is not supported. "
                    f"Must be one of the following: {list(self._map_cfihos_type_to_object.keys())}"
                )
            self.includes_cfihos_types.append(type_obj(**init_config))

        # Setup cfihos type metadata
        self.cfihos_type_metadata = {}
        for cfihos_type in self.includes_cfihos_types:
            self.cfihos_type_metadata[cfihos_type.type] = {
                "type_prefix": cfihos_type.type_prefix,
                "type_id_prefix": cfihos_type.type_id_prefix,
            }

        # set of id-prefixes and how we want to replace them, e.g. for tag/equipment CFIHOS-300000001 => _300000001
        self.id_prefix_replace_filters = {}
        for cfihos_type in self.includes_cfihos_types:
            self.id_prefix_replace_filters[cfihos_type.id_prefix] = cfihos_type.id_prefix_replacement

        self._init_mapping_tables()

    def _init_mapping_tables(self):
        """Initializes mapping tables."""
        self._init_entity_name_to_entity_id()
        self._init_entity_id_to_dms_id()
        self._map_dms_id_to_entity_id = {val: key for key, val in self._map_entity_id_to_dms_id.items()}

    def _init_entity_name_to_entity_id(self):
        """Creates a mapping table from entity name to model id."""
        abs_fpath = self.abs_fpath_model_raw_data_folder / pathlib.Path(self.rdl_master_objects_fname)
        df = read_input_sheet(abs_fpath, source=self.source)[
            [self.rdl_master_object_id_col_name, self.rdl_master_object_name_col_name]
        ]
        self._map_entity_name_to_entity_id = dict(
            zip(
                df[self.rdl_master_object_name_col_name],
                df[self.rdl_master_object_id_col_name],
                strict=False,
            )
        )

    def _init_entity_id_to_dms_id(self):
        id_prefix_to_entity_types = {}
        id_prefix_filters = []
        for _, metadata in self.cfihos_type_metadata.items():
            id_prefix_to_entity_types.setdefault(metadata["type_id_prefix"], []).append(metadata["type_prefix"])
            id_prefix_filters.append(metadata["type_id_prefix"])

        # Remove duplicates
        id_prefix_filters = list(set(id_prefix_filters))
        df = read_input_sheet(
            self.abs_fpath_model_raw_data_folder / pathlib.Path(self.rdl_master_objects_fname),
            source=self.source,
        )
        entity_to_dms_mapping = {}

        for id_prefix_filter in id_prefix_filters:
            df_enity_type = df.loc[df[self.rdl_master_object_id_col_name].str.startswith(id_prefix_filter)]
            entity_types = id_prefix_to_entity_types[id_prefix_filter]
            for _, row in df_enity_type.iterrows():
                for entity_type in entity_types:
                    entity_ending_id = row[self.rdl_master_object_id_col_name]
                    for (
                        remove_str,
                        _,
                    ) in self.id_prefix_replace_filters.items():  # Revise this one
                        entity_ending_id = entity_ending_id.replace(remove_str, entity_ending_id)

                    # Want to ensure that CFIHOS ID remains in our ID, hence this split

                    entity_to_dms_mapping[entity_type + row[self.rdl_master_object_id_col_name]] = entity_type + row[
                        self.rdl_master_object_id_col_name
                    ].replace("-", "_")

        self._map_entity_id_to_dms_id = entity_to_dms_mapping

    def replace_id_func(self, s: str):
        """Replace id prefixes."""
        for replace_str, replacement_str in self.id_prefix_replace_filters.items():
            s = s.replace(replace_str, replacement_str)
        return s

    def process(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Process the CFIHOS Entity, Tag and Equipment data and return the processed.

        entities, properties and property metadata in a generic format.

        Returns:
            Tuple[pd.DataFrame,pd.DataFrame, pd.DataFrame]: DataFrames of model entities, corresponding properties,
            and properties metadata
        """
        processing_funcs: dict[
            str,
            Callable[[Any], tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]],
        ] = {
            constants.CFIHOS_TYPE_ENTITY: self._process_and_retrieve_entities,
            constants.CFIHOS_TYPE_TAG: self._process_and_retrieve_tags,
            constants.CFIHOS_TYPE_EQUIPMENT: self._process_and_retrieve_equipment,
        }

        list_of_entities_df = []
        list_of_properties_df = []
        list_of_properties_metadata_df = []

        for cfihos_type in self.includes_cfihos_types:
            if cfihos_type.type not in processing_funcs:
                raise KeyError(
                    f"cfihos_type - {cfihos_type.type} is not supported by processing_funcs: {processing_funcs.keys()}"
                )
            process_func = processing_funcs[cfihos_type.type]

            self._loggingInfo(f"Collecting {cfihos_type.type}")

            df_entities, df_properties, df_properties_metadata = process_func(cfihos_type)
            df_entities["type"] = cfihos_type.type
            df_entities["type_prefix"] = cfihos_type.type_prefix
            list_of_entities_df.append(df_entities)
            list_of_properties_df.append(df_properties)
            list_of_properties_metadata_df.append(df_properties_metadata)

        df_entities = pd.concat(list_of_entities_df)
        df_properties = pd.concat(list_of_properties_df)
        df_properties_metadata = pd.concat(list_of_properties_metadata_df)

        df_entities[PropertyStructure.FIRSTCLASSCITIZEN] = (
            df_entities[PropertyStructure.FIRSTCLASSCITIZEN].astype("boolean").fillna(False)
        )
        df_properties[PropertyStructure.FIRSTCLASSCITIZEN] = (
            df_properties[PropertyStructure.FIRSTCLASSCITIZEN].astype("boolean").fillna(False)
        )

        # add unique_validaiton_id column to make sure no duplicate properties per entity.
        # Duplicate properties for the same entity should be unique if one entity is FCC
        df_properties[PropertyStructure.UNIQUE_VALIDATION_ID] = np.where(
            df_properties[PropertyStructure.FIRSTCLASSCITIZEN],
            df_properties[EntityStructure.ID] + df_properties[PropertyStructure.ID],
            df_properties[EntityStructure.ID] + df_properties[PropertyStructure.ID],
        )

        # Get df_properties_metadata rows that do not exist in df_properties
        df_properties_metadata = df_properties_metadata[
            ~df_properties_metadata[PropertyStructure.ID].isin(df_properties[PropertyStructure.ID])
        ]
        df_properties_metadata.drop_duplicates(subset=[PropertyStructure.ID], inplace=True)

        if not df_entities[EntityStructure.ID].is_unique:
            duplicate_entities = df_entities.loc[
                df_entities[EntityStructure.ID].duplicated(keep=False), ["entityId", "entityName", "description"]
            ]
            raise ValueError(f"Duplicated entity ids detected:\n{duplicate_entities}")

        if not df_properties[PropertyStructure.UNIQUE_VALIDATION_ID].is_unique:
            duplicate_properties = df_properties.loc[
                df_properties[PropertyStructure.UNIQUE_VALIDATION_ID].duplicated(keep=False),
                ["entityId", "entityName", "propertyId", "propertyName", "unique_validation_id"],
            ]
            raise ValueError(f"Duplicated entity-property ids detected:\n{duplicate_properties}")

        df_properties[PropertyStructure.FIRSTCLASSCITIZEN] = (
            df_properties[PropertyStructure.FIRSTCLASSCITIZEN].fillna(False).astype(bool)
        )

        return df_entities, df_properties, df_properties_metadata

    # TODO: Rename/reconsider this one
    def _get_property_metadata(self, fpath: str, mapping_table: dict) -> pd.DataFrame:
        # Get additional propertyMetadata
        df = read_input_sheet(fpath, source=self.source, keep_default_na=False)
        df = df.rename(columns=mapping_table)
        df = df[list(mapping_table.values())]
        return df

    def _extend_property_metadata(
        self, fpath: str, mapping_table: dict[str, str], metadata_subset: pd.DataFrame
    ) -> pd.DataFrame:
        base_metadata = self._get_property_metadata(fpath, mapping_table)
        extended_metadata = pd.concat([metadata_subset, base_metadata], ignore_index=True)
        return extended_metadata

    def _process_and_retrieve_entities(
        self, cfihos_type_obj: cfihosTypeEntity
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Process data according to cfihos entities structures and returns it according to the generic structure.

        In case the reverse relation does not have a corresponding through property (a direct relation), the
        direct relation is added to the properties dataframe.

        Args:
            cfihos_type_obj (cfihosTypeEntity): A CFIHOS Entity Type object containing all the necessary info
            for processing

        Returns:
            Tuple[pd.DataFrame,pd.DataFrame, pd.DataFrame]: A df containing the entities, corresponding property info
            and entity properties metadata
        """
        df = read_input_sheet(
            cfihos_type_obj.entities_abs_fpath,
            source=self.source,
            keep_default_na=False,
        )
        df[EntityStructure.ID] = df[ENTITY_RAW_COLUMN_MAPPING[EntityStructure.ID]]
        df = df.set_index(df[EntityStructure.ID])

        # Convert towards generic types
        df = df.rename(columns=ENTITY_COLUMN_MAPPING)

        # Not all entities strucutres has Parent cols
        if (EntityStructure.INHERITS_FROM_ID in df.columns) and (EntityStructure.INHERITS_FROM_NAME in df.columns):
            df[EntityStructure.INHERITS_FROM_ID] = df[EntityStructure.INHERITS_FROM_ID].apply(
                lambda x: [x] if x else None
            )
            df[EntityStructure.INHERITS_FROM_NAME] = df[EntityStructure.INHERITS_FROM_NAME].apply(
                lambda x: [x] if x else None
            )
        else:
            df[EntityStructure.INHERITS_FROM_ID] = None
            df[EntityStructure.INHERITS_FROM_NAME] = None

        # Select subset
        df = df[
            [
                EntityStructure.ID,
                EntityStructure.NAME,
                EntityStructure.DESCRIPTION,
                EntityStructure.INHERITS_FROM_ID,
                EntityStructure.INHERITS_FROM_NAME,
                EntityStructure.FIRSTCLASSCITIZEN,
            ]
        ]

        # adding entities implementing core model
        if cfihos_type_obj.entities_core_model:
            # # Read Core Data Model inheritance requirements
            df_inherits_cdm = read_input_sheet(
                cfihos_type_obj.entities_core_model_abs_fpath,
                source=self.source,
                keep_default_na=False,
            )

            # Dropping columns (only relevant for IMOD, Core structures have their own names/descriptions)
            df_inherits_cdm.drop(columns=["name", "description"], inplace=True)
            df_inherits_cdm = df_inherits_cdm.rename(columns=ENTITY_CDM_EXTENSION_MAPPING)
            df_inherits_cdm[EntityStructure.IMPLEMENTS_CORE_MODEL] = df_inherits_cdm.apply(
                lambda row: {
                    "space": row["inherited from space"],
                    "external_id": row[EntityStructure.IMPLEMENTS_CORE_MODEL],
                    "version": row["type version"],
                },
                axis=1,
            )
            df_grouped_inheritance = (
                df_inherits_cdm.groupby(EntityStructure.ID)
                .agg({EntityStructure.IMPLEMENTS_CORE_MODEL: list})
                .reset_index()
            )
            df = pd.merge(df.reset_index(drop=True), df_grouped_inheritance, on=EntityStructure.ID, how="left")
            df = df.set_index(df[EntityStructure.ID])
        else:
            df[EntityStructure.IMPLEMENTS_CORE_MODEL] = None

        # Get properties relation to entities
        df_prop = read_input_sheet(
            cfihos_type_obj.entities_attrib_relation_abs_fpath,
            source=self.source,
            keep_default_na=False,
        )

        df_prop = df_prop[list(ENTITY_RELEVANT_PROPERTY_COLUMNS)]
        df_prop = df_prop.rename(columns=ENTITY_RELEVANT_PROPERTY_COLUMNS)
        df_prop = self._assign_rev_through_property(df_prop)
        df_prop[PropertyStructure.FIRSTCLASSCITIZEN] = False
        df_prop[PropertyStructure.FIRSTCLASSCITIZEN] = df_prop[PropertyStructure.FIRSTCLASSCITIZEN].replace(
            np.nan, False
        )

        # Get related properties
        df_prop_metadata = self._get_property_metadata(
            fpath=cfihos_type_obj.entities_attrib_abs_fpath,
            mapping_table=ENTITY_PROPERTY_METADATA_MAPPING,
        )

        if cfihos_type_obj.base_entities_attrib_abs_fpath:
            df_prop_metadata = self._extend_property_metadata(
                fpath=cfihos_type_obj.base_entities_attrib_abs_fpath,
                mapping_table=ENTITY_PROPERTY_METADATA_MAPPING,
                metadata_subset=df_prop_metadata,
            )

        if cfihos_type_obj.base_tag_attrib_abs_fpath:
            df_prop_metadata = self._extend_property_metadata(
                fpath=cfihos_type_obj.base_tag_attrib_abs_fpath,
                mapping_table=TAG_OR_EQUIPMENT_PROPERTY_METADATA_MAPPING,
                metadata_subset=df_prop_metadata,
            )

        metadata_suffix = "_metadata"
        df_prop = df_prop.merge(
            df_prop_metadata,
            how="left",
            on=PropertyStructure.ID,
            suffixes=("", metadata_suffix),
        )
        df_prop = df_prop.drop(df_prop.filter(regex=f"{metadata_suffix}$").columns, axis=1)

        # Check for entity relation, if so update target type to entity type instead of referring to string, int, etc.
        # TODO: Simplify this
        def set_target_type(x, y):
            return x if (x) else y

        df_prop[PropertyStructure.TARGET_TYPE] = df_prop.apply(
            lambda x: set_target_type(x[PropertyStructure.PROPERTY_TYPE], x[PropertyStructure.TARGET_TYPE]),
            axis=1,
        )

        df_prop[PropertyStructure.UOM] = None  # TODO: verify that this will always be Null
        df_prop[PropertyStructure.ENUMERATION_TABLE] = None  # TODO: verify that this will always be Null
        df_prop["temp_prop_type_dict"] = df_prop[PropertyStructure.PROPERTY_TYPE].apply(
            lambda row: self._get_property_field_type(row)
        )
        df_prop[PropertyStructure.PROPERTY_TYPE] = df_prop["temp_prop_type_dict"].apply(lambda x: x["type"])
        df_prop[PropertyStructure.TARGET_TYPE] = df_prop.apply(
            lambda row: self._get_property_field_target_type(row, temp_prop_type_dic_col_name="temp_prop_type_dict"),
            axis=1,
        )

        df_prop[PropertyStructure.IS_UNIQUE] = df_prop[PropertyStructure.IS_REQUIRED].map(
            lambda s: self._get_property_field_is_unique(s)
        )  # TODO: using is required is a bad way of solving this, should be its own field
        df_prop[PropertyStructure.IS_REQUIRED] = df_prop[PropertyStructure.IS_REQUIRED].map(
            lambda s: self._get_property_field_is_required(s)
        )

        # Update all id's of all entity relations
        df_prop.loc[df_prop[PropertyStructure.PROPERTY_TYPE] == "ENTITY_RELATION", PropertyStructure.ID] += "_rel"

        # Add _list to direct or reverese direct relation that is multivalued (MULTI_VALUED is boolean)
        df_prop.loc[df_prop[PropertyStructure.MULTI_VALUED], PropertyStructure.ID] += "_list"

        # Create reverse direct relations if provided
        rows_with_reverse_relations = df_prop[df_prop[PropertyStructure.REV_THROUGH_PROPERTY] != ""]

        if not rows_with_reverse_relations.empty:
            reverse_direct_relations = self._create_reverse_direct_relations(rows_with_reverse_relations)
            df_prop = self._add_property_rows(df_prop, reverse_direct_relations)

        df_prop = df_prop.drop(columns=["temp_prop_type_dict"])

        # Get df_prop_metadata rows that do not exist in df_properties
        df_prop_metadata = df_prop_metadata[
            ~df_prop_metadata[PropertyStructure.ID].isin(df_prop[PropertyStructure.ID].unique())
        ]

        df_prop_metadata[PropertyStructure.ENUMERATION_TABLE] = None  # TODO: verify that this will always be Null
        df_prop_metadata = self._transform_properties(df_prop_metadata)

        if cfihos_type_obj.entities_edges:
            # Read entities-edge relations csv
            df_edge_all = read_input_sheet(
                cfihos_type_obj.entities_edges_abs_fpath,
                source=self.source,
                keep_default_na=False,
            )

            # Define the Edge External ID first
            df_edge_all[PropertyStructure.EDGE_EXTERNAL_ID] = (
                df_edge_all["source"] + "." + df_edge_all["edge unique id"]
            )

            df_edge = df_edge_all[list(ENTITY_EDGE_COLUMN_MAPPING)].rename(columns=ENTITY_EDGE_COLUMN_MAPPING)
            df_reverse_edge = df_edge_all[list(ENTITY_EDGE_REVERSE_COLUMN_MAPPING)].rename(
                columns=ENTITY_EDGE_REVERSE_COLUMN_MAPPING
            )

            # Assign directions and external ID
            df_edge[PropertyStructure.EDGE_DIRECTION] = "outwards"
            df_reverse_edge[PropertyStructure.EDGE_DIRECTION] = "inwards"

            # Concatenate both DataFrames
            df_edge = pd.concat([df_edge, df_reverse_edge], ignore_index=True)

            # Add other information
            df_edge[EntityStructure.ID] = df_edge[PropertyStructure.EDGE_SOURCE]
            df_edge[PropertyStructure.PROPERTY_TYPE] = PropertyStructure.ENTITY_EDGE

            # Concatenate edge with df_prop
            df_prop = pd.concat([df_prop, df_edge], ignore_index=True, sort=False)

        return df, df_prop, df_prop_metadata

    def _process_and_retrieve_tag_or_equipment(
        self, cfihos_type_obj: cfihosTypeEquipment | cfihosTypeTag
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        if cfihos_type_obj.type not in constants.CFIHOS_TYPE_EQUIPMENT_AND_TAG:
            raise ValueError(
                f"cfihos-type '{cfihos_type_obj.type} not supported. "
                f"Function supports {constants.CFIHOS_TYPE_EQUIPMENT_AND_TAG}"
            )

        tag_or_equipment = TagOrEquipment(cfihos_type_obj.type)

        df = read_input_sheet(
            cfihos_type_obj.entities_abs_fpath,
            source=self.source,
            keep_default_na=False,
        )

        # Convert to global unique CFIHOS ID
        df[tag_or_equipment.raw_column_mapping[EntityStructure.ID]] = np.where(
            df[tag_or_equipment.raw_column_mapping[EntityStructure.ID]].str.startswith(cfihos_type_obj.type_id_prefix),
            cfihos_type_obj.type_prefix + df[tag_or_equipment.raw_column_mapping[EntityStructure.ID]],
            df[tag_or_equipment.raw_column_mapping[EntityStructure.ID]],
        )

        df[tag_or_equipment.raw_column_mapping["parent_join_key"]] = df[
            tag_or_equipment.raw_column_mapping["parent_name_key"]
        ].map(self._map_entity_name_to_entity_id)

        # Convert to global unique CFIHOS ID
        df[tag_or_equipment.raw_column_mapping["parent_join_key"]] = np.where(
            df[tag_or_equipment.raw_column_mapping["parent_join_key"]].str.startswith(cfihos_type_obj.type_id_prefix),
            cfihos_type_obj.type_prefix + df[tag_or_equipment.raw_column_mapping["parent_join_key"]],
            df[tag_or_equipment.raw_column_mapping["parent_join_key"]],
        )

        df[EntityStructure.ID] = df[tag_or_equipment.raw_column_mapping[EntityStructure.ID]]

        if tag_or_equipment.raw_column_mapping["parent_join_key"] is not None:
            df_parent = df[[EntityStructure.ID, tag_or_equipment.raw_column_mapping[EntityStructure.NAME]]]
            df_parent = df_parent.drop_duplicates(subset=EntityStructure.ID)

            # Check for inheritance
            df = df.merge(
                df_parent,
                how="left",
                left_on=tag_or_equipment.raw_column_mapping["parent_join_key"],
                right_on=tag_or_equipment.raw_column_mapping["entity_join_key"],
                suffixes=("", constants.PARENT_SUFFIX),
            )

            for idx, row in df.iterrows():
                cfihos_parent_id_col = f"{EntityStructure.ID}_parent"
                cfihos_parent_name_col = f"{cfihos_type_obj.type} class name{constants.PARENT_SUFFIX}"
                if pd.isnull(row[cfihos_parent_id_col]):
                    cfihos_parent_name = row[f"parent {cfihos_type_obj.type} class name"]
                    cfihos_parent_id = self._map_entity_name_to_entity_id.get(cfihos_parent_name, None)
                    df.at[idx, cfihos_parent_id_col] = None
                    df.at[idx, cfihos_parent_name_col] = None
                    if cfihos_parent_id is None:
                        self._loggingInfo(f"parent name '{cfihos_parent_name}' is None, for {row[EntityStructure.ID]}")
                        continue
                    for _, metadata in self.cfihos_type_metadata.items():
                        if cfihos_parent_id.startswith(metadata["type_prefix"] + metadata["type_id_prefix"]):
                            df.at[idx, cfihos_parent_id_col] = cfihos_parent_id
                            df.at[idx, cfihos_parent_name_col] = cfihos_parent_name
                            break

        else:
            df[EntityStructure.INHERITS_FROM_ID] = None
            df[EntityStructure.INHERITS_FROM_NAME] = None

        df_collected_inheritance = (
            df[
                [
                    tag_or_equipment.parent_entity_name_column,
                    tag_or_equipment.parent_entity_id_column,
                    EntityStructure.ID,
                ]
            ]
            .groupby(EntityStructure.ID)
            .agg(lambda x: list(x))
        )

        df = df.drop_duplicates(EntityStructure.ID)
        df = df.merge(
            df_collected_inheritance,
            on=EntityStructure.ID,
            how="left",
            suffixes=("", "_inherit"),
        )

        df[f"{tag_or_equipment.parent_entity_id_column}"] = df[f"{tag_or_equipment.parent_entity_id_column}_inherit"]
        df[f"{tag_or_equipment.parent_entity_id_column}"] = df[f"{tag_or_equipment.parent_entity_id_column}"].apply(
            lambda x: x if x != [None] else None
        )
        df[f"{tag_or_equipment.parent_entity_name_column}"] = df[
            f"{tag_or_equipment.parent_entity_name_column}_inherit"
        ]

        df = df.set_index(df[EntityStructure.ID])

        # Convert towards generic types
        df = df.rename(columns=tag_or_equipment.column_renaming)

        df[EntityStructure.INHERITS_FROM_ID] = df[EntityStructure.INHERITS_FROM_ID].replace({np.nan: None})
        df[EntityStructure.INHERITS_FROM_NAME] = df[EntityStructure.INHERITS_FROM_NAME].replace({np.nan: None})
        # Select subset
        df = df[
            [
                EntityStructure.ID,
                EntityStructure.NAME,
                EntityStructure.DESCRIPTION,
                EntityStructure.INHERITS_FROM_ID,
                EntityStructure.INHERITS_FROM_NAME,
            ]
        ]

        # Get related properties
        df_prop = read_input_sheet(
            cfihos_type_obj.entities_attrib_abs_fpath,
            source=self.source,
            keep_default_na=False,
        )

        # Rename properties according to generic types
        df_prop = df_prop.rename(columns=tag_or_equipment.property_mapping)

        df_prop_metadata = self._get_property_metadata(
            fpath=cfihos_type_obj.property_metadata_abs_fpath,
            mapping_table=TAG_OR_EQUIPMENT_PROPERTY_METADATA_MAPPING,
        )

        if cfihos_type_obj.base_property_metadata_abs_fpath:
            df_prop_metadata = self._extend_property_metadata(
                fpath=cfihos_type_obj.base_property_metadata_abs_fpath,
                mapping_table=TAG_OR_EQUIPMENT_PROPERTY_METADATA_MAPPING,
                metadata_subset=df_prop_metadata,
            )

        join_key = PropertyStructure.ID
        metadata_suffix = "_metadata"
        df_prop = df_prop.merge(
            df_prop_metadata,
            how="left",
            on=join_key,
            suffixes=("", metadata_suffix),
        )

        # update properties' unit of measure from metadata if it doesn't exist
        df_prop.loc[
            df_prop[PropertyStructure.UOM].isnull() | (df_prop[PropertyStructure.UOM] == ""), PropertyStructure.UOM
        ] = df_prop[PropertyStructure.UOM + metadata_suffix]

        df_prop = df_prop.drop(df_prop.filter(regex=f"{metadata_suffix}$").columns, axis=1)

        metadata_columns_of_interest = [
            val for val in TAG_OR_EQUIPMENT_PROPERTY_METADATA_MAPPING.values() if val != join_key
        ]

        # Convert to global unique CFIHOS ID
        df_prop[EntityStructure.ID] = np.where(
            df_prop[EntityStructure.ID].str.startswith(cfihos_type_obj.type_id_prefix),
            cfihos_type_obj.type_prefix + df_prop[EntityStructure.ID],
            df_prop[EntityStructure.ID],
        )

        # Select subset of columns
        df_prop = df_prop[
            list(
                set(
                    [
                        EntityStructure.ID,
                        EntityStructure.NAME,
                        PropertyStructure.ID,
                        PropertyStructure.NAME,
                        PropertyStructure.UOM,
                        *metadata_columns_of_interest,
                    ]
                )
            )
        ]

        df_prop = self._transform_properties(df_prop)
        # Update all id's of all entity relation's
        df_prop.loc[df_prop[PropertyStructure.PROPERTY_TYPE] == "ENTITY_RELATION", PropertyStructure.ID] = (
            df_prop.loc[df_prop[PropertyStructure.PROPERTY_TYPE] == "ENTITY_RELATION", PropertyStructure.ID] + "_rel"
        )

        # Get df_prop_metadata rows that do not exist in df_properties
        df_prop_metadata = df_prop_metadata[
            ~df_prop_metadata[PropertyStructure.ID].isin(df_prop[PropertyStructure.ID].unique())
        ]
        df_prop_metadata = self._transform_properties(df_prop_metadata)

        return df, df_prop, df_prop_metadata

    def _process_and_retrieve_equipment(self, cfihos_type_obj: cfihosTypeEquipment):
        return self._process_and_retrieve_tag_or_equipment(cfihos_type_obj)

    def _process_and_retrieve_tags(self, cfihos_type_obj: cfihosTypeTag):
        return self._process_and_retrieve_tag_or_equipment(cfihos_type_obj)

    def _transform_properties(self, df_prop: pd.DataFrame) -> pd.DataFrame:
        """Transforms and enriches the properties according to the generic property structure.

        Args:
            df_prop (pd.DataFrame): A DataFrame containing the property information

        Returns:
            pd.DataFrame: The transformed DataFrame
        """
        df_prop[PropertyStructure.IS_REQUIRED] = False  # TODO Missing data on this, thus defaults to false
        df_prop[PropertyStructure.MULTI_VALUED] = False  # TODO Missing data on this, thus defaults to false

        # Make sure that UOM column always exits
        df_prop[PropertyStructure.UOM] = (
            "" if PropertyStructure.UOM not in df_prop.columns else df_prop[PropertyStructure.UOM]
        )

        def is_entity_relation(x, y):
            if x or y:
                pass
            return None

        df_prop[PropertyStructure.PROPERTY_TYPE] = df_prop.apply(
            lambda x: is_entity_relation(x[PropertyStructure.ENUMERATION_TABLE], x[PropertyStructure.UOM]),
            axis=1,
        )
        df_prop["temp_prop_type_dict"] = df_prop[PropertyStructure.PROPERTY_TYPE].apply(
            lambda row: self._get_property_field_type(row)
        )
        df_prop[PropertyStructure.PROPERTY_TYPE] = df_prop["temp_prop_type_dict"].apply(lambda x: x["type"])
        df_prop[PropertyStructure.TARGET_TYPE] = df_prop.apply(
            lambda row: self._get_property_field_target_type(row, temp_prop_type_dic_col_name="temp_prop_type_dict"),
            axis=1,
        )
        df_prop = df_prop.drop(columns=["temp_prop_type_dict"])
        df_prop[PropertyStructure.IS_REQUIRED] = df_prop[PropertyStructure.IS_REQUIRED].map(
            lambda s: self._get_property_field_is_required(s)
        )
        df_prop[PropertyStructure.IS_UNIQUE] = df_prop[PropertyStructure.IS_REQUIRED].map(
            lambda s: self._get_property_field_is_unique(s)
        )  # TODO: base using is_req to determine both this and above

        return df_prop

    def _get_property_field_is_required(self, s: str) -> bool:
        """Infers the is_required property field from string.

        Args:
            s (str): cfihos field with the is required information
        Raises:
            KeyError: If provided string value is unknown to mapping logic
        Returns:
            str: True if field is required, else False.
        """
        mapper = {
            False: False,
            True: True,
            "Optional": False,
            "Mandatory": True,
            "Identifier": True,
        }
        if s not in mapper:
            raise KeyError(f"Could not map property field 'is required field' - '{s}'")
        return mapper[s]

    def _get_property_field_is_unique(self, s: str | bool) -> bool:
        """Infers the is unique property field from string.

        Args:
            s (str | bool): cfihos field with the is unique information
        Raises:
            KeyError: If provided string value is unknown to mapping logic
        Returns:
            str: True if field is unique, else False.
        """
        if isinstance(s, bool):
            return s

        mapper = {
            "Optional": False,
            "Mandatory": False,
            "Identifier": True,
        }
        if s not in mapper:
            raise KeyError(f"Could not map cfihos is unique field - '{s}'")
        return mapper[s]

    def _get_property_field_type(self, s: str | None) -> dict[str, str]:
        if s is None or not s:
            return {"type": "BASIC_DATA_TYPE"}
        else:
            return {"type": "ENTITY_RELATION", "pointsTo": s}

    def _get_property_field_target_type(self, property_dict: dict, temp_prop_type_dic_col_name: str):
        # TODO: Check this logic - as of now we assume a string value for all entity relations
        raw_target_type = property_dict[PropertyStructure.TARGET_TYPE]
        prop_type = property_dict[temp_prop_type_dic_col_name]

        if prop_type["type"] == "ENTITY_RELATION":
            if property_dict[PropertyStructure.UOM]:
                return property_dict[PropertyStructure.UOM]
            elif property_dict[PropertyStructure.ENUMERATION_TABLE]:
                return property_dict[PropertyStructure.ENUMERATION_TABLE]
            else:
                return self._map_entity_id_to_dms_id[
                    self._map_entity_name_to_entity_id[prop_type["pointsTo"].replace("  ", " ")]
                ]

        if isinstance(raw_target_type, float) and np.isnan(raw_target_type):
            self._loggingError(f"Error in target type conversion: {raw_target_type}. A string type shall be assigned.")
            self._loggingError(f"Property dict:\n{property_dict}")
            raw_target_type = "Text"

        if raw_target_type.startswith("Text,"):
            raw_target_type = "Text"

        target_type_converter = {
            "Text": "String",
            "Date": "Timestamp",
            "Boolean (Yes/No)": "Boolean",
            "Decimal (10)": "Float32",
            "Integer": "Int",
            "NUM": "Float32",
            "Boolean": "Boolean",
            "Number": "Float32",
        }
        try:
            return target_type_converter[raw_target_type]
        except KeyError as e:
            raise KeyError(f"Missing conversion for '{raw_target_type}'") from e

    def _assign_rev_through_property(self, df_prop: pd.DataFrame) -> pd.DataFrame:
        """Assigns the reverse through property to the property DataFrame.

        The reverse through property is assigned to the property ID if it is not empty.

        Args:
            df_prop (pd.DataFrame): The property DataFrame

        """
        df_prop.loc[df_prop[PropertyStructure.REV_THROUGH_PROPERTY] != "", PropertyStructure.REV_THROUGH_PROPERTY] = (
            df_prop[PropertyStructure.ID]
        )
        return df_prop

    def _create_reverse_direct_relations(self, relations: pd.DataFrame) -> pd.DataFrame:
        """Creates a missing direct relation based on a reverse relation.

        Properties
        isRequired, firstClassCitizen, unitOfMeasure, enumerationTableName, isUnique
        remain the same as in the provided Reverse Direct Relation.

        Args:
            relations (pd.DataFrame): The reverse relation

        Returns:
            pd.DataFrame: The missing direct relation
        """
        missing_direct_relation = relations.copy()

        missing_direct_relation[EntityStructure.ID] = relations[PropertyStructure.TARGET_TYPE].map(
            self._map_dms_id_to_entity_id
        )
        missing_direct_relation[EntityStructure.NAME] = relations["temp_prop_type_dict"].apply(lambda x: x["pointsTo"])
        missing_direct_relation[PropertyStructure.ID] += "_" + relations[EntityStructure.ID].apply(
            lambda id: id.split("-")[-1]
        )
        missing_direct_relation[PropertyStructure.NAME] = relations[PropertyStructure.REV_PROPERTY_NAME]
        missing_direct_relation[PropertyStructure.PROPERTY_TYPE] = Relations.REVERSE
        missing_direct_relation[PropertyStructure.DESCRIPTION] = relations[PropertyStructure.REV_PROPERTY_DESCRIPTION]
        missing_direct_relation[PropertyStructure.REV_THROUGH_PROPERTY] = relations[PropertyStructure.ID]
        missing_direct_relation[PropertyStructure.MULTI_VALUED] = True
        missing_direct_relation[PropertyStructure.TARGET_TYPE] = relations[EntityStructure.ID].map(
            self._map_entity_id_to_dms_id
        )
        missing_direct_relation[PropertyStructure.UNIQUE_VALIDATION_ID] = (
            missing_direct_relation[EntityStructure.ID] + missing_direct_relation[PropertyStructure.ID]
        )

        return missing_direct_relation

    def _add_property_rows(self, df_prop: pd.DataFrame, properties_to_add: pd.DataFrame) -> pd.DataFrame:
        """Adds property rows to the entity properties DataFrame.

        Args:
            df_prop (pd.DataFrame): The entity properties DataFrame
            properties_to_add (pd.DataFrame): The properties to add

        Returns:
            pd.DataFrame: The updated DataFrame, with the property rows added
        """
        try:
            self._loggingInfo(f"Appending {len(properties_to_add)} reverse direct relation properties")
            self._loggingDebug("\n" + ("\n".join(properties_to_add[PropertyStructure.ID])))
            df_prop = pd.concat([df_prop, properties_to_add], ignore_index=True)
        except Exception as e:
            self._loggingError(f"Error adding properties: {e}\nThe property rows will not be added.")

        return df_prop
