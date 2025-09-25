"""Shortcut to data model catalog"""

from pathlib import Path

_CATALOG = Path(__file__).parent
imf_attributes = _CATALOG / "conceptual-imf-data-model.xlsx"
hello_world_pump = _CATALOG / "hello_world_pump.xlsx"
classic_model = _CATALOG / "classic_model.xlsx"
