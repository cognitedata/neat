# Data Modeling in Excel

The main interface for working with `NEAT` is through a Python notebook environment. To get more granular control
over the data modeling process, you can use the Excel interface of a data model either to modify an existing data
model or to create a new one. The `NeatSession` objects provides methods for reading and writing data models to 
Excel files.

```python
from cognite.neat import NeatSession, get_cognite_client

client = get_cognite_client(".env")

neat = NeatSession(client)

# Reading an existing data model
neat.read.excel("path/to/excel/file.xlsx")


# Writing a data model to an Excel file
neat.to.excel("path/to/excel/file.xlsx")
```

Neat data models comes in two flavors, `logical` (`information`) and `physical` (`dms`). The `logical` data model
is the semantic data model, it is a description of how the different concepts relate to each other and what properties
they have. The `physical` data model specifies how the data model is implemented in Cognite Data Fusion (CDF),
specifically in the Domain Modeling Service (DMS). 

These two data models are intended for different user personas, the `logical` data model is intended for domain experts/
information architects, while the `physical` data model is intended for DMS/CDF architects.
