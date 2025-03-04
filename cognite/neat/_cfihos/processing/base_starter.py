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
from cognite.neat._cfihos.dms.views import build_views_from_entities, create_views_from_containers,build_views_from_containers
from cognite.neat._cfihos.processing.cfihos.cfihos import CfihosProcessor
from cognite.neat._cfihos.common.reader import read_yaml, read_csv
from cognite.neat._cfihos.processing.processor import Processor
from cognite.neat._cfihos.common.utils import generate_neat_rules_sheet

logging = log_init(f"{__name__}", "i")


@dataclass
class base_starter_class:

    model_processors_config : str = ""
    # Model entities
    _model_entities = {}
    _model_properties = {}
    _model_property_groups = {}
    _domain_model_config = ""
    _processor_config = ""
    _containers_indexes = {}
    _path_to_cfihos_config = ""



    @property
    def model_entities(self):
        return self._model_entities

    @property
    def model_properties(self):
        return self._model_properties
    
    @classmethod
    def get_domain_model_config(slef, path_to_config: str) -> dict:
        """Returns the configuration information related to a domain model"""

        # config_fpath =  pathlib.Path(path_to_config)

        print("config_fpath",path_to_config)

        # Check if file exists
        config_folder_exists = pathlib.Path.is_file(path_to_config)

        if not config_folder_exists:
            raise FileNotFoundError(
                f"Could not find '{path_to_config}'"
            )

        return read_yaml(path_to_config)
    
    def process_model(self):

        
        domain_model_config = self.get_domain_model_config(path_to_config= self.model_processors_config)
        processor_config = {k: v for k, v in domain_model_config.items() if k == "model_processors_config"}
        containers_indexes = {k: v for k, v in domain_model_config.items() if k == "containers_indexes"}

        containers_dm_space = "xom_draft_domain_model_containers"
        views_dm_space = "xom_draft_domain_model_views"
        containers_model_Version = "1"
        views_model_Version= "1"

        print("Excuting the processor")

        
        container_model_dict =  {"role": "DMS Architect","dataModelType": "enterprise","schema": "complete","space" : domain_model_config["container_data_model_space"],"name" : domain_model_config["data_model_name"],"description" : domain_model_config["data_model_description"],"external_id" : domain_model_config["data_model_external_id"],"version" : domain_model_config["model_version"],"creator" : domain_model_config["model_creator"]}
        df_container_model_metadata = pd.DataFrame(list(container_model_dict.items()), columns=["Key", "Value"])
            

    # Setup model processor
        model_processor = Processor(**processor_config)

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
            containers_indexes=containers_indexes["containers_indexes"],
        )

        # Setup population views on-top of containers
        logging.info(f"STEP 3: Started upserting {len(containers)} population views on-top of containers ...")

        lst_views, lst_properties = build_views_from_containers(
            version=containers_model_Version,
            containers=containers,
            entities=model_processor.model_entities,
        )

        logging.info(f"STEP 4: exporting NEAT rules sheet ...")
        generate_neat_rules_sheet("/Users/ali.majed@cognitedata.com/projects/neat-xom/neat/cfihos_src/dmsTemplates/cfihos_neat_model.xlsx",
                                  pd.DataFrame(df_container_model_metadata),
                                  pd.DataFrame(lst_properties),
                                  pd.DataFrame(lst_views),
                                  pd.DataFrame(containers)
                                  )
        
        # # Find scope
        # scoped_model = collect_model_subset(
        #     full_model=model_processor.model_entities,
        #     scope_config=domain_model_config["scope_config"],
        #     scope=domain_model_config["scope"],
        #     map_dms_id_to_model_id=model_processor.map_dms_id_to_entity_id,
        # )

        # logging.info(f"STEP 4: Started building {len(scoped_model)} scoped entity views")
        # entity_views = build_views_from_entities(
        #     containers_space=containers_dm_space,
        #     views_space=views_dm_space,
        #     version=views_model_Version,
        #     entities=scoped_model,
        # )

        # logging.info(f"**** SUCCESS! Pipeline deployed domain model ****")



