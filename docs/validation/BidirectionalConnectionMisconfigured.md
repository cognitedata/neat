This validator checks bidirectional connections to ensure reverse and direct connection pairs
are properly configured.

A bidirectional connection consists of:
- A direct connection property in a source view that points to the target view
  SourceView -- [directConnection] --> TargetView
- A reverse connection property in a target view, pointing to a source view through a direct connection property
  TargetView -- [reverseConnection, through(SourceView, SourceView.directConnection)] --> SourceView

Validation checks:
    1. Source view and property exist
    2. Property is a direct connection type
    3. Container mapping is correct
    4. Direct connection points back to correct target
