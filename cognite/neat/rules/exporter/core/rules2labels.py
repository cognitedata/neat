from cognite.neat.rules.models import TransformationRules


def get_labels(transformation_rules: TransformationRules) -> set[str]:
    """Return CDF labels for classes and relationships."""
    class_labels = {class_.class_id for class_ in transformation_rules.classes.values()}

    property_labels = {property_.property_id for property_ in transformation_rules.properties.values()}

    relationship_labels = {
        rule.label for rule in transformation_rules.properties.values() if "Relationship" in rule.cdf_resource_type
    }

    return class_labels.union(relationship_labels).union(property_labels)
