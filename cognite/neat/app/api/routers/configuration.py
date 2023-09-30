import logging
import os
from pathlib import Path

from fastapi import APIRouter

from cognite.neat.app.api.configuration import Config, neat_app

router = APIRouter()


@router.get("/api/configs/global")
def get_configs():
    return neat_app.config.dict()


@router.post("/api/configs/global")
def set_configs(request: Config):
    logging.info(f"Updating global config: {request}")
    config = request
    config.to_yaml(Path(os.environ.get("NEAT_CONFIG_PATH", "config.yaml")))
    neat_app.stop()
    neat_app.start(config=config)
    return config
