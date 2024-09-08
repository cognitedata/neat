from typing import Annotated, Any

from pydantic import (
    AnyHttpUrl,
    BeforeValidator,
    PlainSerializer,
)

from ._single_value import AssetEntity, ClassEntity, ContainerEntity, RelationshipEntity, ViewEntity


def _split_str(v: Any) -> list[str]:
    if isinstance(v, str):
        return v.replace(", ", ",").split(",")
    return v


def _join_str(v: list[ClassEntity]) -> str | None:
    return ",".join([entry.id for entry in v]) if v else None


def _generate_cdf_resource_list(v: Any) -> list[AssetEntity | RelationshipEntity]:
    results = []
    for item in _split_str(v):
        if isinstance(item, str):
            if "relationship" in item.lower():
                results.append(RelationshipEntity.load(item))
            elif "asset" in item.lower():
                results.append(AssetEntity.load(item))  # type: ignore
            else:
                raise ValueError(f"Unsupported implementation definition: {item}")

        elif isinstance(item, AssetEntity | RelationshipEntity):
            results.append(item)
        else:
            raise ValueError(f"Unsupported implementation definition: {item}")

    return results  # type: ignore


ClassEntityList = Annotated[
    list[ClassEntity],
    BeforeValidator(_split_str),
]


CdfResourceEntityList = Annotated[
    list[AssetEntity | RelationshipEntity],
    BeforeValidator(_generate_cdf_resource_list),
    PlainSerializer(
        _join_str,
        return_type=str,
        when_used="unless-none",
    ),
]


ContainerEntityList = Annotated[
    list[ContainerEntity],
    BeforeValidator(_split_str),
]

ViewEntityList = Annotated[
    list[ViewEntity],
    BeforeValidator(_split_str),
    PlainSerializer(
        _join_str,
        return_type=str,
        when_used="unless-none",
    ),
]

URLEntity = Annotated[
    AnyHttpUrl,
    PlainSerializer(lambda v: str(v), return_type=str, when_used="unless-none"),
]
