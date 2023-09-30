import pkg_resources
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from cognite import neat
from cognite.neat.app.api.asgi.metrics import prometheus_app
from cognite.neat.app.api.configuration import NEAT_APP, UI_PATH
from cognite.neat.app.api.context_manager import lifespan
from cognite.neat.app.api.routers import configuration, crud, data_exploration, metrics, rules, workflows

app = FastAPI(title="Neat", lifespan=lifespan)


origins = [
    "http://localhost:8000",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount ASGI apps
app.mount("/metrics", prometheus_app)
app.mount("/static", StaticFiles(directory=UI_PATH), name="static")
app.mount("/data", StaticFiles(directory=NEAT_APP.config.data_store_path), name="data")


# Mount routers
app.include_router(configuration.router)
app.include_router(metrics.router)
app.include_router(workflows.router)
app.include_router(rules.router)
app.include_router(crud.router)
app.include_router(data_exploration.router)


# General routes
@app.get("/")
def read_root():
    return RedirectResponse("/static/index.html")


@app.get("/api/about")
def get_about():
    installed_packages = pkg_resources.working_set
    installed_packages_list = sorted([f"{i.key}=={i.version}" for i in installed_packages])
    return {"version": neat.__version__, "packages": installed_packages_list}
