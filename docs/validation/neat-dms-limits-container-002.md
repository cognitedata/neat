Validates that container property list sizes do not exceed CDF limits.

## What it does
Checks that list-type properties (max_list_size) do not exceed the appropriate limit based on:
- Data type (Int32, Int64, DirectRelation, etc.)
- Presence of btree index
- Default vs maximum limits

## Why is this bad?
CDF enforces different list size limits for different data types and indexing configurations
to ensure optimal performance and prevent resource exhaustion.

## Example
If a DirectRelation property has max_list_size=2000 with a btree index, but the limit
is 1000 for indexed DirectRelations, this validator will raise a ConsistencyError issue.

## Note
Enum properties are skipped as they have a separate 32-value limit checked during read time of data model to neat
as a SyntaxError check.