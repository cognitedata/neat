import pytest


@pytest.fixture(scope="session")
def valid_dms_yaml_format() -> str:
    return """Metadata:
- Key: space
  Value: cdf_cdm
- Key: externalId
  Value: CogniteDataModel
- Key: version
  Value: v1
Properties:
- View: CogniteDescribable
  View Property: name
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: CogniteDescribable
  Container Property: name
  Index: btree:name(cursorable=True)
  Connection: null
Views:
- View: CogniteDescribable
Containers:
- Container: CogniteDescribable
  Used For: node
"""


@pytest.fixture(scope="session")
def invalid_dms_yaml_format() -> str:
    return """Metadata:
- Key: space
  Value: cdf_cdm
- Key: externalId
  Value: CogniteDataModel
- Key: version
  Value: v1
Properties:
- View: CogniteDescribable
  View Property: name
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: CogniteDescribable
  Container Property: name
  Index: notValidIndex:name(cursorable=True)
  Connection: null
Views:
- View: CogniteDescribable
Containers:
- Container: CogniteDescribable
  Used For: node
"""
