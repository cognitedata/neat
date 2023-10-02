import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from cognite.neat.app.api.configuration import NEAT_APP


@asynccontextmanager
async def lifespan(app_ref: FastAPI):
    logging.info("Startup FastAPI server")
    NEAT_APP.set_http_server(app_ref)
    NEAT_APP.start()
    yield
    logging.info("FastApi shutdown event")
    NEAT_APP.stop()
