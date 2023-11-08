# Rule Types in NEAT

In NEAT we have are currently supporting two types of rules, namely `sparql`, `rdfpath` and `rawlookup`. `rdfpath` rules resolve in SPARQL queries which are executed against `rdf` knowledge graph typically stored in triple/rdf graph databases such as GraphDB or Jena Fuseki. In NEAT we have 4 different types of `rdfpath` rules which we use in different situations to transform the source knowledge graph to the targeted knowledge graph. In this post we will go through each of them and explain them.

On the other side, `rawlookup` resolves as query against `rdf` knowledge graph, typically fetching references of object via SPARQL query, and query against CDF RAW. This type of rules are used typically  to enrich the target knowledge graph with the information which were not present in the source knowledge graph, though they can also serve as a transformation of non linked data to linked data.

Before we deep dive in explaining the two rule types it is worth at this point to introduce concept of prefixes, namespaces and entity (being classes, properties, instances) references. Throughout this post you will notice that we are using the following notation:

```
prefix:EntityName
```

where `prefix` is short name of a namespace in which the entity is defined and `EntityName` is the name of the entity. Together they form entity reference, which is a globally unique identifier (URI) for given entity. For example in case of the entity `cim:Substation`, prefix `cim` corresponds to namespace `http://iec.ch/TC57/2013/CIM-schema-cim16#`, while `Substation` corresponds to a specific class in the cim namespace.

SPARQL engine translates this short form into http://iec.ch/TC57/2013/CIM-schema-cim16#Substation. As one can see, the short form is much more
readable and easier to write than the long URI.

## `sparql` rule
The most flexible rule type in NEAT. It basically contains raw SPARQL query which is executed against the source knowledge graph. The result of the query is then used to create triples in the target knowledge graph. You have fully flexibility to define the query, however, you need to be aware of the following:
- The query must return three columns: `subject`, `predicate` and `object`
- Currently NEAT is not capable of detecting syntax errors

Therefore, it is recommended to use `sparql` rule type only when you are familiar with SPARQL and you know what you are doing.
Use [Data Exploration](./ui-data-exploration.md) to test your query and make sure it returns the expected results before you use it in the rule.

## `rdfpath` rule: SingleProperty
This query type is used to get a single property from all class instances. It is defined in the Excel file by `rdfpath` value `prefix:ClassName(prefix:PropertyName)`.

Let's look at one row of Excel file in the **Properties** sheet:

| Class      | Property | ... | Rule Type | Rule              |
| ---------- | -------- | --- | --------- | ----------------- |
| Substation | mRID       | ... | rdfpath   | cim:Substation(IdentifiedObject.mRID)    |

This row defines a query that will get all values of property `IdenetifiedObject.mRID` of all `Substation` instance from the source graph (also known as domain graph) and store them as values of property `mRID` of `Substation` instances in the target graph (also known as solution or application graph).

Beware that the property and class references in the target graph will use the target graph prefix and namespace. The prefix and namespace are derived using the field `shortName` in the **Metadata** sheet, which defines the prefix, combined with the base URI `http://purl.org/cognite/` to form the namespace such as `http://purl.org/cognite/shortName#`.

We omit to write prefix when we define target classes and properties, thus we consider the target prefix to be implicit. However, the original references of the source objects will be used in the target graph (e.g., references of substation instances). The retention of original references (i.e., avoiding to rename their original namespace to target namespace) helps debugging and comparing objects between graphs.

The query is defined by `rdfpath` value `cim:Substation(IdentifiedObject.mRID)`.

`NEAT` converts rdfpath` value `cim:Substation(IdentifiedObject.mRID)` into the following SPARQL query:
```sparql
PREFIX cim: <http://iec.ch/TC57/2013/CIM-schema-cim16#>

SELECT DISTINCT ?subject ?predicate ?object
    WHERE {
        ?subject a cim:Substation .
        ?subject cim:IdentifiedObject.mRID ?object .
        BIND(cim:IdentifiedObject.mRID AS ?predicate)
        }
```

The above query will result in triples (subject, predicate, object), where:
- Subject is the reference of the instance
- Predicate is the property which value we are looking to get
- Object is the value of the property

Here is an example of the result:

| subject                                                                 | predicate                                                                 | object                                                                 |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| cim:Substation.1                 | cim:IdentifiedObject.mRID                        | "f176964e-9aeb-11e5-91da-b8763fd99c5f"                 |
| cim:Substation.2                 | cim:IdentifiedObject.mRID                        | "b176964e-9aeb-11e5-91da-b8763fd99c5f"                 |

as mentioned `NEAT` will convert predicate to the target namespace and prefix. In this case the predicate will be `http://purl.org/cognite/shortName#IdentifiedObject.mRID`, or in short `shortName:IdentifiedObject.mRID`.


