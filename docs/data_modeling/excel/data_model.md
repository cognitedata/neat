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
neat.physical_data_model.read.excel("path/to/excel/file.xlsx")


# Writing a data model to an Excel file
neat.physical_data_model.write.excel("path/to/excel/file.xlsx")
```
