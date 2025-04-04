import copy
import re
from dataclasses import dataclass, field

import pandas as pd

from cognite.neat._cfihos.common.constants import CONTAINER_PROPERTY_LIMIT
from cognite.neat._cfihos.common.generic_classes import (
    DataSource,
    EntityStructure,
    PropertyStructure,
)
from cognite.neat._cfihos.common.log import log_init
from cognite.neat._cfihos.processing.cfihos.cfihos import CfihosProcessor

logging = log_init(f"{__name__}", "i")


@dataclass
class Processor:
    """
    Processor class for handling model processing.

    Attributes:
        model_processors_config (List[dict]): Configuration for model processors.
        custom_extended_properties (List[dict]): Custom extended properties.
    """

    # List of available processor
    model_processors_config: list[dict]

    model_processors: list[CfihosProcessor] = field(
        default_factory=list, init=False
    )  # Will become a List[Union[]] when/if new processor types are created

    # Dataframes containing all entities and properties of a given project model
    _df_entities: pd.DataFrame = field(default=None, init=False)
    _df_entity_properties: pd.DataFrame = field(
        default=None, init=False
    )  # will hold all the FCC properties in the FCC containers and single property per attribute in wide containers
    _df_properties_metadata: pd.DataFrame = field(default=None, init=False)

    # Model entities
    _model_entities: dict = field(default_factory=dict)
    _model_properties: dict = field(default_factory=dict)
    _model_property_groups: dict = field(default_factory=dict)

    _id_prefix_replace_filters = {"CFIHOS-": "_", "EPC-": "_"}

    _property_groupings: list = field(default_factory=list)

    # Available processors
    map_model_processor_type_to_processor_class = {"CFIHOS": CfihosProcessor}

    # Source of input data (CSVs, Github, CDF)
    source: DataSource = field(default=DataSource.default(), init=False)

    _map_entity_name_to_dms_name: dict = field(default_factory=dict, init=False)
    _map_entity_id_to_dms_id: dict = field(default_factory=dict, init=False)
    _map_entity_name_to_entity_id: dict = field(default_factory=dict, init=False)
    _map_dms_id_to_entity_id: dict = field(default_factory=dict, init=False)
    _map_entity_id_to_dms_name: dict = field(default_factory=dict, init=False)

    @property
    def model_entities(self):
        return self._model_entities

    @property
    def model_properties(self):
        return self._model_properties

    @property
    def model_property_groups(self):
        return self._model_property_groups

    @property
    def map_entity_id_to_dms_id(self):
        return self._map_entity_id_to_dms_id

    @property
    def map_dms_id_to_entity_id(self):
        return self._map_dms_id_to_entity_id

    def __post_init__(self):
        self._setup_model_processors()
        self._setup_property_groups()
        self._sync_processor_mapping_tables()

    def _setup_model_processors(self):
        for model_processor in self.model_processors_config:
            for model_processor_type, processor_data in model_processor.items():
                processor_data["processor_config_name"] = model_processor_type
                self._loggingInfo(f"Setting up {model_processor_type}")
                processor_engine = processor_data.pop("processor_engine")
                processor_obj = self.map_model_processor_type_to_processor_class.get(processor_engine)

                if processor_obj is None:
                    raise KeyError(f"Model Processor Type: {model_processor_type} is not supported")
                self.model_processors.append(processor_obj(**processor_data))

    def _setup_property_groups(self):
        # TODO: Hardcoded
        self._property_groupings = [f"CFIHOS_{idx}" for idx in range(0, 10)]
        self._property_groupings.append("EPC_")

    def _sync_processor_mapping_tables(self):
        """Synchronizes mapping tables across the processor to ensure global mapping between models.
        Updated mapping tables are:
         - map_entity_id_to_dms_id
         - map_dms_id_to_entity_id
         - map_entity_name_to_entity_id
        """
        if len(self.model_processors) == 0:
            self._loggingWarning("Processor received no models")
        for processor in self.model_processors:
            self._map_entity_id_to_dms_id.update(processor.entity_id_to_dms_id)
            self._map_dms_id_to_entity_id.update(processor.dms_id_to_entity_id)
            self._map_entity_name_to_entity_id.update(processor.entity_name_to_entity_id)

        for processor in self.model_processors:
            processor.entity_id_to_dms_id = self._map_entity_id_to_dms_id
            processor.dms_id_to_entity_id = self._map_dms_id_to_entity_id
            processor.entity_name_to_entity_id = self._map_entity_name_to_entity_id

    def _dict_key_exists(list_of_dicts, key):
        return any(key in d for d in list_of_dicts)

    def _create_property_row(
        self,
        property_item: dict,
        property_group=None,
        is_uom_variant=False,
        is_relationship_variant=False,
        is_custom_property=False,
        is_first_class_citzen=False,
        is_edge_property=False,
        target_type="String",
    ):
        """
        Unified method to handle property row creation with variations for UOM, relationship, and default properties.

        Parameters:
        - property_item: The property data (dictionary).
        - property_group: The property group for the property, if applicable.
        - is_uom_variant: Flag to indicate if this is a UOM variant.
        - is_relationship_variant: Flag to indicate if this is a relationship variant.
        - columns_to_check: Columns to check for specific properties, if applicable.

        Returns:
        A dictionary representing the property row.
        """
        # Base property row structure
        property_row = {
            PropertyStructure.ID: property_item[PropertyStructure.ID].replace("-", "_"),
            PropertyStructure.NAME: property_item.get(PropertyStructure.NAME, None),
            PropertyStructure.DESCRIPTION: property_item.get(PropertyStructure.DESCRIPTION, None),
            PropertyStructure.PROPERTY_TYPE: property_item.get(PropertyStructure.PROPERTY_TYPE, None),
            PropertyStructure.TARGET_TYPE: property_item[PropertyStructure.TARGET_TYPE]
            if PropertyStructure.TARGET_TYPE in property_item.keys()
            and property_item[PropertyStructure.TARGET_TYPE] != None
            else target_type,
            PropertyStructure.MULTI_VALUED: property_item.get(PropertyStructure.MULTI_VALUED, None),
            PropertyStructure.IS_REQUIRED: False,
            PropertyStructure.IS_UNIQUE: False,
            PropertyStructure.UOM: property_item.get(PropertyStructure.UOM, None),
            PropertyStructure.ENUMERATION_TABLE: property_item.get(PropertyStructure.ENUMERATION_TABLE, None),
            PropertyStructure.INHERITED: False,
            PropertyStructure.PROPERTY_GROUP: property_group,
            PropertyStructure.CUSTOM_PROPERTY: is_custom_property,
            PropertyStructure.FIRSTCLASSCITIZEN: is_first_class_citzen,  # lable the property if it is first class citizen
            EntityStructure.ID: property_item.get(EntityStructure.ID, None),
            PropertyStructure.UNIQUE_VALIDATION_ID: property_item[PropertyStructure.UNIQUE_VALIDATION_ID].replace(
                "-", "_"
            )
            if PropertyStructure.UNIQUE_VALIDATION_ID in property_item.keys()
            else None,
            "cfihosId": property_item[PropertyStructure.ID],
        }

        # Adjustments for UOM variant
        if is_uom_variant:
            property_row.update(
                {
                    PropertyStructure.ID: f"{property_item[PropertyStructure.ID].replace('-', '_')}_UOM",
                    PropertyStructure.NAME: f"{property_item[PropertyStructure.NAME]}_UOM",
                    PropertyStructure.DESCRIPTION: f"{property_item[PropertyStructure.DESCRIPTION]} unit of measure",
                    PropertyStructure.PROPERTY_TYPE: "BASIC_DATA_TYPE",
                    PropertyStructure.TARGET_TYPE: "String",
                    "cfihosId": f"{property_item[PropertyStructure.ID]}_UOM",
                }
            )

        # Adjustments for relationship variant
        if is_relationship_variant:
            property_row.update(
                {
                    PropertyStructure.ID: property_item[PropertyStructure.ID].rstrip("_rel"),
                    PropertyStructure.UNIQUE_VALIDATION_ID: property_item[
                        PropertyStructure.UNIQUE_VALIDATION_ID
                    ].rstrip("_rel"),
                    PropertyStructure.PROPERTY_TYPE: "BASIC_DATA_TYPE",
                    PropertyStructure.TARGET_TYPE: "String",
                    "cfihosId": property_item[PropertyStructure.ID].rstrip("_rel"),
                }
            )

        # Added for edge support
        if is_edge_property:
            property_row.update(
                {
                    PropertyStructure.EDGE_EXTERNAL_ID: property_item[PropertyStructure.EDGE_EXTERNAL_ID].replace(
                        "-", "_"
                    ),
                    PropertyStructure.EDGE_SOURCE: property_item[PropertyStructure.EDGE_SOURCE].replace("-", "_"),
                    PropertyStructure.EDGE_TARGET: property_item[PropertyStructure.EDGE_TARGET].replace("-", "_"),
                    PropertyStructure.EDGE_DIRECTION: property_item[PropertyStructure.EDGE_DIRECTION],
                }
            )

        return property_row

    def process_and_collect_models(self):
        """
        Processes and collects data models from multiple model processors. This function aggregates entities, properties,
        and properties metadata from different processors, validates them for uniqueness, and prepares them for further
        processing.

        This method performs the following steps:
        - Processes data from each model processor and collects entities, properties, and properties metadata.
        - Ensures the uniqueness of entity IDs and property validation IDs.
        - Filters and combines metadata with entity properties.
        - Adds string properties for remaining `_rel` properties.
        - Prepares the final data model by creating model properties and entities, and extending first-class citizen properties.

        Returns:
            None
        """
        list_of_entities = []
        list_of_properties = []
        list_of_properties_metadata = []

        for processor in self.model_processors:
            (
                df_processor_entities,
                df_processor_properties,
                df_processor_properties_metadata,
            ) = processor.process()

            # TODO: Validate dfs according to req. columns
            # Add processor name to id to check for uniqueness
            df_processor_properties_metadata["unique_val_id"] = (
                df_processor_properties_metadata[PropertyStructure.ID] + f"_metadata_{processor.processor_config_name}"
            )
            list_of_entities.append(df_processor_entities)
            list_of_properties.append(df_processor_properties)
            list_of_properties_metadata.append(df_processor_properties_metadata)

        self._df_entities = pd.concat(list_of_entities)
        self._df_entity_properties = pd.concat(list_of_properties)
        self._df_properties_metadata = pd.concat(list_of_properties_metadata)

        self._df_entity_properties.loc[
            self._df_entity_properties[EntityStructure.ID].isin(
                self._df_entities.loc[self._df_entities[EntityStructure.FIRSTCLASSCITIZEN] == True, EntityStructure.ID]
            ),
            EntityStructure.FIRSTCLASSCITIZEN,
        ] = True

        if self._df_entities[EntityStructure.ID].is_unique is False:
            duplicated_entities = self._df_entities[self._df_entities.duplicated([EntityStructure.ID], keep=False)][
                EntityStructure.ID
            ].values
            raise ValueError(f"Processed Entities has overlapping ids. Duplicated entity ids {duplicated_entities}")

        if self._df_entity_properties[PropertyStructure.UNIQUE_VALIDATION_ID].is_unique is False:
            duplicated_entities_props = self._df_entity_properties[
                self._df_entity_properties.duplicated([PropertyStructure.UNIQUE_VALIDATION_ID], keep=False)
            ][PropertyStructure.UNIQUE_VALIDATION_ID].values
            raise ValueError(
                f"Processed Properties has overlapping entity-property-ids. Duplicated entity ids {duplicated_entities_props}"
            )

        # Keep only properties metadata rows that do not exist in entity properties
        self._df_properties_metadata = self._df_properties_metadata[
            ~self._df_properties_metadata[PropertyStructure.ID].isin(self._df_entity_properties[PropertyStructure.ID])
        ]

        # Add properties from metadata that are not already in the entity properties df
        self._df_entity_properties = pd.concat(
            [self._df_entity_properties, self._df_properties_metadata], ignore_index=True
        )

        # set FIRSTCLASSCITIZEN column to False where value is NaN
        self._df_entity_properties[PropertyStructure.FIRSTCLASSCITIZEN] = (
            self._df_entity_properties[PropertyStructure.FIRSTCLASSCITIZEN].fillna(False).astype(bool)
        )

        # Add string property for remaining _rel properties
        list_new_rows = []
        for _, prop_rel in self._df_entity_properties.loc[
            (self._df_entity_properties[PropertyStructure.ID].str.endswith("_rel"))
        ].iterrows():
            if prop_rel[PropertyStructure.ID].rstrip("_rel") not in self._df_entity_properties[PropertyStructure.ID]:
                new_row = self._create_property_row(
                    prop_rel,
                    is_first_class_citzen=prop_rel[PropertyStructure.FIRSTCLASSCITIZEN],
                    is_relationship_variant=True,
                )

                list_new_rows.append(new_row)
        df_new_rows = pd.DataFrame(list_new_rows)
        self._df_entity_properties = pd.concat([self._df_entity_properties, df_new_rows], ignore_index=True)

        self._create_model_properties()
        self._create_model_entities()
        self._extend_first_class_citizens_model_properties()

    def get_property_group_from_id(self, property: dict):
        property_id = property[PropertyStructure.ID].replace("-", "_")
        return self._model_properties[property_id][PropertyStructure.PROPERTY_GROUP]

    def _create_model_properties(self):
        """
        Creates and validates model properties from the collected entity properties. This function processes the entity
        properties DataFrame, checks for consistency, and constructs a DataFrame of unique model properties.

        This method performs the following steps:
        - Extracts unique properties from the entity properties DataFrame.
        - Validates that each property has consistent attribute values across non-first-class citizen entries.
        - Constructs property rows and appends them to a list of properties.
        - Converts the list of properties into a DataFrame and updates the model properties dictionary.

        Returns:
            None
        """
        properties = []
        unique_properties = self._df_entity_properties[PropertyStructure.ID].unique()
        # Check that all target types are present
        for prop in unique_properties:
            df_property_subset = self._df_entity_properties.loc[
                (self._df_entity_properties[PropertyStructure.ID] == prop)
                & (self._df_entity_properties[PropertyStructure.FIRSTCLASSCITIZEN] == False)
            ]
            df_property_subset_groups = df_property_subset.groupby(
                PropertyStructure.PROPERTY_TYPE
            )  # Note: If other than basic or entity appears, this breaks
            for idx, df_subset in df_property_subset_groups:
                if len(df_subset) > 0:
                    columns_to_check = {
                        PropertyStructure.NAME: df_subset[PropertyStructure.NAME].unique(),
                        PropertyStructure.TARGET_TYPE: df_subset[PropertyStructure.TARGET_TYPE].unique()
                        if idx == "BASIC_DATA_TYPE"
                        else [None],
                        PropertyStructure.PROPERTY_TYPE: df_subset[PropertyStructure.PROPERTY_TYPE].unique(),
                        PropertyStructure.MULTI_VALUED: df_subset[PropertyStructure.MULTI_VALUED].unique(),
                    }
                    for col_name, data in columns_to_check.items():
                        # validate duplicate non fcc properties
                        if len(data) != 1:
                            raise ValueError(f"Found properties '{col_name}' with lacking or multiple values: {data}")
                    prop_row = {PropertyStructure.ID: prop.replace("-", "_")}
                    if columns_to_check:
                        for key, value in columns_to_check.items():
                            if key not in [PropertyStructure.FIRSTCLASSCITIZEN, PropertyStructure.UNIQUE_VALIDATION_ID]:
                                prop_row[key] = value[0]

                    properties.append(self._create_property_row(prop_row))

        self._df_properties = pd.DataFrame(data=properties)
        self._add_property_groups()
        self._df_properties.set_index(PropertyStructure.ID, drop=False, inplace=True)
        self._model_properties.update(self._df_properties.to_dict("index"))

    def _extend_first_class_citizens_model_properties(self):
        """
        Extends the model properties with first-class citizen properties. This function processes the first-class citizen
        properties from the entity properties DataFrame, validates them for consistency, and appends them to the model properties.

        This method performs the following steps:
        - Identifies first-class citizen properties from the entity properties DataFrame.
        - Validates that each property has consistent attribute values across entries.
        - Constructs property rows and appends them to a list of properties.
        - Converts the list of properties into a DataFrame and updates the model properties dictionary.

        Returns:
            None
        """
        properties = []
        fcc_properties = self._df_entity_properties.loc[
            self._df_entity_properties[PropertyStructure.FIRSTCLASSCITIZEN] == True
        ]
        # Check that all target types are present
        for _, prop in fcc_properties.iterrows():
            df_property_subset = self._df_entity_properties.loc[
                (
                    self._df_entity_properties[PropertyStructure.UNIQUE_VALIDATION_ID]
                    == prop[PropertyStructure.UNIQUE_VALIDATION_ID]
                )
            ]
            df_property_subset_groups = df_property_subset.groupby(
                PropertyStructure.PROPERTY_TYPE
            )  # Note: If other than basic or entity appears, this breaks
            for idx, df_subset in df_property_subset_groups:
                if len(df_subset) > 0:
                    columns_to_check = {
                        PropertyStructure.NAME: df_subset[PropertyStructure.NAME].unique(),
                        PropertyStructure.TARGET_TYPE: df_subset.loc[
                            df_subset[PropertyStructure.FIRSTCLASSCITIZEN] == True
                        ][PropertyStructure.TARGET_TYPE].unique()
                        if idx == "BASIC_DATA_TYPE"
                        else [None],
                        PropertyStructure.PROPERTY_TYPE: df_subset[PropertyStructure.PROPERTY_TYPE].unique(),
                        PropertyStructure.MULTI_VALUED: df_subset[PropertyStructure.MULTI_VALUED].unique(),
                        PropertyStructure.UNIQUE_VALIDATION_ID: df_subset[PropertyStructure.UNIQUE_VALIDATION_ID],
                    }
                    for col_name, data in columns_to_check.items():
                        if len(data) != 1:
                            raise ValueError(f"Found properties '{col_name}' with lacking or multiple values: {data}")

                if columns_to_check:
                    for key, value in columns_to_check.items():
                        if key not in [PropertyStructure.FIRSTCLASSCITIZEN, PropertyStructure.UNIQUE_VALIDATION_ID]:
                            prop[key] = value[0]

                    properties.append(
                        self._create_property_row(
                            prop,
                            property_group=prop[EntityStructure.ID].replace("-", "_"),
                            is_first_class_citzen=True,
                        )
                    )

        pd_frist_class_properties = pd.DataFrame(data=properties)
        pd_frist_class_properties.set_index(PropertyStructure.UNIQUE_VALIDATION_ID, drop=False, inplace=True)
        self._model_properties.update(pd_frist_class_properties.to_dict("index"))

    def _create_model_entities(self):
        """
        Creates model entities from the collected entity data. This function processes the entity DataFrame, validates them for
        uniqueness, maps entity IDs, and constructs a dictionary of entities with their properties.

        This method performs the following steps:
        - Iterates through the entities DataFrame and constructs a dictionary of entities.
        - Validates that each entity and its properties have unique IDs.
        - Maps entity IDs from _map_entity_id_to_dms_id and constructs property rows for each entity.
        - Adds custom extended search properties from the configuration file (if enabled).
        - Adds inherited properties to the entities.
        - Regroups and updates model properties after adding UOM properties.

        Returns:
            None
        """
        entities = {}

        for _, row in self._df_entities.iterrows():
            unique_entity_id = row[EntityStructure.ID]
            # Check for duplicates
            if unique_entity_id in entities:
                raise ValueError(f"Found duplicate cfihos entity id: {unique_entity_id}")

            entities[unique_entity_id] = {
                EntityStructure.ID: self._map_entity_id_to_dms_id[row[EntityStructure.ID]],
                EntityStructure.NAME: row[EntityStructure.NAME],
                EntityStructure.DESCRIPTION: row[EntityStructure.DESCRIPTION],
                EntityStructure.INHERITS_FROM_ID: [
                    self._map_entity_id_to_dms_id[parent_id] for parent_id in row[EntityStructure.INHERITS_FROM_ID]
                ]
                if row[EntityStructure.INHERITS_FROM_ID] is not None
                else None,
                EntityStructure.INHERITS_FROM_NAME: row[EntityStructure.INHERITS_FROM_NAME],
                EntityStructure.FULL_INHERITANCE: {},
                "cfihosType": row["type"],
                "cfihosId": row[EntityStructure.ID],
                EntityStructure.PROPERTIES: [],
                EntityStructure.FIRSTCLASSCITIZEN: True if row[EntityStructure.FIRSTCLASSCITIZEN] else False,
            }

            cur_entity_prop_ids = {}
            cur_fcc_entity_prop_ids = {}

            for _, prop_row in self._df_entity_properties[
                (self._df_entity_properties[EntityStructure.ID] == row[EntityStructure.ID])
            ].iterrows():
                # Check for duplicates
                if (
                    not prop_row[PropertyStructure.FIRSTCLASSCITIZEN]
                    and prop_row[PropertyStructure.ID] in cur_entity_prop_ids
                ):
                    raise ValueError(
                        f"Found duplicate property id '{prop_row[PropertyStructure.ID]}' in {unique_entity_id}"
                    )
                if (
                    prop_row[PropertyStructure.FIRSTCLASSCITIZEN]
                    and prop_row[PropertyStructure.ID] in cur_fcc_entity_prop_ids
                ):
                    raise ValueError(
                        f"Found duplicate property id '{prop_row[PropertyStructure.ID]}' in FCC {unique_entity_id}"
                    )
                if prop_row[PropertyStructure.FIRSTCLASSCITIZEN]:
                    cur_fcc_entity_prop_ids[prop_row[PropertyStructure.ID]] = 1
                else:
                    cur_entity_prop_ids[prop_row[PropertyStructure.ID]] = 1

                if prop_row[PropertyStructure.PROPERTY_TYPE] == "ENTITY_RELATION":
                    if self._map_dms_id_to_entity_id.get(prop_row[PropertyStructure.TARGET_TYPE], False) is False:
                        logging.warning(
                            f"[WARNING] Could not map target property "
                            f"{prop_row[PropertyStructure.TARGET_TYPE]} for {row[EntityStructure.ID]}"
                        )
                        continue

                property_group = ""
                if row[EntityStructure.FIRSTCLASSCITIZEN]:
                    property_group = prop_row[EntityStructure.ID].replace("-", "_")
                else:
                    # Generate dms friendly property name, while ensuring that the CFIHOS ID is preserved
                    property_group = self.get_property_group_from_id(prop_row)

                # NOTE: We are simplifying UOM for now in CFIHOS by having propertyId holding value and propertyIdUoM holding the corresponding UOM value
                if prop_row[PropertyStructure.UOM]:
                    property_row_uom = self._create_property_row(
                        prop_row,
                        property_group=property_group,
                        is_first_class_citzen=row[EntityStructure.FIRSTCLASSCITIZEN],
                        is_uom_variant=True,
                    )

                    self._model_properties[f"{prop_row[PropertyStructure.ID].replace('-', '_')}_UOM"] = property_row_uom
                    self._model_property_groups.setdefault(property_group, []).append(property_row_uom)

                    # # check if the UOM property is a UOM (This is a rare or none existing case as enities don't have UOMs)
                    # if prop_row[PropertyStructure.FIRSTCLASSCITIZEN]:
                    #     property_row_uom[PropertyStructure.PROPERTY_GROUP] = prop_row[EntityStructure.ID]
                    # entities[unique_entity_id][EntityStructure.PROPERTIES].append(property_row_uom)

                target_type = self._map_entity_id_to_dms_name.get(
                    prop_row[PropertyStructure.TARGET_TYPE],
                    prop_row[PropertyStructure.TARGET_TYPE],
                )
                property_row = self._create_property_row(
                    prop_row,
                    property_group=property_group,
                    is_first_class_citzen=row[EntityStructure.FIRSTCLASSCITIZEN],
                    is_edge_property=True
                    if prop_row[PropertyStructure.PROPERTY_TYPE] == PropertyStructure.ENTITY_EDGE
                    else False,
                    target_type=target_type,
                )

                self._model_property_groups.setdefault(property_group, []).append(property_row)
                entities[unique_entity_id][EntityStructure.PROPERTIES].append(property_row)

        self._add_inherited_properties(entities)
        self._model_entities = entities

        # Regroup model and entity properties after adding UOM properties
        self._df_properties = pd.DataFrame(
            data=self._model_properties.values(), columns=list(self._model_properties.values())[0].keys()
        )
        self._add_property_groups(CONTAINER_PROPERTY_LIMIT)
        self._regroup_properties(CONTAINER_PROPERTY_LIMIT)
        self._model_properties.update(self._df_properties.to_dict("index"))

    # Custom function to extract numeric part of the string
    def _extract_property_numeric_part(self, property):
        # This regular expression matches the first group of one or more digits in the string
        matches = re.search(r"\d+", property)
        if matches:
            return int(matches.group())
        else:
            return 0  # Return 0 if no number is found

    def _add_property_groups(self, container_property_limit: int = 100) -> None:
        """
        Group none FCC properties into groups of 100
        Example: CFIHOS_1_10000001_10000101, CFIHOS_4_40000001_40000101, etc.
        """
        for property_group_prefix in self._property_groupings:
            df_property_group = self._df_properties.loc[
                (self._df_properties[PropertyStructure.ID].str.startswith(property_group_prefix))
                & (self._df_properties[PropertyStructure.FIRSTCLASSCITIZEN] == False)
            ].copy(deep=True)
            # Not all potential groups will necessarily exist, if so we simply continue
            if len(df_property_group) == 0:
                continue

            # df_property_group["numeric_property"] = df_property_group[PropertyStructure.ID].apply(
            #     self._extract_property_numeric_part
            # )
            df_property_group["numeric_property"] = df_property_group[PropertyStructure.ID].apply(
                self._extract_property_numeric_part
            )
            df_property_group = df_property_group.sort_values(by="numeric_property")
            # df_property_group = df_property_group.sort_values(by=[PropertyStructure.ID])
            property_extention_suffix_list = ["_rel", "_uom"]
            for prop_id in df_property_group[PropertyStructure.ID]:
                id_number = int(self._get_property_id_number(prop_id))
                if id_number % container_property_limit == 0:
                    property_group_suffix = f"{id_number - (id_number - 1) % container_property_limit}_{id_number - (id_number - 1) % container_property_limit + container_property_limit}"
                else:
                    property_group_suffix = f"{id_number - id_number % container_property_limit + 1}_{id_number - id_number % container_property_limit + container_property_limit + 1}"

                property_group_suffix += (
                    "_ext" if any(prop_id.lower().endswith(ext) for ext in property_extention_suffix_list) else ""
                )
                self._df_properties.loc[
                    self._df_properties[PropertyStructure.ID] == prop_id, PropertyStructure.PROPERTY_GROUP
                ] = (
                    f"{property_group_prefix}{property_group_suffix}"
                    if property_group_prefix == "EPC_"
                    else f"{property_group_prefix}_{property_group_suffix}"
                )

    def _regroup_properties(self, container_property_limit: int = 100) -> None:
        """
        Regroup properties into groups of CONTAINER_PROPERTY_LIMIT
        Property group names are suffixed with _1, _2, _3, etc.
        :param container_property_limit: Number of properties per group. Default is 100.
        """

        self._df_properties.set_index(PropertyStructure.ID, drop=False, inplace=True)
        property_groups = (
            self._df_properties.loc[
                (self._df_properties[PropertyStructure.FIRSTCLASSCITIZEN] == False)
                & (self._df_properties[PropertyStructure.CUSTOM_PROPERTY] == False)
            ]
            .groupby(PropertyStructure.PROPERTY_GROUP)
            .groups
        )
        property_groups = {
            f"{key}_{i // container_property_limit + 1}" if i > 1 else key: sorted(x for x in list(properties))[
                i : i + container_property_limit
            ]
            for key, properties in property_groups.items()
            for i in range(0, len(properties), container_property_limit)
        }
        for property_group, properties in property_groups.items():
            for prop_id in properties:
                self._df_properties.loc[
                    (self._df_properties[PropertyStructure.ID] == prop_id), PropertyStructure.PROPERTY_GROUP
                ] = property_group

        # Update model entities with new property groups
        for entity in self._model_entities.values():
            for prop in entity[EntityStructure.PROPERTIES]:
                if (
                    prop[PropertyStructure.FIRSTCLASSCITIZEN] == False
                    and prop[PropertyStructure.CUSTOM_PROPERTY] == False
                ):
                    prop[PropertyStructure.PROPERTY_GROUP] = self._df_properties.loc[
                        prop[PropertyStructure.ID], PropertyStructure.PROPERTY_GROUP
                    ]

    def _get_property_id_number(self, property_id: str) -> str:
        property_id_number = re.findall(r"\d+", property_id)[0]
        return property_id_number

    def _dfs(self, parent_ids, entities, property_dict, entity, level):
        for parent_entity_id in parent_ids:
            entity[EntityStructure.FULL_INHERITANCE].setdefault(level, []).append(parent_entity_id)
            parent_properties = {
                prop[PropertyStructure.ID]: prop
                for prop in copy.deepcopy(entities[parent_entity_id.replace("_", "-")][EntityStructure.PROPERTIES])
            }
            for prop in parent_properties.values():
                prop[PropertyStructure.INHERITED] = True
                prop[PropertyStructure.INHERITED_FROM] = parent_entity_id

            # TODO: Ideally one should raise an error if child holds parent property
            # but CFIHOS is not consistent enough.
            property_dict.update(parent_properties)

            parents = entities[parent_entity_id.replace("_", "-")][EntityStructure.INHERITS_FROM_ID]
            if parents:
                self._dfs(parents, entities, property_dict, entity, level=level + 1)

    def _add_inherited_properties(self, entities: dict):
        """
        Adds inherited properties to the entities. This function recursively traverses the inheritance hierarchy using depth-first search (DFS) and
        collects properties from parent entities, adding them to the child entities.

        Args:
            entities (dict): A dictionary containing entity information, keyed by entity ID. Each entity is expected to
                            have a list of properties and a list of parent entity IDs from which it inherits properties.

        Returns:
            None
        """
        for _, entity in entities.items():
            property_dict = {prop[PropertyStructure.ID]: prop for prop in entity[EntityStructure.PROPERTIES]}
            if parents := entity[EntityStructure.INHERITS_FROM_ID]:
                self._dfs(parents, entities, property_dict, entity, level=1)

            entity[EntityStructure.PROPERTIES] = list(property_dict.values())

    def _get_property_field_type(self, s: str) -> dict:
        if s is None or len(s) == 0:
            return {"type": "BASIC_DATA_TYPE"}
        else:
            return {"type": "ENTITY_RELATION", "pointsTo": s}

    def _replace_id_prefix_func(self, s: str) -> str:
        """raplaces id_prefixes with defined replacements strings from a string according to 'id_prefix_replace_filters'

        Args:
            s (str): String to be filtered

        Returns:
            str: A filtered string according to the defined id_prefix filters
        """
        for replace_str, replacement_str in self._id_prefix_replace_filters.items():
            s = s.replace(replace_str, replacement_str)
        return s

    def _loggingDebug(self, msg: str) -> None:
        logging.debug(f"[Model Processor] {msg}")

    def _loggingInfo(self, msg: str) -> None:
        logging.info(f"[Model Processor] {msg}")

    def _loggingWarning(self, msg: str) -> None:
        logging.warning(f"[Model Processor] {msg}")

    def _loggingError(self, msg: str) -> None:
        logging.error(f"[Model Processor] {msg}")

    def _loggingCritial(self, msg: str) -> None:
        logging.critical(f"[Model Processor] {msg}")
