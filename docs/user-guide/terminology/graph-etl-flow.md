# Graph ETL Flow
The Graph ETL (Extract, Transform, Load) flow in NEAT is a systematic flow that involves extracting graph from a source system/format, optionally transforming this graph by reducing complexity, enriching it with additional information, and then loading the transformed or original graph into Cognite Data Fusion. This process facilitates the efficient manipulation and loading of graph data, enabling users to form knowledge base in Cognite Data Fusion. The ETL flow is divided into three main stages: the Extractor, the Transformer, and the Loader.

To use Graph ETL Flow one needs to have compliant `Rules` extended with configuration of graph ETL through combination of `rdfpath`, `sparql` and/or `rawlookup` directives (aka transformation rules).

![NEAT High Level](./artifacts/figs/graph-etl-flow.png)

## Extractor
It is worth to mention that all the extractors have one aim and that is to extract RDF triples from source to [NeatGraphStore](./api/graph/stores.md#neatgraph-store). In some cases a certain conversion of source data to triples is performed.

### RDF Extractor
The RDF Extractor is a component of the Graph ETL flow in NEAT. It is responsible for extracting RDF triples from RDF (Resource Description Framework) sources. RDF is a standard model for data interchange on the Web. The RDF Extractor reads RDF data, which can be in various formats such as XML, Turtle, or JSON-LD, and load them to `NeatGraphStore`, which is then used in the rest of the Graph ETL flow. The most simplest use-case is to extract triples from a RDF file dump.

### Graph Capturing Sheet Extractor
This extractor extracts triples from a tailored spreadsheet template generated based on data model described in `Rules`. More details about this extractor can be found in [the reference documentation](./api/graph/extractors.md#cognite.neat.graph.extractors.graph_sheet_to_graph.extract_graph_from_sheet).

### DMS Extractor
This extractor extracts triples from nodes and edges stored in Cognite's Data Model Storage. Basically this extractor has also a role of converting nodes and edges to a set of triples which can be loaded to `NeatGraphStore` for downstream processing and transformations.

!!! note annotate "WIP"

    This extractor is work in progress, and it not in general availability!


## Source Graph
Source graph is stored in [NeatGraphStore](./api/graph/stores.md#neatgraph-store) that can be configured as:

- internal `in-memory` or `on-disk` RDF triple store
- remote RDF triple store (requires connection to the remote [SPARQL endpoint](https://medium.com/virtuoso-blog/what-is-a-sparql-endpoint-and-why-is-it-important-b3c9e6a20a8b))


## Transformer
NEAT contains its own transformation engine which, as mentioned earlier, is configured through `Rules` via [transformation rules](./transformation-directive-types.md). Predominately, the transformation engine leverages on graph traversal via `SPARQL` queries against the source graph. These queries are either explicitly stated through `sparql` directives, or implicitly constructed using `rdfpath` ([see more details](./transformation-directive-types.md#rdfpath-rule-singleproperty)). The library module for this step in the graph ETL flow consists of a single method which is described in more details in [the reference library](./api/graph/transformers.md).


## Transformed Graph
The derived transformed graph also makes use of `NeatGraphStore`.

## Loader
Opposite to Extractors, loaders resolve RDF triples stored in `NeatGraphStore` to downstream Cognite Data Fusion representations.

### Asset Hierarchy Loader
Asset hierarchy loader turns RDF triples to CDF asset hierarchy and relations among the assets. This downstream representation is also known as classic CDF, as it was the first data model representation in Cognite Data Fusion.


### DMS Loader
DMS loader turns RDF triples in set of nodes and edges which are stored in DMS.

### RDF Loader
Optionally RDF triples stored in the `NeatGraphStore` can be exported as an RDF drop for later use.

!!! note annotate "WIP"

    This extractor is work in progress, and it not in general availability!
