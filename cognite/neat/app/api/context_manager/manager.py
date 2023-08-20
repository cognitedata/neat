import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from cognite.neat.app.api.configuration import neat_app


@asynccontextmanager
async def lifespan(app_ref: FastAPI):
    logging.info("Startup FastAPI server")
    neat_app.set_http_server(app_ref)
    neat_app.start()
    yield
    logging.info("FastApi shutdown event")
    neat_app.stop()
