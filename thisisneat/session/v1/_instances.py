from typing import Any, cast

from cognite.client.utils.useful_types import SequenceNotStr

from thisisneat.core._client import NeatClient
from thisisneat.core._constants import NEAT
from thisisneat.core._instances import examples as instances_examples
from thisisneat.core._instances import extractors
from thisisneat.core._issues import IssueList
from thisisneat.core._utils.reader import NeatReader
from thisisneat.session._state import SessionState
from thisisneat.session.exceptions import session_class_wrapper


@session_class_wrapper
class InstancesAPI:
    """API for managing instances in NEAT session."""

    def __init__(self, state: SessionState) -> None:
        self._state = state
        self.read = ReadAPI(state)
        self.validate = ValidateAPI(state)


@session_class_wrapper
class ReadAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state
        self.examples = Examples(state)

    def rdf(self, io: Any) -> IssueList:
        self._state._raise_exception_if_condition_not_met(
            "Read RDF Instances",
            empty_data_model_store_required=True,
        )
        reader = NeatReader.create(io)
        self._state.instances.store.write(extractors.RdfFileExtractor(reader.materialize_path()))
        return IssueList()

    def raw(
        self,
        db_name: str,
        table_name: str,
        type: str | None = None,
        foreign_keys: str | SequenceNotStr[str] | None = None,
        unpack_json: bool = False,
        str_to_ideal_type: bool = False,
    ) -> IssueList:
        """Reads a raw table from CDF to the knowledge graph.

        Args:
            db_name: The name of the database
            table_name: The name of the table, this will be assumed to be the type of the instances.
            type: The type of instances in the table. If None, the table name will be used.
            foreign_keys: The name of the columns that are foreign keys. If None, no foreign keys are used.
            unpack_json: If True, the JSON objects will be unpacked into the graph.
            str_to_ideal_type: If True, the string values will be converted to ideal types.

        Returns:
            IssueList: A list of issues that occurred during the extraction.

        Example:
            ```python
            neat.read.cdf.raw("my_db", "my_table", "Asset")
            ```

        """
        self._state._raise_exception_if_condition_not_met(
            "Read RAW",
            client_required=True,
        )

        extractor = extractors.RAWExtractor(
            cast(NeatClient, self._state.client),
            db_name=db_name,
            table_name=table_name,
            table_type=type,
            foreign_keys=foreign_keys,
            unpack_json=unpack_json,
            str_to_ideal_type=str_to_ideal_type,
        )
        return self._state.instances.store.write(extractor)


@session_class_wrapper
class Examples:
    """Used as example for reading various sources into NeatSession."""

    def __init__(self, state: SessionState) -> None:
        self._state = state

    def nordic44(self) -> IssueList:
        """Reads the Nordic 44 knowledge graph into the NeatSession graph store."""

        self._state._raise_exception_if_condition_not_met(
            "Read Nordic44 graph example",
            empty_instances_store_required=True,
            empty_data_model_store_required=True,
        )

        self._state.instances.store.write(extractors.RdfFileExtractor(instances_examples.nordic44_knowledge_graph))
        return IssueList()


@session_class_wrapper
class ValidateAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def __call__(self, io: Any) -> tuple[bool, str, str]:
        """Here we should pass io which contains either shacl string, file path to shacl,
        or a rdflib graph containing the shacl shapes.

        If None, neat should generate shacl shapes out of conpceptual data model in the session.
        and then validate against the instances in the graph store.

        Conversion to shacl shapes should always aim at using instance source as
        first choice when comes to the actual URI of the class to which shapes relates
        to...

        """

        import pyshacl

        try:
            self._state.instances.store.graph(NEAT.ValidationGraph).parse(data=io)

        except Exception:
            self._state.instances.store.graph(NEAT.ValidationGraph).parse(io)

        conforms, report_graph, report_text = pyshacl.validate(
            data_graph=self._state.instances.store.graph(),
            shacl_graph=self._state.instances.store.graph(NEAT.ValidationGraph),
            inference="rdfs",
            debug=False,
            serialize_report_graph="ttl",
        )
        return conforms, report_graph.decode("utf-8"), report_text
