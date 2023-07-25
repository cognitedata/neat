from cognite.neat.rules.models import TransformationRules


def get_instances_as_triples(transformation_rules: TransformationRules) -> list[tuple]:
    """Converts transformation rules instances sheet to RDF triples

    Parameters
    ----------
    transformation_rules : TransformationRules
        An instance of TransformationRules pydantic class

    Returns
    -------
    list[tuple]
        List of triples provided as tuples
    """
    if transformation_rules.instances:
        return [(instance.instance, instance.property_, instance.value) for instance in transformation_rules.instances]
    else:
        return []
