import logging
import os
from pathlib import Path

from fastapi import APIRouter

from cognite.neat._app.api.configuration import NEAT_APP
from cognite.neat._config import Config

router = APIRouter()


@router.get("/api/configs/global")
def get_configs():
    return NEAT_APP.config.as_legacy_config()


@router.post("/api/configs/global")
def set_configs(request: Config):
    logging.info(f"Updating global config: {request}")
    config = request
    config.to_yaml(Path(os.environ.get("NEAT_CONFIG_PATH", "config.yaml")))
    NEAT_APP.stop()
    NEAT_APP.start(config=config)
    return config
