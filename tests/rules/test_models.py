from datetime import datetime

from rdflib import Namespace

from cognite.neat.rules.models import Classes, Metadata, Properties, TransformationRules


def tests_create_empty_rules():
    metadata = Metadata(
        title="Dummy Title",
        description="A description",
        version="0_1",
        creator="Cognite",
        created=datetime.utcnow(),
        namespace=Namespace("http://purl.org/cognite/neat#"),
        prefix="neat",
        cdf_space_name="MySpace",
        data_model_name="MyDataModel",
    )
    classes = Classes()
    properties = Properties()

    # Act
    rules = TransformationRules(metadata=metadata, classes=classes, properties=properties, prefixes={}, instances=[])

    # Assert
    # Main point is that the rules are created without errors
    assert rules.metadata.title == "Dummy Title"
