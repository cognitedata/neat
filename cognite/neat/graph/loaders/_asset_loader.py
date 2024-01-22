import logging
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, fields
from datetime import datetime
from itertools import groupby
from typing import Any, Literal, overload

from cognite.client import CogniteClient
from cognite.client.data_classes import AssetWrite, LabelDefinitionWrite, RelationshipWrite, RelationshipWriteList
from pydantic_core import ErrorDetails
from rdflib.query import ResultRow

from cognite.neat.graph.stores import NeatGraphStoreBase
from cognite.neat.rules.models import Rules
from cognite.neat.rules.models.rules import Property
from cognite.neat.utils import remove_namespace
from cognite.neat.utils.utils import epoch_now_ms

from ._base import CogniteLoader

if sys.version_info >= (3, 11):
    from datetime import UTC
else:
    from datetime import timezone

    UTC = timezone.utc

METADATA_VALUE_MAX_LENGTH = 5120


@dataclass(frozen=True)
class AssetLoaderMetadataKeys:
    """Class holding mapping between NEAT metadata key names and their desired names
    in CDF Asset metadata

    Args:
        start_time: Start time key name
        end_time: End time key name
        update_time: Update time key name
        resurrection_time: Resurrection time key name
        identifier: Identifier key name
        active: Active key name
        type: Type key name
    """

    start_time: str = "start_time"
    end_time: str = "end_time"
    update_time: str = "update_time"
    resurrection_time: str = "resurrection_time"
    identifier: str = "identifier"
    active: str = "active"
    type: str = "type"

    def as_aliases(self) -> dict[str, str]:
        return {str(field.default): getattr(self, field.name) for field in fields(self)}


AssetResource = AssetWrite | RelationshipWrite | LabelDefinitionWrite


