Validates that views referenced in the data model actually exist.

## What it does
Validates that all views referenced in the data model actually exist either locally or in CDF.

## Why is this bad?
If a view referenced in the data model does not exist, the data model cannot be deployed to CDF.

## Example
If view WindTurbine is referenced in the data model, but does not exist in the data model or in CDF,
the data model cannot be deployed to CDF.