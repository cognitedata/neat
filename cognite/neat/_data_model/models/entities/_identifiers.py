from pydantic import HttpUrl, RootModel, ValidationError

from cognite.neat.v0.core._utils.auxiliary import local_import


class URI(RootModel[str]):
    def __init__(self, value: str):
        try:
            # Use Pydantic's HttpUrl to validate the URI
            _ = HttpUrl(value)
        except ValidationError as e:
            raise ValueError(f"Invalid URI: {value}") from e
        super().__init__(value)

    def __str__(self) -> str:
        return self.root

    def __repr__(self) -> str:
        return f"URI({self.root!r})"

    def as_rdflib_uriref(self):  # type: ignore[no-untyped-def]
        # rdflib is an optional dependency, so import here
        local_import("rdflib", "rdflib")
        from rdflib import URIRef

        return URIRef(self.root)


class NameSpace(RootModel[str]):
    def __init__(self, value: str):
        try:
            # Use Pydantic's HttpUrl to validate the URI
            _ = HttpUrl(value)
        except ValidationError as e:
            raise ValueError(f"Invalid Namespace: {value}") from e
        super().__init__(value)

    def __str__(self) -> str:
        return self.root

    def __repr__(self) -> str:
        return f"NameSpace({self.root!r})"

    def term(self, name: str) -> URI:
        # need to handle slices explicitly because of __getitem__ override
        return URI(self.root + (name if isinstance(name, str) else ""))

    def __getitem__(self, key: str) -> URI:  # type: ignore[override]
        return self.term(key)

    def __getattr__(self, name: str) -> URI:
        if name.startswith("__"):  # ignore any special Python names!
            raise AttributeError
        return self.term(name)

    def as_rdflib_namespace(self):  # type: ignore[no-untyped-def]
        # rdflib is an optional dependency, so import here
        local_import("rdflib", "rdflib")
        from rdflib import Namespace

        return Namespace(self.root)
