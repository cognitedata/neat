query_templates = [
    {"name": "Get all classes", "query": "SELECT DISTINCT ?class WHERE { ?s a ?class }"},
    {
        "name": "Get all classes with stats",
        "query": "SELECT ?class (count(?s) as ?instances ) "
        "WHERE { ?s a ?class . } group by ?class order by DESC(?instances)",
    },
    {"name": "Describe object", "query": " DESCRIBE <http://cog.com/neat#_30b297b4-8e19-da40-9f52-fb9175136a22>"},
    {"name": "Count all classes", "query": " SELECT (COUNT(DISTINCT ?class) AS ?count) WHERE { ?s a ?class }"},
    {"name": "Get all instances", "query": " SELECT DISTINCT ?s ?class WHERE { ?s a ?class }"},
    {"name": "Count all instances", "query": " SELECT (COUNT(DISTINCT ?s) AS ?count) WHERE { ?s a ?class }"},
    {"name": "Get all properties", "query": " SELECT DISTINCT ?p WHERE { ?s ?p ?o }"},
    {"name": "Count all properties", "query": " SELECT (COUNT(DISTINCT ?p) AS ?count) WHERE { ?s ?p ?o }"},
    {
        "name": "Get all properties of a class",
        "query": " SELECT DISTINCT ?property WHERE { ?s a ?class . ?s ?property ?o }",
    },
    {
        "name": "Get all properties of an instance",
        "query": " SELECT DISTINCT ?property WHERE { ?instance a ?class . ?instance ?property ?o }",
    },
    {
        "name": "Get all properties of a class and their values",
        "query": " SELECT DISTINCT ?property ?value WHERE { ?s a ?class . ?s ?property ?value }",
    },
    {
        "name": "Get all properties of an instance and their values",
        "query": " SELECT DISTINCT ?property ?value WHERE { ?instance a ?class . ?instance ?property ?value }",
    },
    {
        "name": "Get all properties of a class and their values (with type)",
        "query": """ SELECT DISTINCT ?property ?value ?type
            WHERE { ?s a ?class . ?s ?property ?value . ?value a ?type }""",
    },
    {
        "name": "Get all properties of an instance and their values (with type)",
        "query": """ SELECT DISTINCT ?property ?value ?type
            WHERE {?instance a ?class . ?instance ?property ?value . ?value a ?type }""",
    },
    {
        "name": "Get all properties of a class and their values (with type and label)",
        "query": """ SELECT DISTINCT ?property ?value ?type ?label
                      WHERE { ?s a ?class . ?s ?property ?value . ?value a ?type . ?value rdfs:label ?label }""",
    },
    {
        "name": "Get all properties of an instance and their values (with type and label)",
        "query": """ SELECT DISTINCT ?property ?value ?type ?label
            WHERE { ?instance a ?class . ?instance ?property ?value . ?value a ?type . ?value rdfs:label ?label }""",
    },
    {
        "name": "Get all properties of a class and their values (with type and label) (with type and label)",
        "query": """ SELECT DISTINCT ?property ?value ?type ?label
            WHERE { ?s a ?class . ?s ?property ?value . ?value a ?type . ?value rdfs:label ?label }""",
    },
    {
        "name": "Get all properties of an instance and their values (with type and label) (with type and label)",
        "query": """ SELECT DISTINCT ?property ?value ?type ?label
            WHERE { ?instance a ?class . ?instance ?property ?value . ?value a ?type . ?value rdfs:label ?label }""",
    },
    {
        "name": "Get list of all properties of Substations",
        "query": "SELECT ?subject ?p ?object "
        "WHERE { ?subject a cim:Substation . ?subject ?p ?object . } "
        "order by ?subject limit 12",
    },
    {
        "name": "Get all properties of the node",
        "query": "SELECT ?predicate ?object "
        "WHERE { <http://neat-cog.com/#_fbf1e5dc-2ce7-ec2a-e040-1e828c9489bf> ?predicate ?object . }",
    },
    {
        "name": "Get all properties of the node and performing 2 level traversal",
        "query": "SELECT ?property1 ?value1 ?property2 ?value2 WHERE "
        "{ <http://neat-cog.com/#_fbf1e5dc-2ce7-ec2a-e040-1e828c9489bf> ?property1 ?value1 . "
        "OPTIONAL { ?value1 ?property2 ?value2 } }",
    },
    {
        "name": "Get graph compatible query",
        "query": """
SELECT (?parentName AS ?node_name)  (?parentClass AS ?node_class) ?parentPath (?parentInst AS ?node_id )
 (?parentInst AS ?src_object_ref) (?parentInst2 AS ?dst_object_ref) WHERE {
 ?tagInst a neat:AttributeTag .
 ?tagInst neat:Path ?tagPath .
 ?tagInst neat:Value ?tagValue .
 ?tagInst neat:hasParent+ ?parentInst .
 ?parentInst neat:Name ?parentName .
 ?parentInst neat:Path ?parentPath .
 ?parentInst a ?parentClass .
 ?parentInst neat:hasParent ?parentInst2
  }  limit 100""",
    },
]
