from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cognite.neat._client.client import NeatClient
from cognite.neat._data_model.importers._table_importer.importer import DMSTableImporter
from cognite.neat._data_model.validation.dms import DataModelLimitValidator
from cognite.neat._data_model.validation.dms._orchestrator import DmsDataModelValidation


def generate_implements_list(interface_count: int) -> str:
    return ",".join([f"my_space:Interface{i}(version=v1)" for i in range(1, interface_count + 1)])


def generate_properties_section(view_name: str, container_base: str, count: int) -> str:
    return "\n".join(
        [
            f"""- View: {view_name}
  View Property: prop{i}
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:{container_base}{1 + int((i + 1) / 35)}
  Container Property: prop{i}"""
            for i in range(count)
        ]
    )


def generate_container_references(view_name: str, container_count: int) -> str:
    return "\n".join(
        [
            f"""- View: {view_name}
  View Property: prop_container_{i}
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:Container{i}
  Container Property: prop1"""
            for i in range(1, container_count + 1)
        ]
    )


def generate_large_container_props(view_name: str, container_name: str, count: int) -> str:
    return "\n".join(
        [
            f"""- View: {view_name}
  View Property: container_prop{i}
  Value Type: text
  Min Count: 0
  Max Count: 1
  Connection: null
  Container: my_space:{container_name}
  Container Property: prop{i}"""
            for i in range(count)
        ]
    )


def generate_containers(container_names: list[str]) -> str:
    return "\n".join(
        [
            f"""- Container: my_space:{name}
  Used For: node"""
            for name in container_names
        ]
    )


def generate_enum_values(collection_name: str, count: int) -> str:
    return "\n".join(
        [
            f"""- Collection: {collection_name}
  Value: value{i}
  Name: Value {i}"""
            for i in range(1, count + 1)
        ]
    )


# Container names
container_names = [f"Container{i}" for i in range(1, 12)] + [
    "ContainerWithTooManyProperties",
    "DirectRelationContainer",
    "MinCountContainer",
    "Int32Container",
    "Int64Container",
    "TextListContainer",
    "EnumContainer",
]


@pytest.fixture(scope="session")
def dms_yaml_hitting_all_the_data_model_limits() -> tuple[str, set[str]]:
    yaml = f"""Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
Properties:
# View with 301 properties (exceeds 300 limit)
{generate_properties_section("ViewWithTooManyProperties", "Container", 301)}
# View referencing 11 containers (exceeds 10 limit)
{generate_container_references("ViewWithTooManyContainers", 11)}
# Container with 101 properties (exceeds 100 limit)
{generate_large_container_props("ViewWithLargeContainer", "ContainerWithTooManyProperties", 101)}
# Direct relation list exceeding 2000 limit
- View: ViewWithTooManyDirectRelations
  View Property: directRelations
  Connection: direct
  Value Type: my_space:TargetView(version=v1)
  Min Count: 0
  Max Count: 2001
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
# Text list exceeding 2000 default limit
- View: ViewWithTooManyTextInList
  View Property: textList
  Value Type: text
  Min Count: 0
  Max Count: 2001
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
  Implements: {generate_implements_list(11)}
{chr(10).join([f"- View: Interface{i}" for i in range(1, 12)])}
- View: TargetView
{chr(10).join([f"- View: DataModelView{i}" for i in range(101)])}
Containers:
{generate_containers(container_names)}
Enum:
{generate_enum_values("SomeEnums", 2)}

"""

    expected_problems = {
        "The data model references 123 views",
        "View my_space:ViewWithTooManyProperties(version=v1) has 301 properties",
        "View my_space:ViewWithTooManyContainers(version=v1) references 11 containers",
        "View my_space:ViewWithTooManyImplements(version=v1) implements 11 views",
        "Container my_space:ContainerWithTooManyProperties has 101 properties",
        "Container my_space:Int32Container has property int32List with list size 601",
        "Container my_space:Int64Container has property int64List with list size 301",
        "Container my_space:TextListContainer has property textList with list size 2001",
        "Container my_space:DirectRelationContainer has property directRelations with list size 2001",
        "View my_space:ViewWithTooHighMinCount(version=v1) does not have any properties defined",
        "View my_space:ViewWithTooManyImplements(version=v1) does not have any properties defined",
        "View my_space:TargetView(version=v1) does not have any properties defined",
        "Container my_space:MinCountContainer does not have any properties defined",
    }

    expected_problems.update(
        {f"View my_space:Interface{i}(version=v1) does not have any properties defined" for i in range(1, 12)}
    )
    expected_problems.update(
        {f"View my_space:DataModelView{i}(version=v1) does not have any properties defined" for i in range(101)}
    )

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

    found_issues = []
    # here we check that all expected problematic reversals are found
    found_problems = set()
    for problem in expected_problems:
        for issue in by_code[DataModelLimitValidator.code]:
            if problem in issue.message:
                found_problems.add(problem)
                found_issues.append(issue)
                break

    assert found_problems == expected_problems
