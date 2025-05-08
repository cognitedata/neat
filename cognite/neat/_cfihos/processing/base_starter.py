import pathlib
from dataclasses import dataclass, field

from cognite.neat._cfihos.common.log import log_init
from cognite.neat._cfihos.common.reader import read_yaml
from cognite.neat._cfihos.common.utils import collect_model_subset
from cognite.neat._cfihos.dms.container import create_container_from_property_struct_dict
from cognite.neat._cfihos.dms.views import build_views_from_containers, build_views_from_entities
from cognite.neat._cfihos.processing.processor import Processor

logging = log_init(f"{__name__}", "i")


@dataclass
class cfihosReadResult:
    Properties: list[dict]
    Containers: list[dict]
    Views: list[dict]
    Metadata: dict


@dataclass
class base_starter_class:
    model_processors_config_path: str

    # Model entities
    _model_entities: dict = field(default_factory=dict)
    _model_properties: dict = field(default_factory=dict)
    _model_property_groups: dict = field(default_factory=dict)
    _map_dms_id_to_entity_id: dict = field(default_factory=dict)
    domain_model_config: dict = field(default_factory=dict)
    processor_config: dict = field(default_factory=dict)
    containers_indexes: dict = field(default_factory=dict)

    def __post_init__(self):
        self.domain_model_config = self.get_domain_model_config(self.model_processors_config_path)
        self.processor_config = {k: v for k, v in self.domain_model_config.items() if k == "model_processors_config"}
        self.containers_indexes = {k: v for k, v in self.domain_model_config.items() if k == "containers_indexes"}
        self.container_space = self.domain_model_config["container_data_model_space"]
        self.views_space = self.domain_model_config["views_data_model_space"]
        self.model_version = self.domain_model_config["model_version"]
        self.model_creator = self.domain_model_config["model_creator"]
        self.model_name = self.domain_model_config["data_model_name"]
        self.model_description = self.domain_model_config["data_model_description"]
        self.model_external_id = self.domain_model_config["data_model_external_id"]

    @property
    def model_entities(self):
        return self._model_entities

    @property
    def model_properties(self):
        return self._model_properties

    @property
    def map_dms_id_to_entity_id(self):
        return self._map_dms_id_to_entity_id

    @property
    def scopes(self):
        return self.domain_model_config["scopes"]

    @property
    def scopes(self):
        return self.domain_model_config["scopes"]

    @property
    def scopes(self):
        return self.domain_model_config["scopes"]

    @property
    def scopes(self):
        return self.domain_model_config["scopes"]

    def get_domain_model_config(self, path_to_config: str) -> dict:
        """Returns the configuration information related to a domain model"""

        config_fpath = pathlib.Path(path_to_config)

        # Check if file exists
        config_folder_exists = pathlib.Path.is_file(config_fpath)

        if not config_folder_exists:
            raise FileNotFoundError(f"Could not find '{config_fpath}'")

        return read_yaml(config_fpath)

    def process_model(self) -> None:
        """
        Processes the CFIHOS model according to the provided configuration.
        """

        print("Excuting the processor")

        # Setup model processor
        model_processor = Processor(**self.processor_config)

        # Process and combine models into one
        model_processor.process_and_collect_models()

        # Setup Model Containers
        self._model_properties = model_processor.model_properties

        self._map_dms_id_to_entity_id = model_processor.map_dms_id_to_entity_id
        self._model_entities = model_processor.model_entities

    def build_containers_model(self) -> cfihosReadResult:
        # Setup containers from models
        logging.info(f"STEP 2: Started upserting {len(self._model_properties)} container properties ...")
        containers = create_container_from_property_struct_dict(
            space=self.container_space,
            property_data=self._model_properties,
            containers_indexes=self.containers_indexes["containers_indexes"],
        )

        # Setup population views on-top of containers
        logging.info(f"STEP 3: Started upserting {len(containers)} population views on-top of containers ...")

        lst_views, lst_properties = build_views_from_containers(
            containers=containers,
            entities=self.model_entities,
        )

        logging.info("STEP 4: generating NEAT rules ...")

        container_model_dict = {
            "role": "DMS Architect",
            "dataModelType": "enterprise",
            "schema": "complete",
            "space": self.container_space,
            "name": self.model_name,
            "description": self.model_description,
            "external_id": self.model_external_id,
            "version": self.model_version,
            "creator": self.model_creator,
        }

        return {
            "Properties": lst_properties,
            "Containers": containers,
            "Views": lst_views,
            "Metadata": container_model_dict,
        }

    def build_scoped_views_models(self, scope) -> cfihosReadResult:
        views_scope = ""
        for sub_scope in self.domain_model_config["scopes"]:
            if sub_scope["scope_name"] == scope:
                views_scope = sub_scope
                break

        scoped_model = collect_model_subset(
            full_model=self.model_entities,
            scope_config=self.domain_model_config["scope_config"],
            scope=views_scope["scope_subset"],
            map_dms_id_to_model_id=self.map_dms_id_to_entity_id,
        )
        lst_entity_views, lst_entity_properties = build_views_from_entities(
            version=self.model_version,
            entities=scoped_model,
        )

        logging.info(f"STEP 4: Started building {len(scoped_model)} scoped entity views")

        return {
            "Properties": lst_entity_properties,
            "Containers": [],
            "Views": lst_entity_views,
            "Metadata": {
                "role": "DMS Architect",
                "dataModelType": "enterprise",
                "schema": "complete",
                "space": self.views_space,
                "name": "cfihos_" + str.replace(views_scope["scope_name"], " ", "_"),
                "description": views_scope["scope_description"],
                "external_id": "cfihos_" + views_scope["scope_name"],
                "version": self.model_version,
                "creator": self.model_creator,
            },
        }
