# NeatSession
::: cognite.neat.NeatSession.__init__
    options:
      heading_level: 3
      show_root_heading: true
      show_source: false
      show_if_no_docstring: true

**Session Initialization**

```python
neat = NeatSession(client = ... , config = ...)
```

### issues
```python
neat.issues
```
Presents issues and insights found during the session operations.

### result
```python
neat.result
```
Holds the result of the last executed operation in the session.


## Physical Data Model
```python
neat.physical_data_model
```


### Reading Physical Data Models


::: cognite.neat._session._physical.ReadPhysicalDataModel
    options:
      show_root_toc_entry: false
      show_root_heading: false
      heading_level: 4
      show_source: false
      show_signature_annotations: true
      signature_crossrefs: true
      separate_signature: true
      filters:
        - "!^_"


### Writing Physical Data Models

::: cognite.neat._session._physical.WritePhysicalDataModel
    options:
      show_root_toc_entry: false
      show_root_heading: false
      heading_level: 4
      show_source: false
      show_signature_annotations: true
      signature_crossrefs: true
      separate_signature: true
      filters:
        - "!^_"