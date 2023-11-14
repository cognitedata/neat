from cognite.neat.rules.models.rules import Rules


def get_labels(transformation_rules: Rules) -> set[str]:
    """
    Return CDF labels for classes and relationships.

    Args:
        transformation_rules: The transformation rules to extract labels from.

    Returns:
        Set of CDF labels
    """
    class_labels = {class_.class_id for class_ in transformation_rules.classes.values()}

    property_labels = {property_.property_id for property_ in transformation_rules.properties.values()}

    relationship_labels = {
        str(rule.label)
        for rule in transformation_rules.properties.values()
        if "Relationship" in rule.cdf_resource_type and rule.label
    }

    return class_labels.union(relationship_labels).union(property_labels)
