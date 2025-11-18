**Neat supports 19 validation rules** for data modeling. These rules are learned
 from best practice, knowledge of the Cognite Data Fusion data modeling service, and practical experience from
 helping customers build and maintain their data models.



### Connections (NEAT-DMS-CONNECTIONS)

Validators for connections in data model specifications.

| code | name | message |
|------|------|---------|
| NEAT-DMS-CONNECTIONS-001 | [ConnectionValueTypeUnexisting](NEAT-DMS-CONNECTIONS-001.md) | Validates that connection value types exist. |
| NEAT-DMS-CONNECTIONS-002 | [ConnectionValueTypeUndefined](NEAT-DMS-CONNECTIONS-002.md) | Validates that connection value types are not None, i.e. undefined. |
| NEAT-DMS-CONNECTIONS-REVERSE-001 | [ReverseConnectionSourceViewMissing](NEAT-DMS-CONNECTIONS-REVERSE-001.md) | Validates that source view referenced in reverse connection exist. |
| NEAT-DMS-CONNECTIONS-REVERSE-002 | [ReverseConnectionSourcePropertyMissing](NEAT-DMS-CONNECTIONS-REVERSE-002.md) | Validates that source property referenced in reverse connections exist. |
| NEAT-DMS-CONNECTIONS-REVERSE-003 | [ReverseConnectionSourcePropertyWrongType](NEAT-DMS-CONNECTIONS-REVERSE-003.md) | Validates that source property for the reverse connections is a direct relation. |
| NEAT-DMS-CONNECTIONS-REVERSE-004 | [ReverseConnectionContainerMissing](NEAT-DMS-CONNECTIONS-REVERSE-004.md) | Validates that the container referenced by the reverse connection source properties exist. |
| NEAT-DMS-CONNECTIONS-REVERSE-005 | [ReverseConnectionContainerPropertyMissing](NEAT-DMS-CONNECTIONS-REVERSE-005.md) | Validates that container property referenced by the reverse connections exists. |
| NEAT-DMS-CONNECTIONS-REVERSE-006 | [ReverseConnectionContainerPropertyWrongType](NEAT-DMS-CONNECTIONS-REVERSE-006.md) | Validates that the container property used in reverse connection is the direct relations. |
| NEAT-DMS-CONNECTIONS-REVERSE-007 | [ReverseConnectionTargetMissing](NEAT-DMS-CONNECTIONS-REVERSE-007.md) | Validates that the direct connection in reverse connection pair have target views specified. |
| NEAT-DMS-CONNECTIONS-REVERSE-008 | [ReverseConnectionPointsToAncestor](NEAT-DMS-CONNECTIONS-REVERSE-008.md) | Validates that direct connections point to specific views rather than ancestors. |
| NEAT-DMS-CONNECTIONS-REVERSE-009 | [ReverseConnectionTargetMismatch](NEAT-DMS-CONNECTIONS-REVERSE-009.md) | Validates that direct connections point to the correct target views. |

### Consistency (NEAT-DMS-CONSISTENCY)

Validators checking for consistency issues in data model.

| code | name | message |
|------|------|---------|
| NEAT-DMS-CONSISTENCY-001 | [ViewSpaceVersionInconsistentWithDataModel](NEAT-DMS-CONSISTENCY-001.md) | Validates that views have consistent space and version with the data model. |

### Limits (NEAT-DMS-LIMITS)

Validators for checking if defined data model is within CDF DMS schema limits.

| code | name | message |
|------|------|---------|
| NEAT-DMS-LIMITS-CONTAINER-001 | [ContainerPropertyCountIsOutOfLimits](NEAT-DMS-LIMITS-CONTAINER-001.md) | Validates that a container does not exceed the maximum number of properties. |
| NEAT-DMS-LIMITS-CONTAINER-002 | [ContainerPropertyListSizeIsOutOfLimits](NEAT-DMS-LIMITS-CONTAINER-002.md) | Validates that container property list sizes do not exceed CDF limits. |
| NEAT-DMS-LIMITS-DATA-MODEL-001 | [DataModelViewCountIsOutOfLimits](NEAT-DMS-LIMITS-DATA-MODEL-001.md) | Validates that the data model does not exceed the maximum number of views. |
| NEAT-DMS-LIMITS-VIEW-001 | [ViewPropertyCountIsOutOfLimits](NEAT-DMS-LIMITS-VIEW-001.md) | Validates that a view does not exceed the maximum number of properties. |
| NEAT-DMS-LIMITS-VIEW-002 | [ViewContainerCountIsOutOfLimits](NEAT-DMS-LIMITS-VIEW-002.md) | Validates that a view does not reference too many containers. |
| NEAT-DMS-LIMITS-VIEW-003 | [ViewImplementsCountIsOutOfLimits](NEAT-DMS-LIMITS-VIEW-003.md) | Validates that a view does not implement too many other views. |

### Views (NEAT-DMS-VIEW)

Validators for checking containers in the data model.

| code | name | message |
|------|------|---------|
| NEAT-DMS-VIEW-001 | [ViewToContainerMappingNotPossible](NEAT-DMS-VIEW-001.md) | Validates that container and container property referenced by view property exist. |
