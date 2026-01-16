Validates that requires constraints between containers do not form cycles.

## What it does
This validator checks if the requires constraints between containers form a cycle.
For example, if container A requires B, B requires C, and C requires A, this forms
a cycle.

## Why is this bad?
Cycles in requires constraints will be rejected by the CDF API. The deployment
of the data model will fail if any such cycle exists.

## Example
Container `my_space:OrderContainer` requires `my_space:CustomerContainer`, which
requires `my_space:OrderContainer`. This creates a cycle and will be rejected.