"""This script converts a spreadsheet of an ill-formed model to a conceptual model.

The ill-formed model is organized as follows:

The classes names are in the header of column D-M.
The first row contains the word 'Property'.
The following rows contains the properties for each class.

In addition, there should be a shared based class defined in the same way in the B-column.

For example, the first rows of the spreadsheet looks like this:

```markdown
| common       | Pump         | HeatExchanger | StorageTank   | ... |
|--------------|--------------|---------------|---------------|-----|
| Property     | Property     | Property      | Property      | ... |
| externalId   | externalId   | externalId    | externalId    | ... |
| name         | name         | name          | name          | ... |
| description  | description  | description   | description   | ... |
| ...          | ...          | ...           | ...           | ... |
```
"""



