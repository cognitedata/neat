import pytest
from rdflib import Namespace, URIRef

from cognite.neat._constants import DEFAULT_SPACE_URI
from cognite.neat._utils.rdf_ import uri_instance_to_display_name


class TestURIInstanceToDisplayName:
    @pytest.mark.parametrize(
        "uri, expected",
        [
            (URIRef("http://example.com/namespace#instance"), "instance"),
            (URIRef("http://example.com/namespace#"), ""),
            (Namespace(DEFAULT_SPACE_URI.format(space="my_space"))["myInstance"], "my_space:myInstance"),
        ],
    )
    def test_to_display_name(self, uri: URIRef, expected: str) -> None:
        assert uri_instance_to_display_name(uri) == expected
