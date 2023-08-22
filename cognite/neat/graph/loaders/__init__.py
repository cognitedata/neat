from cognite.neat.graph.loaders.core.labels import upload_labels

from .core.rdf_to_assets import categorize_assets, rdf2assets, upload_assets
from .core.rdf_to_relationships import categorize_relationships, rdf2relationships, upload_relationships

__all__ = [
    "rdf2relationships",
    "categorize_assets",
    "upload_assets",
    "rdf2assets",
    "categorize_relationships",
    "upload_relationships",
    "upload_labels",
]
