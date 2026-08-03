Validates that reverse connections do not point through other reverse direct relations.

## What it does
Checks that the property referenced in a reverse connection's 'through' clause
is a direct relation property, not another reverse direct relation property.

## Why is this bad?
Reverse direct relation properties do not map to a container; they rely on the
direct relation property they reverse. Pointing two reverse properties at each other
creates a cycle that never resolves to container storage, even when the containers
have correct direct relation properties defined.

## Example
If ViewA has reverse property `items` through ViewB's reverse property `owners`,
and ViewB has reverse property `owners` through ViewA's reverse property `items`,
neither reverse connection maps down to a container direct relation.