import pytest
from rdflib import Namespace, URIRef

from cognite.neat.core._constants import DEFAULT_SPACE_URI
from cognite.neat.core._utils.rdf_ import uri_to_cdf_id, uri_to_entity_components


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


def test_uri_to_entity_components_valid_uri():
    """Test uri_to_entity_components with a valid URI that matches expected format."""
    uri = URIRef("https://cognitedata.com/cdf_cdm/CogniteCore/v1/CogniteAsset")
    prefixes = {"cdf_cdm": Namespace("https://cognitedata.com/cdf_cdm/")}

    result = uri_to_entity_components(uri, prefixes)

    assert result == ("cdf_cdm", "CogniteCore", "v1", "CogniteAsset")


def test_uri_to_entity_components_no_matching_prefix():
    """Test uri_to_entity_components with URI that doesn't match any prefix."""
    uri = URIRef("https://example.com/space/model/v1/entity")
    prefixes = {"cdf_cdm": Namespace("https://cognitedata.com/cdf_cdm/")}

    result = uri_to_entity_components(uri, prefixes)

    assert result is None


def test_uri_to_entity_components_incomplete_components():
    """Test uri_to_entity_components with URI that has fewer than 3 components after namespace."""
    uri = URIRef("https://cognitedata.com/cdf_cdm/CogniteCore/v1")
    prefixes = {"cdf_cdm": Namespace("https://cognitedata.com/cdf_cdm/")}

    result = uri_to_entity_components(uri, prefixes)

    assert result is None


def test_uri_to_entity_components_empty_components():
    """Test uri_to_entity_components with URI that has empty components."""
    uri = URIRef("https://cognitedata.com/cdf_cdm//v1/")
    prefixes = {"cdf_cdm": Namespace("https://cognitedata.com/cdf_cdm/")}

    result = uri_to_entity_components(uri, prefixes)

    assert result is None


def test_uri_to_entity_components_multiple_prefixes():
    """Test uri_to_entity_components with multiple prefixes, should return first match."""
    uri = URIRef("https://cognitedata.com/space/model/v1/entity")
    prefixes = {
        "prefix1": Namespace("https://cognitedata.com/"),
        "prefix2": Namespace("https://cognitedata.com/space/"),
    }

    result = uri_to_entity_components(uri, prefixes)

    # Should match the first prefix that works
    assert result == ("prefix2", "model", "v1", "entity")


def test_uri_to_entity_components_empty_prefixes():
    """Test uri_to_entity_components with empty prefixes dictionary."""
    uri = URIRef("https://cognitedata.com/cdf_cdm/CogniteCore/v1/CogniteAsset")
    prefixes = {}

    result = uri_to_entity_components(uri, prefixes)

    assert result is None


def test_uri_to_entity_components_exact_namespace_match():
    """Test uri_to_entity_components with URI that exactly matches namespace."""
    uri = URIRef("https://cognitedata.com/cdf_cdm/")
    prefixes = {"cdf_cdm": Namespace("https://cognitedata.com/cdf_cdm/")}

    result = uri_to_entity_components(uri, prefixes)

    assert result is None


def test_uri_to_entity_components_too_many_components():
    """Test uri_to_entity_components with URI that has more than 3 components after namespace."""
    uri = URIRef("https://cognitedata.com/cdf_cdm/CogniteCore/v1/CogniteAsset/extra")
    prefixes = {"cdf_cdm": Namespace("https://cognitedata.com/cdf_cdm/")}

    result = uri_to_entity_components(uri, prefixes)

    assert result is None
