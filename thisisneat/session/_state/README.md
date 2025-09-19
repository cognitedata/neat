# NeatState

**IN DEVELOPMENT**
The neat state controls the `NeatInstanceStore` and `NeatGraphStore`. It is implementing a state machine pattern
to ensure valid state transitions. The diagram below shows the state machine:

```mermaid
stateDiagram-v2
    state excel_importer <<fork>>
        [*] --> EmptyState
        EmptyState --> Instances: extractor
        Instances --> Instances: graph transformer
        EmptyState --> Conceptual: importer
        EmptyState --> Physical: DMS importer/extractor
        Instances --> Conceptual: infer/importer
        Conceptual --> Physical: convert
        Conceptual --> Conceptual: conceptual transformer/infer
        Physical --> Physical: physical transformer/infer
        EmptyState --> excel_importer: Excel/YAML importer
        state excel_importer <<join>>
            excel_importer --> Conceptual
            excel_importer --> Physical
```