## `rdfpath` rule: AllReferences
This query type is used to get references of all instance of a given class. It is defined in the Excel file by `rdfpath` value `prefix:ClassName`. Let's look at one row of Excel file in **Properties** sheet:

| Class      | Property | ... | Rule Type | Rule              |
| ---------- | -------- | --- | --------- | ----------------- |
| Substation | mRID       | ... | rdfpath   | cim:Substation    |

This row defines a query that will get all references of all `Substation` instance from the source graph (also known as domain graph) and store them as values of property "mRID" of Substation instances in the target graph (also known as solution or app graph). The query is defined by `rdfpath` value `cim:Substation`.

`NEAT` will in return create this SPARQL query:
```sparql
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX cim: <http://iec.ch/TC57/2013/CIM-schema-cim16#>

SELECT DISTINCT ?subject ?predicate ?object
    WHERE {
    		?subject a cim:Substation
                {
                BIND(?subject AS ?object)
                BIND(dct:identifier AS ?predicate)
                }
          }

```
One can notice that we have the BIND statements. These BIND statements are guarantee that the result of the query will be list of triples (subject, predicate, object), where:
- Subject is the reference of the instance
- Predicate is dct:identifier, which is used as temporarily predicate before it is converted to the target property
- Object is also the reference of the instance

Here is an example of the result:

| subject                                                                 | predicate                                                                 | object                                                                 |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| cim:Substation.1                 | dct:identifier                        | cim:Substation.1                 |
| cim:Substation.2                 | dct:identifier                        | cim:Substation.2                 |


In the follow up step, `NEAT` will convert the predicate to the target namespace and prefix. In this case the predicate will be `http://purl.org/cognite/shortName#IdentifiedObject.mRID`, or in short `shortName:IdentifiedObject.mRID`.

This query type if often used as convenience in case when for example we are missing some properties in the source graph and we want to get them in the target graph. For example, in case of a TSO customer, there was a number of class instances which were missing mRID property. We have created them in the target graph using the above rule example, where we in addition specify that the namespace should be dropped, so converting URI to literal value. For example, cim:Substation.1 will be converted to "Substation.1".


## `rdfpath` rule: AllProperties
This query type is used to get all properties of all instance of a given class. It is defined in the Excel file by `rdfpath` value `*`.
Let's look at one row of Excel file in **Properties** sheet:


| Class      | Property | ... | Rule Type | Rule              |
| ---------- | -------- | --- | --------- | ----------------- |
| Substation | *        | ... | rdfpath   | cim:Substation(*) |

This row defines a query that will get all properties of all `Substation` instance. The query is defined by `rdfpath` value `cim:Substation(*)`. The `*` character is a wildcard that means that we want to get all properties of a given class instance.

`NEAT` will in return create this SPARQL query:
```sparql
PREFIX cim: <http://iec.ch/TC57/2013/CIM-schema-cim16#>

SELECT DISTINCT ?subject ?predicate ?object
    WHERE {
        ?subject a cim:Substation .
        ?subject ?predicate ?object .
        }
```

The above query will result in triples (subject, predicate, object) that define all `Substation` instances. Here is an example of the result:

| subject                                                                 | predicate                                                                 | object                                                                 |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| <cim:Substation.1>                 | <rdf:type>                        | <cim:Substation>                 |
| <cim:Substation.1>                 | <cim:Substation.Region>            | <cim:SubGeographicalRegion.1>     |
| <cim:Substation.1>                 | <cim:Substation.EquipmentContainer> | <cim:VoltageLevel.1>             |
| <cim:Substation.1>                 | <cim:IdentifiedObject.name>        | "Substation 1"                                                        |
| <cim:Substation.1>                 | <cim:IdentifiedObject.description> | "Substation 1"                                                        |
| <cim:Substation.1>                 | <cim:IdentifiedObject.mRID>        | "Substation.1"                                                        |



This `rdfpath` rule and corresponding query is discouraged since it can result in a huge amount of data. Also, since we are not controlling in what corresponding property it will land in the solution graph, it can result in a lot of duplicates. In addition, the original property references will not be converted to the target namespace and prefix. For example, `cim:Substation.Region` will not be converted to `shortName:Substation.Region`.

## `rdfpath` rule: Hop
This query type is used to traverse (aka hop) the source graph and get desired class instance references or some their properties.

> Hops which fetch all the properties are not yet supported in `NEAT`.

### Hop which fetches all references
In the most typical scenario we are extracting desired class instances from the source graph and storing them in the target graph under new property which did not existed in the source graph. By doing this we are "shortening" the path and query time in the target graph. This process also "flattens" the target graph in comparison to the source graph.

Let's look at picture bellow to see how this works:

![Hop](./figs/multi-hop.png)

In the above picture we are hopping (i.e. graph traversing) from `Terminal` to `Substation` via intermediate nodes `ConnectivityNode` and `VoltageLevel`. Our desire is to extract connections between terminals and substations and make them directly connected in the target graph. As we can see from the picture, our graph is directional, so there are properties which connect:
- `Terminal` to `ConnectivityNode`
- `ConnectivityNode` to `VoltageLevel`
- `VoltageLevel` to `Substation`

