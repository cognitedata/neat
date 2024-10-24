"""This module performs importing of various formats to one of serializations for which
there are loaders to TransformationRules pydantic class."""

from cognite.neat._rules.importers._rdf._base import BaseRDFImporter
from cognite.neat._rules.importers._rdf._shared import make_components_compliant

from ._owl2classes import parse_owl_classes
from ._owl2metadata import parse_owl_metadata
from ._owl2properties import parse_owl_properties


class OWLImporter(BaseRDFImporter):
    """Convert OWL ontology to tables/ transformation rules / Excel file.

        Args:
            filepath: Path to OWL ontology

    !!! Note
        OWL Ontologies are information models which completeness varies. As such, constructing functional
        data model directly will often be impossible, therefore the produced Rules object will be ill formed.
        To avoid this, neat will automatically attempt to make the imported rules compliant by adding default
        values for missing information, attaching dangling properties to default containers based on the
        property type, etc.

        One has to be aware that NEAT will be opinionated about how to make the ontology
        compliant, and that the resulting rules may not be what you expect.

    """

    def _to_rules_components(
        self,
    ) -> dict:
        components = {
            "Metadata": parse_owl_metadata(self.graph),
            "Classes": parse_owl_classes(self.graph),
            "Properties": parse_owl_properties(self.graph),
        }

        return make_components_compliant(components)
