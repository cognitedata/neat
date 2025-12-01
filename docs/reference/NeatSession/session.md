::: cognite.neat._session._session.NeatSession

## Session Components

The `NeatSession` provides three main components to interact with:

### physical_data_model

The `PhysicalDataModel` component provides methods for reading, creating, and managing physical data models in CDF.

```python
neat.physical_data_model.read(...)
neat.physical_data_model.write(...)
```

See [Physical Data Model](./physical.md) for detailed documentation.

### issues

The `Issues` component provides access to issues found during reading and writing of data models:

```python
neat.issues
```

### result

The `Result` component provides access to the results of data model operations and transformations.

```python
neat.result
```