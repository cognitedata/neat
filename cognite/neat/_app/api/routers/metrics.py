from fastapi import APIRouter
from prometheus_client import REGISTRY

router = APIRouter()


@router.get("/api/metrics")
def get_metrics():
    metrics = REGISTRY.collect()
    return {"prom_metrics": metrics}
