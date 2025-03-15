import copy
import pathlib
import re
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np
import pandas as pd

from cognite.neat._cfihos.common.constants import CONTAINER_PROPERTY_LIMIT
from cognite.neat._cfihos.common.generic_classes import (
    DataSource,
    EntityStructure,
    PropertyStructure,
)
from cognite.neat._cfihos.common.log import log_init
from cognite.neat._cfihos.common.utils import collect_model_subset
from cognite.neat._cfihos.dms.container import create_container_from_property_struct_dict
from cognite.neat._cfihos.dms.views import build_views_from_containers
from cognite.neat._cfihos.processing.cfihos.cfihos import CfihosProcessor
from cognite.neat._cfihos.common.reader import read_yaml, read_csv
from cognite.neat._cfihos.processing.processor import Processor
from cognite.neat._cfihos.common.utils import generate_neat_rules_sheet
from cognite.neat._rules.models.dms._rules import _DEFAULT_VERSION, DMSContainer, DMSEnum, DMSMetadata, DMSNode, DMSProperty, DMSRules, DMSView

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
    _model_entities : Dict = field(default_factory=dict)
    _model_properties : Dict = field(default_factory=dict)
    _model_property_groups : Dict = field(default_factory=dict)
    domain_model_config : Dict = field(default_factory=dict)
    processor_config : Dict = field(default_factory=dict)
    containers_indexes : Dict = field(default_factory=dict)
    

    def __post_init__(self):
        self.domain_model_config = self.get_domain_model_config(self.model_processors_config_path)
        self.processor_config = {k: v for k, v in self.domain_model_config.items() if k == "model_processors_config"}
        self.containers_indexes = {k: v for k, v in self.domain_model_config.items() if k == "containers_indexes"}


    @property
    def model_entities(self):
        return self._model_entities

    @property
    def model_properties(self):
        return self._model_properties
    
    @staticmethod
    def get_domain_model_config( path_to_config: str) -> dict:
        """Returns the configuration information related to a domain model"""

        config_fpath =  pathlib.Path(path_to_config)

        # Check if file exists
        config_folder_exists = pathlib.Path.is_file(config_fpath)

        if not config_folder_exists:
            raise FileNotFoundError(
                f"Could not find '{config_fpath}'"
            )

        return read_yaml(config_fpath)
    
    def process_model(self) -> cfihosReadResult:
        """
        Processes the CFIHOS model according to the provided configuration.
        """
        containers_dm_space = "xom_draft_domain_model_containers"
        views_dm_space = "xom_draft_domain_model_views"
        containers_model_Version = "1"
        views_model_Version= "1"

        print("Excuting the processor")

        container_model_dict =  {"role": "DMS Architect","dataModelType": "enterprise","schema": "complete","space" : self.domain_model_config["container_data_model_space"],"name" : self.domain_model_config["data_model_name"],"description" : self.domain_model_config["data_model_description"],"external_id" : self.domain_model_config["data_model_external_id"],"version" : self.domain_model_config["model_version"],"creator" : self.domain_model_config["model_creator"]}
        df_container_model_metadata = pd.DataFrame(list(container_model_dict.items()), columns=["Key", "Value"])
            

    # Setup model processor
        model_processor = Processor(**self.processor_config)

        # Process and combine models into one
        model_processor.process_and_collect_models()

        # Setup Model Containers
        model_properties = model_processor.model_properties

        # Setup containers from models
        logging.info(
            f"STEP 2: Started upserting {len(model_properties)} container properties ..."
        )
        containers = create_container_from_property_struct_dict(
            space=containers_dm_space,
            property_data=model_properties,
            containers_indexes=self.containers_indexes["containers_indexes"],
        )

        # Setup population views on-top of containers
        logging.info(f"STEP 3: Started upserting {len(containers)} population views on-top of containers ...")

        lst_views, lst_properties = build_views_from_containers(
            version=containers_model_Version,
            containers=containers,
            entities=model_processor.model_entities,
        )

        logging.info(f"STEP 4: exporting NEAT rules sheet ...")

        return cfihosReadResult(Properties=lst_properties, Containers=containers, Views=lst_views, Metadata=df_container_model_metadata)
