from ._interface import NeatEngine


def import_engine() -> NeatEngine:
    from neatengine import NeatEngine  # type: ignore[import-not-found]

    return NeatEngine()
