from collections.abc import Iterable
from pathlib import Path
from unittest.mock import MagicMock

from rdflib import Literal, URIRef

from cognite.neat import NeatSession
from cognite.neat.core._instances.extractors import EventsExtractor
from cognite.neat.core._shared import Triple
from cognite.neat.core._utils.rdf_ import uri_to_cdf_id


class TestInstanceMapping:
    def test_instance_value_mapping(self) -> None:
        neat = NeatSession()
        filepath = MagicMock(spec=Path)
        filepath.read_text.return_value = [
            {"externalId": "my_event", "subtype": "SomeType"},
        ]
        extractor = EventsExtractor.from_file(file_path=filepath, as_write=True, identifier="externalId")

        neat._state.instances.store.write(extractor)

        issues = neat.mapping.instances.value_mapping({"SomeType": "AnotherType"}, property="subtype")
        assert len(issues) == 0

        triples = neat._state.instances.store.queries.select.list_triples(limit=5)
        assert set(clean_triples(triples)) == {
            ("Event_my_event", "type", "Event"),
            ("Event_my_event", "subtype", "AnotherType"),
            ("Event_my_event", "externalId", "my_event"),
        }


def clean_triples(triples: Iterable[Triple]) -> set[tuple[str, str, object]]:
    return {(uri_to_cdf_id(s), uri_to_cdf_id(p), _clean_uri_or_literal(o)) for s, p, o in triples}


def _clean_uri_or_literal(uri: URIRef | Literal) -> object:
    if isinstance(uri, Literal):
        return uri.toPython()
    if isinstance(uri, URIRef):
        return uri_to_cdf_id(uri)
    raise ValueError(f"Expected URIRef or Literal, got {type(uri)}: {uri}")
