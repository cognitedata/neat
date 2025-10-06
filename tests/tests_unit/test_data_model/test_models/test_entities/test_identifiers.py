import pytest
from rdflib import Namespace, URIRef

from cognite.neat._data_model.models.entities import URI, NameSpace


class TestNameSpace:
    def test_valid_namespace_creation(self) -> None:
        """Test creating a NameSpace with valid URIs."""
        valid_namespaces = [
            "http://example.com/",
            "https://example.org/vocab#",
            "http://www.w3.org/2000/01/rdf-schema#",
            "https://schema.org/",
        ]

        for namespace_str in valid_namespaces:
            ns = NameSpace(namespace_str)
            assert str(ns) == namespace_str
            assert ns.root == namespace_str

    def test_invalid_namespace_creation(self) -> None:
        """Test that invalid URIs raise ValueError."""
        invalid_namespaces = [
            "not-a-uri",
            "",
            "://invalid",
            "http://",
            "just-text",
            "ftp://files.example.com/",
        ]

        for invalid_ns in invalid_namespaces:
            with pytest.raises(ValueError, match="Invalid Namespace"):
                NameSpace(invalid_ns)

    def test_namespace_repr(self) -> None:
        """Test string representation of NameSpace."""
        ns = NameSpace("http://example.com/")
        assert repr(ns) == "NameSpace('http://example.com/')"

    def test_term_method(self) -> None:
        """Test creating terms using the term method."""
        ns = NameSpace("http://example.com/vocab#")

        term = ns.term("Person")
        assert isinstance(term, URI)
        assert str(term) == "http://example.com/vocab#Person"

        term = ns.term("hasName")
        assert str(term) == "http://example.com/vocab#hasName"

    def test_getitem_method(self) -> None:
        """Test creating terms using bracket notation."""
        ns = NameSpace("http://example.com/vocab#")

        term = ns["Person"]
        assert isinstance(term, URI)
        assert str(term) == "http://example.com/vocab#Person"

        term = ns["hasAge"]
        assert str(term) == "http://example.com/vocab#hasAge"

    def test_getattr_method(self) -> None:
        """Test creating terms using attribute access."""
        ns = NameSpace("http://example.com/vocab#")

        term = ns.Person
        assert isinstance(term, URI)
        assert str(term) == "http://example.com/vocab#Person"

        term = ns.hasName
        assert str(term) == "http://example.com/vocab#hasName"

    def test_getattr_special_names(self) -> None:
        """Test that special Python names raise AttributeError."""
        ns = NameSpace("http://example.com/vocab#")

        with pytest.raises(AttributeError):
            _ = ns.__special__

    def test_as_rdflib_namespace(self) -> None:
        """Test conversion to rdflib Namespace."""
        pytest.importorskip("rdflib")

        ns = NameSpace("http://example.com/vocab#")
        rdflib_ns = ns.as_rdflib_namespace()

        assert isinstance(rdflib_ns, Namespace)
        assert str(rdflib_ns) == "http://example.com/vocab#"

    @pytest.mark.parametrize(
        "term_name",
        [
            "Person",
            "hasName",
            "Organization",
            "member_of",
            "CamelCase",
            "snake_case",
            "kebab-case",
        ],
    )
    def test_various_term_names(self, term_name: str) -> None:
        """Test creating terms with various naming conventions."""
        ns = NameSpace("http://example.com/vocab#")

        # Test all three ways of creating terms
        term1 = ns.term(term_name)
        term2 = ns[term_name]
        term3 = getattr(ns, term_name)

        expected = f"http://example.com/vocab#{term_name}"
        assert str(term1) == expected
        assert str(term2) == expected
        assert str(term3) == expected


class TestURI:
    def test_valid_uri_creation(self) -> None:
        """Test creating URI with valid URIs."""
        valid_uris = [
            "http://example.com",
            "https://example.org/path",
            "http://www.w3.org/2000/01/rdf-schema#Class",
            "https://schema.org/Person",
        ]

        for uri_str in valid_uris:
            uri = URI(uri_str)
            assert str(uri) == uri_str
            assert uri.root == uri_str

    def test_invalid_uri_creation(self) -> None:
        """Test that invalid URIs raise ValueError."""
        invalid_uris = [
            "not-a-uri",
            "",
            "://invalid",
            "http://",
            "just-text",
            "file:///path/to/file",
            "mailto:user@example.com",
            "ftp://files.example.com/file.txt",
        ]

        for invalid_uri in invalid_uris:
            with pytest.raises(ValueError, match="Invalid URI"):
                URI(invalid_uri)

    def test_uri_repr(self) -> None:
        """Test string representation of URI."""
        uri = URI("http://example.com/Person")
        assert repr(uri) == "URI('http://example.com/Person')"

    def test_as_rdflib_uriref(self) -> None:
        """Test conversion to rdflib URIRef."""
        pytest.importorskip("rdflib")

        uri = URI("http://example.com/Person")
        uriref = uri.as_rdflib_uriref()

        assert isinstance(uriref, URIRef)
        assert str(uriref) == "http://example.com/Person"

    @pytest.mark.parametrize(
        "uri_str",
        [
            "http://example.com",
            "https://www.w3.org/2000/01/rdf-schema#Class",
            "https://schema.org/Person",
            "http://xmlns.com/foaf/0.1/name",
        ],
    )
    def test_various_uri_formats(self, uri_str: str) -> None:
        """Test creating URIs with various formats."""
        uri = URI(uri_str)
        assert str(uri) == uri_str
        assert uri.root == uri_str