Accordingly, we have `rdfpath` rules which define the hops as shown in the one of the rows of Excel file in **Properties** sheet:

| Class      | Property | ... | Rule Type | Rule              |
| ---------- | -------- | --- | --------- | ----------------- |
| Terminal   | Terminal.Substation    | ... | rdfpath   | cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation |


One can notice that arrows "->" indicate directions that nodes are connected. These arrows tell `NEAT` to besides generating SPARQL query also find and insert properties for us (so we do not need to know them by heart).

The resulting SPARQL query for the above rule looks like this:

```sparql
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX cim: <http://iec.ch/TC57/2013/CIM-schema-cim16#>

SELECT DISTINCT ?subject ?predicate ?object
    WHERE { ?subject a cim:Terminal .
            ?subject cim:Terminal.ConnectivityNode ?ConnectivityNodeID .
            ?ConnectivityNodeID cim:ConnectivityNode.ConnectivityNodeContainer ?VoltageLevelID .
            ?VoltageLevelID cim:VoltageLevel.Substation ?object .
            ?object a cim:Substation .
            BIND(dct:relation AS ?predicate) }


        }
```

The above query will result in triples (subject, predicate, object) that define all `Terminal` instances and their `Substation` references. Here is an example of the result:

| subject                                                                 | predicate                                                                 | object                                                                 |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| <cim:Terminal.1>                 | <dct:relation>                        | <cim:Substation.1>                 |
| <cim:Terminal.2>                 | <<dct:relation>                        | <cim:Substation.1>                 |
| <cim:Terminal.3>                 | <dct:relation>                        | <cim:Substation.2>                 |



Yet again here, similarly like in case of `AllReferences`, we are using `dct:relation` as a temporary predicate. In the follow up step, `NEAT` will convert the predicate to the target property `Terminal.Substation` with the corresponding namespace and prefix. In this case the predicate will be `http://purl.org/cognite/shortName#Terminal.Substation`, or in short `shortName:Terminal.Substation`.

The hop rdfpath can be bidirectional, example in case when we want to check to what `ACLineSegment`s `Substation`s are connected:
```
cim:Substation<-cim:VoltageLevel<-cim:ConnectivityNode<-cim:Terminal->cim:ACLineSegment
```

which results in the following SPARQL query:
```sparql
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX cim: <http://iec.ch/TC57/2013/CIM-schema-cim16#>

SELECT DISTINCT ?subject ?predicate ?object WHERE {
    ?subject a cim:Substation . ?VoltageLevelID
    cim:VoltageLevel.Substation ?subject .
    ?ConnectivityNodeID cim:ConnectivityNode.ConnectivityNodeContainer ?VoltageLevelID .
    ?TerminalID cim:Terminal.ConnectivityNode ?ConnectivityNodeID .
    ?TerminalID cim:Terminal.ConductingEquipment ?ACLineSegmentID .
    ?object a cim:ACLineSegment
    BIND(dct:relation AS ?predicate) }
```

### Hop which fetches single property
The above hop rule can be extended to grab a specific propety for example `cim:IdentifiedObject.name`:
```
cim:Substation<-cim:VoltageLevel<-cim:ConnectivityNode<-cim:Terminal->cim:ACLineSegment(cim:IdentifiedObject.name)
```

which results in the following SPARQL query:
```sparql
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX cim: <http://iec.ch/TC57/2013/CIM-schema-cim16#>

SELECT DISTINCT ?subject ?predicate ?object WHERE {
    ?subject a cim:Substation . ?VoltageLevelID
    cim:VoltageLevel.Substation ?subject .
    ?ConnectivityNodeID cim:ConnectivityNode.ConnectivityNodeContainer ?VoltageLevelID .
    ?TerminalID cim:Terminal.ConnectivityNode ?ConnectivityNodeID .
    ?TerminalID cim:Terminal.ConductingEquipment ?ACLineSegmentID .
    ?ACLineSegmentID a cim:ACLineSegment .
    ?ACLineSegmentID cim:IdentifiedObject.name ?object .
    BIND(cim:IdentifiedObject.name AS ?predicate) }
```

## `rawlookup` rule

Example of rawlookup rule:  `cim:Substation(cim:IdentifiedObject.name) | substation_code_lookup(NAME,CODE)`

- cim:Substation(cim:IdentifiedObject.name) - rdfpath rule which will fetch all Substation instances and their names from the graph . The name is used as key for the lookup
- substation_code_lookup(NAME,CODE) - substation_code_lookup is a name of the table in CDF RAW. The lookup table has at least two columns NAME and CODE . The NAME column is used as key for the lookup, while the CODE column is used as value for the lookup.



<!-- Anders Albert to write this section. -->
