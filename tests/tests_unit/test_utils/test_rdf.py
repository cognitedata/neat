import pytest
from rdflib import Namespace, URIRef

from cognite.neat.core._constants import DEFAULT_SPACE_URI
from cognite.neat.core._utils.rdf_ import uri_to_cdf_id


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
