**Neat supports 11 validation rules** for data modeling. These rules are learned
 from best practice, knowledge of the Cognite Data Fusion data modeling service, and practical experience from
 helping customers build and maintain their data models.



### Connections (NEAT-DMS-CONNECTIONS)

Validators for connections in data model specifications.

| code | name | message |
|------|------|---------|
| NEAT-DMS-CONNECTIONS-001 | [ConnectionValueTypeExist](ConnectionValueTypeExist.md) | This validator checks whether connections value types (end node types) exist in the data model or in CDF. |
| NEAT-DMS-CONNECTIONS-002 | [ConnectionValueTypeNotNone](ConnectionValueTypeNotNone.md) | This validator checks whether connection value types are not None. |
| NEAT-DMS-CONNECTIONS-003 | [BidirectionalConnectionMisconfigured](BidirectionalConnectionMisconfigured.md) | This validator checks bidirectional connections to ensure reverse and direct connection pairs |

### Consistency (NEAT-DMS-CONSISTENCY)

Validators checking for consistency issues in data model.

| code | name | message |
|------|------|---------|
| NEAT-DMS-CONSISTENCY-001 | [ViewSpaceVersionInconsistentWithDataModel](ViewSpaceVersionInconsistentWithDataModel.md) | Validates that views have consistent space and version with the data model. |

### Limits (NEAT-DMS-LIMITS)

Validators for checking if defined data model is within CDF DMS schema limits.

| code | name | message |
|------|------|---------|
| NEAT-DMS-LIMITS-CONTAINER-001 | [ContainerPropertyCountIsOutOfLimits](ContainerPropertyCountIsOutOfLimits.md) | Validates that a container does not exceed the maximum number of properties. |
| NEAT-DMS-LIMITS-CONTAINER-002 | [ContainerPropertyListSizeIsOutOfLimits](ContainerPropertyListSizeIsOutOfLimits.md) | Validates that container property list sizes do not exceed CDF limits. |
| NEAT-DMS-LIMITS-DATA-MODEL-001 | [DataModelViewCountIsOutOfLimits](DataModelViewCountIsOutOfLimits.md) | Validates that the data model does not exceed the maximum number of views. |
| NEAT-DMS-LIMITS-VIEW-001 | [ViewPropertyCountIsOutOfLimits](ViewPropertyCountIsOutOfLimits.md) | Validates that a view does not exceed the maximum number of properties. |
| NEAT-DMS-LIMITS-VIEW-002 | [ViewContainerCountIsOutOfLimits](ViewContainerCountIsOutOfLimits.md) | Validates that a view does not reference too many containers. |
| NEAT-DMS-LIMITS-VIEW-003 | [ViewImplementsCountIsOutOfLimits](ViewImplementsCountIsOutOfLimits.md) | Validates that a view does not implement too many other views. |

### Views (NEAT-DMS-VIEW)

Validators for checking containers in the data model.

| code | name | message |
|------|------|---------|
| NEAT-DMS-VIEW-001 | [ViewToContainerMappingNotPossible](ViewToContainerMappingNotPossible.md) | Validates that container and container property referenced by view property exist. |
