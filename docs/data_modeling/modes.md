NEAT supports two modes of data modeling: additive and rebuild. Depending on the selected mode, the behavior of NEAT when deploying changes to a data model in Cognite Data Fusion (CDF) will vary. NEAT classifies changes to the data model into three severity levels:

- ✅ `SAFE`: allowed changes that do not impact existing data or functionality
- ⚠️ `WARNING`: allowed changes where caution is advised, as they may have implications
- ❌ `BREAKING`: disallowed changes, which would not be applied to CDF


In the following sections, we describe the characteristics of each mode and provide detailed tables outlining the allowed and disallowed changes for each severity level.


!!! warning "Changes can be done only in the data model space"
    It is important to know that NEAT will only consider changes to the data model components (aka DMS schema components) in the same space as the data model itself. Any change outside of the data model space will be ignored. The reason for this is to avoid accidental changes to data models that have different owners or are managed by different teams.


## Additive Mode

Key characteristics of the additive mode are:

- Forward compatibility: old versions of applications and services can work with the updated data model without requiring changes.
- Incremental changes: data model changes are applied incrementally, allowing for gradual evolution of the data model.
- Suitable for production environments: this mode is ideal for production systems where stability and forward compatibility are crucial.


The following table summarizes the allowed and disallowed changes in additive mode:

| Severity | Operation | Change Description | Example |
|----------|-----------|-------------------|---------|
| **SAFE** | Create | Data model | - |
| **SAFE** | Create | View | Entire views, new properties, filters |
| **SAFE** | Create | Container | Entire containers, new properties, indexes and constraints |
| **SAFE** | Create | New enums to existing enum properties | - |
| **SAFE** | Update | Data model metadata | Name, description, version |
| **SAFE** | Update | Data model's view order | - |
| **SAFE** | Update | View metadata | Name, description, version |
| **SAFE** | Update | Container metadata | Name, description |
| **SAFE** | Update | Property metadata | Name, description |
| **SAFE** | Update | Enums metadata | Name, description |
| **WARNING** | Update | View filters | - |
| **WARNING** | Update | Edge type | - |
| **WARNING** | Update | Source property for reverse connection | Also known as `through` in CDF API |
| **WARNING** | Remove | Container constraints | - |
| **WARNING** | Remove | Container indexes | - |
| **WARNING** | Update | Mutability of container properties | - |
| **WARNING** | Update | Auto-increment of container properties | - |
| **WARNING** | Update | Default value of container properties | - |
| **WARNING** | Update | Max count of listable properties | - |
| **WARNING** | Remove | Container property unit | Removing `meter` from a property |
| **WARNING** | Add | Container property unit | Adding `meter` to a property that did not have a unit before |
| **BREAKING** | Delete | Existing data model | - |
| **BREAKING** | Delete | View reference from the data model | - |
| **BREAKING** | Delete | Existing view | - |
| **BREAKING** | Add | Implements to an existing view | - |
| **BREAKING** | Delete | Property from an existing view | - |
| **BREAKING** | Update | Mapping of view (property) to container (property) | - |
| **BREAKING** | Update | Direct/reverse connection value type | Also known as `source` in CDF API |
| **BREAKING** | Update | Edge source of properties | Setting new view as source of properties |
| **BREAKING** | Update | Edge direction | - |
| **BREAKING** | Update | Connection type | From edge to direct connection |
| **BREAKING** | Update | What container is used for | Switching `usedFor` from `node` to `edge` |
| **BREAKING** | Update | Value type of container property | From `text` to `integer` |
| **BREAKING** | Update | Container constraint definitions | `uniqueness` constraint property `bySpace` cannot be changed |
| **BREAKING** | Update | Container index definitions | Adding or removing properties to which the index applies |
| **BREAKING** | Update | Nullability of container properties | - |
| **BREAKING** | Update | Container property unit | Changing from `meter` to `kilometer` |
| **BREAKING** | Update | `maxTextSize` of text properties | - |
| **BREAKING** | Delete | Enum values from existing enum properties | - |



## Rebuild Mode

Unlike additive mode, rebuild mode allows every change to be applied to the data model, as it is assumed that the entire data model will be rebuilt from scratch. This mode is suitable where there is no existing data or applications depending on the current data model, such as in development or testing environments, since every component of the data model will be first deleted and then recreated. In case when containers that are to be deleted contain data, deployment in the rebuild mode will fail, and NEAT will not accidentally remove data. However, if you are intentionally looking to delete existing data, you will have to set `drop_data=True` when deploying the data model via command `neat.physical_data_model.write.cdf(dry_run = False, drop_data = True)`.