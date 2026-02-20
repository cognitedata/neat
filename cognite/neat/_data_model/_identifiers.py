import hashlib

from pydantic import HttpUrl, RootModel, ValidationError

from cognite.neat._data_model.models.dms import ContainerReference
from cognite.neat._utils.auxiliary import local_import


class URI(RootModel[str]):
    def __init__(self, value: str):
        try:
            # Use Pydantic's AnyUrl to validate the URI
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
            # Use Pydantic's AnyUrl to validate the URI
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


class AutoIdentifier:
    """Generates identifiers for auto-created CDF constraints and indexes.

    CDF has a 43-character limit on constraint/index identifiers. This class
    ensures generated IDs stay within that limit while maintaining uniqueness.
    """

    MAX_LENGTH = 43
    SUFFIX = "__auto"
    HASH_LENGTH = 8
    # base_id + suffix must fit in MAX_LENGTH
    _MAX_BASE_NO_HASH = MAX_LENGTH - len(SUFFIX)
    # base_id + "_" + hash + suffix must fit in MAX_LENGTH
    _MAX_BASE_WITH_HASH = _MAX_BASE_NO_HASH - HASH_LENGTH - 1

    @classmethod
    def make(cls, base_id: str) -> str:
        """Generate an auto identifier, truncating with a hash if needed.

        Args:
            base_id: The primary identifier (e.g., external_id or property_id).

        Returns:
            For short base_ids (<=37 chars): "{base_id}__auto"
            For long base_ids (>37 chars): "{truncated_id}_{hash}__auto"
        """
        if len(base_id) <= cls._MAX_BASE_NO_HASH:
            return f"{base_id}{cls.SUFFIX}"

        hash_suffix = hashlib.sha256(base_id.encode()).hexdigest()[: cls.HASH_LENGTH]
        truncated_id = base_id[: cls._MAX_BASE_WITH_HASH]
        return f"{truncated_id}_{hash_suffix}{cls.SUFFIX}"

    @classmethod
    def for_constraint(cls, destination: ContainerReference) -> str:
        """Generate a constraint identifier for auto-generated requires constraints."""
        return cls.make(destination.external_id)

    @classmethod
    def for_index(cls, property_id: str) -> str:
        """Generate an index identifier for auto-generated indexes."""
        return cls.make(property_id)