class AssetLoader(CogniteLoader[AssetResource]):
    """The Asset Loader is used to load a triple store into the CDF core Asset Hierarchy model.

    Args:
        rules: The transformation rules to use
        graph_store: The graph store to load from
        data_set_id: The data set id to load into
        label_data_set_id: The data set id to load labels into. If not set, the same as data_set_id will be used.
        use_orphanage: Whether to use an orphanage for assets without a parent
        use_labels: Whether to use labels attached to the assets and relationships.
        asset_external_id_prefix: Prefix to add to all external ids
        default_metadata_value: Default metadata value to use for assets without a value. If set to None,
            the metadata key will be omitted. Setting this to an empty string will set the metadata key to an empty
             string, thus ensuring that all assets have the metadata keys.
        metadata_keys: Metadata key names to use
        always_store_in_metadata: Whether to store all properties in metadata. This will be the same as setting
            resource_type_property to metadata for all properties. For example, if you have the property `Terminal.name`
            set with resource_type_property = ["name"], then the property will be stored in metadata as
            `Terminal.name=<Value>`. This also includes properties that are relationships.
    """

    # This is guaranteed ot be in the data
    _identifier: str = "identifier"
    # This label is added to all assets if use_labels is True
    _non_historic_label: str = "non-historic"

    def __init__(
        self,
        rules: Rules,
        graph_store: NeatGraphStoreBase,
        data_set_id: int,
        label_data_set_id: int | None = None,
        use_orphanage: bool = True,
        use_labels: bool = True,
        asset_external_id_prefix: str | None = None,
        default_metadata_value: str | None = "",
        metadata_keys: AssetLoaderMetadataKeys | None = None,
        always_store_in_metadata: bool = False,
    ):
        super().__init__(rules, graph_store)
        self._data_set_id = data_set_id
        self._label_data_set_id = label_data_set_id or data_set_id
        self._use_labels = use_labels
        self._use_orphanage = use_orphanage
        self._orphanage_external_id = (
            f"{asset_external_id_prefix or ''}orphanage-{data_set_id}" if use_orphanage else None
        )
        self._asset_external_id_prefix = asset_external_id_prefix
        self._default_metadata_value = default_metadata_value
        self._metadata_keys = metadata_keys or AssetLoaderMetadataKeys()
        # This is used in a hot loop, so we cache it
        self._metadata_key_aliases = self._metadata_keys.as_aliases()
        self._always_store_in_metadata = always_store_in_metadata

        # State:
        self._loaded_assets: set[str] = set()
        self._loaded_labels: set[str] = set()

    @overload
    def load(self, stop_on_exception: Literal[True]) -> Iterable[AssetResource]:
        ...

    @overload
    def load(self, stop_on_exception: Literal[False] = False) -> Iterable[AssetResource | ErrorDetails]:
        ...

    def load(self, stop_on_exception: bool = False) -> Iterable[AssetResource | ErrorDetails]:
        if self.rules.metadata.namespace is None:
            raise ValueError("Namespace must be provided in transformation rules!")
        namespace = self.rules.metadata.namespace

        properties_by_class_name: dict[str, list[Property]] = defaultdict(list)
        for prop in self.rules.properties.values():
            properties_by_class_name[prop.class_id].append(prop)

        if self._use_labels:
            self._loaded_labels.add(self._non_historic_label)
            yield LabelDefinitionWrite(
                external_id=self._non_historic_label, name=self._non_historic_label, data_set_id=self._label_data_set_id
            )

        # Todo Extend rules to sort topological sorting to ensure that parents are loaded before children
        counter = 0
        for class_name in self.rules.classes.keys():
            if self._use_labels:
                self._loaded_labels.add(class_name)
                yield LabelDefinitionWrite(external_id=class_name, name=class_name, data_set_id=self._label_data_set_id)

            class_uri = namespace[class_name]
            logging.debug(f"Processing class <{class_uri}>.")

            try:
                result = self.graph_store.queries.list_instances_of_type(class_uri)
            except Exception as e:
                logging.error(f"Error while querying for instances of class <{class_uri}> into cache. Reason: {e}")
                if stop_on_exception:
                    raise e
                yield ErrorDetails(
                    input={"class_uri": class_uri},
                    loc=("AssetLoader", "load"),
                    msg=f"Error while querying instances of class <{class_uri}> into cache. Reason: {e}",
                    type=f"Exception of type {type(e).__name__} occurred when processing instance of {class_name}",
                )
                continue

            logging.debug(f"Class <{class_name}> has {len(result)} instances")

            for instance_uri, properties_values in groupby(result, lambda x: x[0]):
                instance_id = remove_namespace(instance_uri)
                values_by_property = self._prepare_instance_data(instance_id, properties_values)
                try:
                    asset = self._load_asset(
                        properties_by_class_name[class_name],
                        values_by_property,
                        instance_id,
                        class_name,
                    )
                except Exception as e:
                    logging.error(f"Error while loading asset from instance <{instance_id}>. Reason: {e}")
                    if stop_on_exception:
                        raise e
                    yield ErrorDetails(
                        input={"instance_id": instance_id},
                        loc=("AssetLoader", "load"),
                        msg=f"Error while loading asset from <{instance_id}>. Reason: {e}",
                        type=f"Exception of type {type(e).__name__} occurred when processing instance of {class_name}",
                    )
                    continue
                else:
                    # We know that external_id is always set
                    self._loaded_assets.add(asset.external_id)  # type: ignore[arg-type]
                    yield asset

                try:
                    relationships = self._load_relationships(
                        properties_by_class_name[class_name],
                        values_by_property,
                        remove_namespace(instance_id),
                        class_name,
                    )
                except Exception as e:
                    logging.error(f"Error while loading relationships from instance <{instance_id}>. Reason: {e}")
                    if stop_on_exception:
                        raise e
                    yield ErrorDetails(
                        input={"instance_id": instance_id},
                        loc=("AssetLoader", "load"),
                        msg=f"Error while loading relationships from <{instance_id}>. Reason: {e}",
                        type=f"Exception of type {type(e).__name__} occurred when processing instance of {class_name}",
                    )
                    continue
                else:
                    for relationship in relationships:
                        for label in relationship.labels or []:
                            if label.external_id and label.external_id not in self._loaded_labels:
                                self._loaded_labels.add(label.external_id)
                                yield LabelDefinitionWrite(
                                    name=label.external_id,
                                    external_id=label.external_id,
                                    data_set_id=self._label_data_set_id,
                                )

                    yield from relationships

                counter += 1
                # log every 10000 assets
                if counter % 10_000 == 0:
                    logging.info(" Next 10,000 Assets processed")

            logging.debug(f"Class <{class_name}> processed")

        # Todo Move orphanage to the beginning to ensure that it is loaded first.
        if self._use_orphanage and self._orphanage_external_id not in self._loaded_assets:
            logging.warning(f"Orphanage with external id {self._orphanage_external_id} not found in asset hierarchy!")
            logging.warning(f"Adding default orphanage with external id {self._orphanage_external_id}")
            now = str(datetime.now(UTC))
            if self._use_labels:
                yield LabelDefinitionWrite(
                    external_id="Orphanage", name="Orphanage", data_set_id=self._label_data_set_id
                )

            yield AssetWrite(
                external_id=self._orphanage_external_id,
                name="Orphanage",
                data_set_id=self._data_set_id,
                parent_external_id=None,
                description="Used to store all assets which parent does not exist",
                labels=["Orphanage", self._non_historic_label] if self._use_labels else None,
                metadata={
                    self._metadata_keys.type: "Orphanage",
                    "cdfResourceType": "Asset",
                    self._metadata_keys.start_time: now,
                    self._metadata_keys.update_time: now,
                    self._metadata_keys.identifier: "orphanage",
                    self._metadata_keys.active: "true",
                },
            )

    @overload
    def load_assets(self, stop_on_exception: Literal[True]) -> Iterable[AssetWrite]:
        ...

    @overload
    def load_assets(self, stop_on_exception: Literal[False] = False) -> Iterable[AssetWrite | ErrorDetails]:
        ...

    def load_assets(self, stop_on_exception: Literal[True, False] = False) -> Iterable[AssetWrite | ErrorDetails]:
        for asset_resource in self.load(stop_on_exception):
            if isinstance(asset_resource, AssetWrite):
                yield asset_resource

    @overload
    def load_relationships(self, stop_on_exception: Literal[True]) -> Iterable[RelationshipWrite]:
        ...

    @overload
    def load_relationships(
        self, stop_on_exception: Literal[False] = False
    ) -> Iterable[RelationshipWrite | ErrorDetails]:
        ...

    def load_relationships(
        self, stop_on_exception: Literal[True, False] = False
    ) -> Iterable[RelationshipWrite | ErrorDetails]:
        for asset_resource in self.load(stop_on_exception):
            if isinstance(asset_resource, RelationshipWrite):
                yield asset_resource

    def load_to_cdf(
        self, client: CogniteClient, batch_size: int | None = 1000, max_retries: int = 1, retry_delay: int = 3
    ) -> None:
        raise NotImplementedError

    def _load_asset(
        self, properties: list[Property], values_by_property: dict[str, str | list[str]], instance_id, class_name: str
    ) -> AssetWrite:
        """Converts a set of properties and values to an AssetWrite object."""
        asset_raw = self._load_asset_data(properties, values_by_property, instance_id, class_name)

        # Loading Asset assumes camel case.
        # Todo Change rules to use camel case?
        for snake_case, came_case in [
            ("external_id", "externalId"),
            ("parent_external_id", "parentExternalId"),
            ("geo_location", "geoLocation"),
        ]:
            if snake_case in asset_raw:
                asset_raw[came_case] = asset_raw.pop(snake_case)

        return AssetWrite.load(asset_raw)

    def _load_asset_data(
        self,
        properties: list[Property],
        values_by_property: dict[str, str | list[str]],
        instance_id: str,
        class_name: str,
    ) -> dict[str, Any]:
        """Creates a raw asset dict from a set of properties and values."""
        asset_raw, missing_metadata_properties = self._load_instance_data(properties, values_by_property)

        self._append_missing_properties(asset_raw, missing_metadata_properties, instance_id, class_name)

        asset_raw["dataSetId"] = self._data_set_id

        # Neat specific metadata keys
        if self._use_labels:
            asset_raw["labels"] = [class_name, self._non_historic_label]
        now = str(datetime.now(UTC))
        asset_raw["metadata"][self._metadata_keys.start_time] = now
        asset_raw["metadata"][self._metadata_keys.update_time] = now
        asset_raw["metadata"][self._metadata_keys.identifier] = instance_id
        asset_raw["metadata"][self._metadata_keys.active] = "true"
        asset_raw["metadata"][self._metadata_keys.type] = class_name

        # Rename metadata keys based on configuration
        asset_raw["metadata"] = {self._metadata_key_aliases.get(k, k): v for k, v in asset_raw["metadata"].items()}
        return asset_raw

    def _prepare_instance_data(
        self, instance_id: str, properties_values: Iterable[ResultRow]
    ) -> dict[str, str | list[str]]:
        """Groups the properties and values by property type.

        Returns:
            A dictionary with property type as key and a list of values as value.
        """
        properties_value_tuples: list[tuple[str, str]] = [
            remove_namespace(prop, value) for _, prop, value in properties_values  # type: ignore[misc]
        ]
        # We add an identifier which will be used as fallback for external_id
        properties_value_tuples.append((self._identifier, remove_namespace(instance_id)))
        values_by_property: dict[str, str | list[str]] = {}
        for prop, values in groupby(sorted(properties_value_tuples), lambda x: x[0]):
            values_list: list[str] = [value for _, value in values]  # type: ignore[misc, has-type]
            if len(values_list) == 1:
                values_by_property[prop] = values_list[0]
            else:
                values_by_property[prop] = values_list
        return values_by_property

    def _load_instance_data(
        self, properties: list[Property], values_by_property: dict[str, str | list[str]]
    ) -> tuple[dict[str, Any], set[str]]:
        """This function loads the instance data into a raw asset dict. It also returns a set of metadata keys that
        were not found in the instance data.

        Returns:
            A tuple with the raw asset dict and a set of metadata keys that were not found in the instance data.
        """
        asset_raw: dict[str, Any] = {"metadata": {}}
        missing_metadata_properties: set[str] = set()
        for prop in properties:
            if prop.property_name is None:
                continue
            is_relationship = "Asset" not in prop.cdf_resource_type
            if not self._always_store_in_metadata and is_relationship:
                continue

            if prop.property_name not in values_by_property:
                for property_type in prop.resource_type_property or []:
                    if property_type.casefold() == "metadata":
                        missing_metadata_properties.add(prop.property_name)
                    elif self._always_store_in_metadata:
                        missing_metadata_properties.add(prop.property_name)
                continue
            values = values_by_property[prop.property_name]
            for property_type in prop.resource_type_property or []:
                if property_type.casefold() == "metadata":
                    asset_raw["metadata"][prop.property_name] = self._to_metadata_value(values)
                else:
                    if property_type not in asset_raw:
                        asset_raw[property_type] = values
                    if self._always_store_in_metadata and prop.property_name not in asset_raw["metadata"]:
                        asset_raw["metadata"][prop.property_name] = self._to_metadata_value(values)
            if is_relationship:
                asset_raw["metadata"][prop.property_name] = self._to_metadata_value(values)

        return asset_raw, missing_metadata_properties

    def _append_missing_properties(
        self, asset_raw: dict[str, Any], missing_metadata_properties: set[str], identifier: str, class_name: str
    ) -> None:
        """This function ensures that the raw asset dict has all the required properties such as external_id, name,
        and parent_external_id. It also ensures that the metadata dict has all the required keys."""

        if "external_id" not in asset_raw:
            msg = f"Missing external_id for {class_name} instance {identifier}. Using value <{identifier}>."
            logging.debug(msg)
            asset_raw["external_id"] = identifier
        elif "external_id" in asset_raw and isinstance(asset_raw["external_id"], list):
            external_ids = asset_raw["external_id"]
            msg = (
                f"Multiple values for {class_name} instance {identifier} external_id. "
                f"Using the first one <{external_ids[0]}>."
            )
            logging.debug(msg)
            asset_raw["external_id"] = external_ids[0]

        if self._asset_external_id_prefix:
            asset_raw["external_id"] = f"{self._asset_external_id_prefix}{asset_raw['external_id']}"

        external_id = asset_raw["external_id"]

        if "name" not in asset_raw:
            msg = f"Missing name for {class_name} instance {external_id}. Using value <{identifier}>."
            logging.debug(msg)
            asset_raw["name"] = identifier
        elif "name" in asset_raw and isinstance(asset_raw["name"], list):
            msg = f"Multiple values for {class_name} instance {external_id} name. Joining them into one."
            logging.debug(msg)
            asset_raw["name"] = self._to_metadata_value(asset_raw["name"])

        if "description" in asset_raw and isinstance(asset_raw["description"], list):
            msg = f"Multiple values for {class_name} instance {external_id} description. Joining them into one."
            logging.debug(msg)
            asset_raw["description"] = self._to_metadata_value(asset_raw["description"])

        if "parent_external_id" not in asset_raw and self._orphanage_external_id is not None:
            asset_raw["parent_external_id"] = self._orphanage_external_id
        elif "parent_external_id" in asset_raw and isinstance(asset_raw["parent_external_id"], list):
            msg = (
                f"Multiple values for {class_name} instance {external_id} parent_external_id. "
                f"Using the first one <{asset_raw['parent_external_id'][0]}>."
            )
            logging.debug(msg)
            asset_raw["parent_external_id"] = asset_raw["parent_external_id"][0]

        if "parent_external_id" in asset_raw:
            asset_raw["parent_external_id"] = f"{self._asset_external_id_prefix or ''}{asset_raw['parent_external_id']}"

        for metadata_key in missing_metadata_properties:
            msg = f"{external_id} of type {class_name} is missing metadata key {metadata_key}."
            logging.debug(msg)
            if self._default_metadata_value is not None and metadata_key not in asset_raw["metadata"]:
                asset_raw["metadata"][metadata_key] = self._default_metadata_value
                logging.debug(f"\tKey {metadata_key} added to <{external_id}> metadata!")

    @staticmethod
    def _to_metadata_value(values: str | list[str]) -> str:
        """A helper function to convert a list of values to a metadata value string respecting metadata value length."""
        # Sorting for deterministic results
        return values if isinstance(values, str) else ", ".join(sorted(values))[: METADATA_VALUE_MAX_LENGTH - 1]

    def _load_relationships(
        self,
        properties: list[Property],
        values_by_property: dict[str, str | list[str]],
        instance_id: str,
        class_name: str,
    ) -> RelationshipWriteList:
        """Converts a set of properties and values to a RelationshipWriteList object."""
        relationships = RelationshipWriteList([])
        relationship_properties = [prop for prop in properties if "Relationship" in prop.cdf_resource_type]
        epoch_now = epoch_now_ms()
        for prop in relationship_properties:
            if not prop.property_name:
                continue
            values = values_by_property.get(prop.property_name, [])
            if not values:
                continue
            value_list = [values] if isinstance(values, str) else values
            for value in value_list:
                relationship = self._load_relationship(prop, value, instance_id, class_name, epoch_now)
                relationships.append(relationship)

        return relationships

    def _load_relationship(
        self,
        prop: Property,
        target_id: str,
        instance_id: str,
        class_name: str,
        epoch_now: int,
    ) -> RelationshipWrite:
        """Converts a set of properties and values to a RelationshipWrite object."""
        prefix = self._asset_external_id_prefix or ""
        labels = (
            [class_name, self._non_historic_label, prop.expected_value_type.suffix, prop.property_id]
            if self._use_labels
            else None
        )
        relationship_raw = {
            "externalId": f"{prefix}{instance_id}:{prefix}{target_id}",
            "sourceExternalId": f"{prefix}{instance_id}",
            "targetExternalId": f"{prefix}{target_id}",
            "sourceType": prop.source_type,
            "targetType": prop.target_type,
            "dataSetId": self._data_set_id,
            "labels": labels,
            "startTime": epoch_now,
        }
        return RelationshipWrite.load(relationship_raw)
