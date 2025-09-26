import pytest
from rdflib import Namespace, URIRef

from cognite.neat.v0.core._constants import DEFAULT_SPACE_URI
from cognite.neat.v0.core._utils.rdf_ import uri_to_cdf_id, uri_to_entity_components


class TestURIInstanceToDisplayName:
    @pytest.mark.parametrize(
        "uri, expected",
        [
            (URIRef("http://example.com/namespace#instance"), "instance"),
            (URIRef("http://example.com/namespace#"), ""),
            (Namespace(DEFAULT_SPACE_URI.format(space="my_space"))["myInstance"], "my_space:myInstance"),
            (URIRef("http://example.com/namespace#instance"), "instance"),
            (URIRef(" http://example.com/namespace#"), ""),
            (URIRef("http://example.com/namespace"), "namespace"),
            (URIRef("http://example.com/namespace#instance/subinstance"), "instance/subinstance"),
            (URIRef("http://example.com/namespace#instance?query=param"), "instance?query=param"),
            (URIRef("http://example.com/namespace#instance#fragment"), "instance#fragment"),
            (URIRef("http://example.com/namespace#instance%20with%20spaces"), "instance with spaces"),
            (
                URIRef("http://example.com/namespace#instance_with_special_chars!@#$%^&*()"),
                "instance_with_special_chars!@#$%^&*()",
            ),
            (URIRef("http://example.com/namespace#instance_with_unicode_✓"), "instance_with_unicode_✓"),
        ],
    )
    def test_uri_to_cdf_id(self, uri: URIRef, expected: str) -> None:
        assert uri_to_cdf_id(uri) == expected


class TestURIToEntityComponents:
    @pytest.mark.parametrize(
        "uri, prefixes, expected",
        [
            # Valid URI with matching format
            (
                URIRef("https://cognitedata.com/cdf_cdm/CogniteCore/v1/CogniteAsset"),
                {"cdf_cdm": Namespace("https://cognitedata.com/cdf_cdm/")},
                ("cdf_cdm", "CogniteCore", "v1", "CogniteAsset"),
            ),
            # No matching prefix
            (
                URIRef("https://example.com/space/model/v1/entity"),
                {"cdf_cdm": Namespace("https://cognitedata.com/cdf_cdm/")},
                None,
            ),
            # Incomplete components (fewer than 3)
            (
                URIRef("https://cognitedata.com/cdf_cdm/CogniteCore/v1"),
                {"cdf_cdm": Namespace("https://cognitedata.com/cdf_cdm/")},
                None,
            ),
            # Empty components
            (
                URIRef("https://cognitedata.com/cdf_cdm//v1/"),
                {"cdf_cdm": Namespace("https://cognitedata.com/cdf_cdm/")},
                None,
            ),
            # Multiple prefixes - should return first match
            (
                URIRef("https://cognitedata.com/space/model/v1/entity"),
                {
                    "prefix1": Namespace("https://cognitedata.com/"),
                    "prefix2": Namespace("https://cognitedata.com/space/"),
                },
                ("prefix2", "model", "v1", "entity"),
            ),
            # Empty prefixes dictionary
            (
                URIRef("https://cognitedata.com/cdf_cdm/CogniteCore/v1/CogniteAsset"),
                {},
                None,
            ),
            # Exact namespace match
            (
                URIRef("https://cognitedata.com/cdf_cdm/"),
                {"cdf_cdm": Namespace("https://cognitedata.com/cdf_cdm/")},
                None,
            ),
            # Too many components (more than 3)
            (
                URIRef("https://cognitedata.com/cdf_cdm/CogniteCore/v1/CogniteAsset/extra"),
                {"cdf_cdm": Namespace("https://cognitedata.com/cdf_cdm/")},
                None,
            ),
        ],
    )
    def test_uri_to_entity_components(self, uri: URIRef, prefixes: dict, expected: tuple | None) -> None:
        result = uri_to_entity_components(uri, prefixes)
        assert result == expected
