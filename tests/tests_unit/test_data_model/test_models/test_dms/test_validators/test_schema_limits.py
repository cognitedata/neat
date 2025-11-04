from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cognite.neat._client.client import NeatClient
from cognite.neat._data_model.importers._table_importer.importer import DMSTableImporter
from cognite.neat._data_model.validation.dms import DataModelLimitValidator
from cognite.neat._data_model.validation.dms._orchestrator import DmsDataModelValidation


@pytest.fixture(scope="session")
def dms_yaml_hitting_all_the_data_model_limits() -> tuple[str, set[str]]:
    implements = ",".join([f"my_space:Interface{i}(version=v1)" for i in range(1, 12)])

    yaml = (
        """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
Properties:
# View with 301 properties (exceeds 300 limit)
"""
        + "\n".join(
            [
                f"""- View: ViewWithTooManyProperties
  View Property: prop{i}
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:Container{1 + int((i + 1) / 35)}
  Container Property: prop{i}"""
                for i in range(301)
            ]
        )
        + """
# View referencing 11 containers (exceeds 10 limit)
- View: ViewWithTooManyContainers
  View Property: prop_container_1
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:Container1
  Container Property: prop1
- View: ViewWithTooManyContainers
  View Property: prop_container_2
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:Container2
  Container Property: prop1
- View: ViewWithTooManyContainers
  View Property: prop_container_3
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:Container3
  Container Property: prop1
- View: ViewWithTooManyContainers
  View Property: prop_container_4
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:Container4
  Container Property: prop1
- View: ViewWithTooManyContainers
  View Property: prop_container_5
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:Container5
  Container Property: prop1
- View: ViewWithTooManyContainers
  View Property: prop_container_6
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:Container6
  Container Property: prop1
- View: ViewWithTooManyContainers
  View Property: prop_container_7
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:Container7
  Container Property: prop1
- View: ViewWithTooManyContainers
  View Property: prop_container_8
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:Container8
  Container Property: prop1
- View: ViewWithTooManyContainers
  View Property: prop_container_9
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:Container9
  Container Property: prop1
- View: ViewWithTooManyContainers
  View Property: prop_container_10
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:Container10
  Container Property: prop1
- View: ViewWithTooManyContainers
  View Property: prop_container_11
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:Container11
  Container Property: prop1
# Container with 101 properties (exceeds 100 limit)
"""
        + "\n".join(
            [
                f"""- View: ViewWithLargeContainer
  View Property: container_prop{i}
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:ContainerWithTooManyProperties
  Container Property: prop{i}"""
                for i in range(101)
            ]
        )
        + f"""
# Direct relation list exceeding 100 limit (Max Count)
- View: ViewWithTooManyDirectRelations
  View Property: directRelations
  Connection: direct
  Value Type: my_space:TargetView(version=v1)
  Min Count: 0
  Max Count: 101
  Container: my_space:DirectRelationContainer
  Container Property: directRelations
# Int32 list with btree exceeding 600 limit
- View: ViewWithTooManyInt32WithBtree
  View Property: int32List
  Value Type: int32
  Min Count: 0
  Max Count: 601
  Connection: null
  Container: my_space:Int32Container
  Container Property: int32List
  Index: btree:int32List(cursorable=True)
# Int64 list with btree exceeding 300 limit
- View: ViewWithTooManyInt64WithBtree
  View Property: int64List
  Value Type: int64
  Min Count: 0
  Max Count: 301
  Connection: null
  Container: my_space:Int64Container
  Container Property: int64List
  Index: btree:int64List(cursorable=True)
# Text list exceeding 1000 default limit
- View: ViewWithTooManyTextInList
  View Property: textList
  Value Type: text
  Min Count: 0
  Max Count: 1001
  Connection: null
  Container: my_space:TextListContainer
  Container Property: textList
# Enum with 33 values (exceeds 32 limit)
- View: ViewWithTooManyEnumValues
  View Property: category
  Value Type: enum(collection=SomeEnums,unknownValue=other)
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:EnumContainer
  Container Property: category
Views:
- View: ViewWithTooManyProperties
- View: ViewWithTooManyContainers
- View: ViewWithLargeContainer
- View: ViewWithTooManyDirectRelations
- View: ViewWithTooHighMinCount
- View: ViewWithTooManyInt32WithBtree
- View: ViewWithTooManyInt64WithBtree
- View: ViewWithTooManyTextInList
- View: ViewWithTooManyEnumValues
# View implementing 11 views (exceeds 10 limit)
- View: ViewWithTooManyImplements
  Implements: {implements}
- View: Interface1
- View: Interface2
- View: Interface3
- View: Interface4
- View: Interface5
- View: Interface6
- View: Interface7
- View: Interface8
- View: Interface9
- View: Interface10
- View: Interface11
- View: TargetView
"""
        + "\n".join([f"- View: DataModelView{i}" for i in range(101)])
        + """
Containers:
- Container: my_space:Container1
  Used For: node
- Container: my_space:Container2
  Used For: node
- Container: my_space:Container3
  Used For: node
- Container: my_space:Container4
  Used For: node
- Container: my_space:Container5
  Used For: node
- Container: my_space:Container6
  Used For: node
- Container: my_space:Container7
  Used For: node
- Container: my_space:Container8
  Used For: node
- Container: my_space:Container9
  Used For: node
- Container: my_space:Container10
  Used For: node
- Container: my_space:Container11
  Used For: node
- Container: my_space:ContainerWithTooManyProperties
  Used For: node
- Container: my_space:DirectRelationContainer
  Used For: node
- Container: my_space:MinCountContainer
  Used For: node
- Container: my_space:Int32Container
  Used For: node
- Container: my_space:Int64Container
  Used For: node
- Container: my_space:TextListContainer
  Used For: node
- Container: my_space:EnumContainer
  Used For: node
Enum:
- Collection: SomeEnums
  Value: value1
  Name: Value 1
- Collection: SomeEnums
  Value: value2
  Name: Too Many
"""
    )

    expected_problems = {
        "The data model references 123 views",
        "View my_space:ViewWithTooManyProperties(version=v1) has 301 properties",
        "View my_space:ViewWithTooManyContainers(version=v1) references 11 containers",
        "View my_space:ViewWithTooManyImplements(version=v1) implements 11 views",
        "Container my_space:ContainerWithTooManyProperties has 101 properties",
        "Container my_space:DirectRelationContainer has property directRelations with list size 101",
        "Container my_space:Int32Container has property int32List with list size 601",
        "Container my_space:Int64Container has property int64List with list size 301",
        "Container my_space:TextListContainer has property textList with list size 1001",
    }

    return yaml, expected_problems


def test_validation(
    validation_test_cdf_client: NeatClient, dms_yaml_hitting_all_the_data_model_limits: tuple[str, list[str]]
) -> None:
    yaml_content, expected_problems = dms_yaml_hitting_all_the_data_model_limits

    read_yaml = MagicMock(spec=Path)
    read_yaml.read_text.return_value = yaml_content
    importer = DMSTableImporter.from_yaml(read_yaml)
    data_model = importer.to_data_model()

    # Run on success validators
    on_success = DmsDataModelValidation(validation_test_cdf_client)
    on_success.run(data_model)

    by_code = on_success.issues.by_code()

    # number of problematic reversals should match number of issues found
    assert len(by_code[DataModelLimitValidator.code]) == len(expected_problems)

    # here we check that all expected problematic reversals are found
    found_problems = set()
    for problem in expected_problems:
        for issue in by_code[DataModelLimitValidator.code]:
            if problem in issue.message:
                found_problems.add(problem)
                break

    assert found_problems == expected_problems
