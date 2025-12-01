The legacy `NEAT` (v0.x) has a lot of capabilities that are not yet implemented in `NEAT` (v1.x). The focus of v1.0 was solely on the physical data modeling read, validation and write.

The roadmap below outlines the planned features packages for future releases of `NEAT` (v1.x) which will robustify and productify all the legacy capabilities while introducing new features and improvements.

Users are encouraged to contribute to the roadmap by suggesting and prioritizing features or improvements that would enhance their experience with `NEAT`. Feedback and suggestions can be submitted through:

- Slack: [#neat-help](https://app.slack.com/client/T3XCNGHJL/C049R6DG3HR)
- Jira: [NEAT Project Board](https://cognitedata.atlassian.net/jira/software/projects/THIS/boards/3021)


## Planned Feature Packages for NEAT (v1.x)

### Data Model Fix
Automatically fix validation issues in the data model based on predefined rules and best practices.


JIRA Epic: [THIS-935](https://cognitedata.atlassian.net/browse/THIS-935)

Legacy availability: Limited, see [documentation](reference/legacy/NeatSession/fix.md)


### Conceptual Data Modeling
NEAT will support the creation and management of Conceptual Data Models (CDM) that serve as high-level, business-oriented representations of data structures, which can be seamlessly converted and linked to Physical Data Models for implementation in CDF. The tooling will intelligently resolve different types of relationships—whether they should be implemented as direct relations, edges, or reverse properties—based on the modeling context and best practices. Additionally, NEAT will enable users to extend not only the Core Data Model (CDM) but any existing data model in CDF, providing flexibility to build upon and customize standard models while maintaining consistency and traceability between conceptual and physical representations.

JIRA Epic: [THIS-800](https://cognitedata.atlassian.net/browse/THIS-800)

Legacy availability: Yes, see [this tutorial](tutorials/legacy/data-modeling/from-conceptual-to-physical-via-CDM.ipynb)


### Data Model Inference
Ability to infer data model directly from data (instances) without the need to define the model explicitly.

JIRA Epic: [THIS-936](https://cognitedata.atlassian.net/browse/THIS-936)

Legacy availability: Yes, [see reference documentation](reference/legacy/NeatSession/base.md#cognite.neat.v0.session.NeatSession.infer)


### Data Model Population
Population of the CDF data model without a need for CDF Transformations and CDF RAW.

JIRA Epic: [THIS-818](https://cognitedata.atlassian.net/browse/THIS-818)

Legacy availability: Yes, [see reference documentation](reference/legacy/NeatSession/to.md#cognite.neat.v0.session._to.CDFToAPI.instances)

### Plugins
Support for plugins to extend NEAT's functionality especially for custom data model readers and writers. This feature package entails refactoring of NeatEngine, an RML engine, which provides creation of instances without the need to create custom extractors.

JIRA Epic: [THIS-805](https://cognitedata.atlassian.net/browse/THIS-805)

Legacy availability: Yes, [see CFIHOS handler plugin](https://github.com/thisisneat-io/cfihos-handler)

### Governance and Version Control
Support for user defined data model versioning and governance profiles to ensure compliance with organizational or global defined best practices.

JIRA Epic: [THIS-825](https://cognitedata.atlassian.net/browse/THIS-825)

Legacy availability: No

### Semantic Data Modeling
Lossless reading and writing of semantic data modeling in/from NeatSession including support for OWL ontologies and SHACL shapes.

JIRA Epic: [THIS-808](https://cognitedata.atlassian.net/browse/THIS-808)

Legacy availability: Partially supported, see [reference documentation](reference/legacy/NeatSession/to.md#cognite.neat.v0.session._read.RDFReadAPI.ontology)

### Instance Validation
Validation of data model instances against SHACL shapes to ensure data integrity and compliance with defined schemas.

JIRA Epic: [THIS-826](https://cognitedata.atlassian.net/browse/THIS-826)
Legacy availability: No



