"""Shortcut to rules catalog files"""

from pathlib import Path

_CATALOG = Path(__file__).parent
imf_attributes = _CATALOG / "info-rules-imf.xlsx"
hello_world_pump = _CATALOG / "hello_world_pump.xlsx"
classic_model = _CATALOG / "classic_model.xlsx"
