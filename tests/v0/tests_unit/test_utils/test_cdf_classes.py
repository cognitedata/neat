from cognite.client.data_classes.data_modeling import NodeApply, NodeId

from cognite.neat.v0.core._client.data_classes.data_modeling import NodeApplyDict


class TestCogniteResourceDict:
    TWO_NODES_RAW = """- space: space1
  externalId: externalId1
  instanceType: node
- space: space1
  externalId: externalId2
  instanceType: node
"""
    TWO_NODES = NodeApplyDict.load(TWO_NODES_RAW)

    def test_node_load_dump(self) -> None:
        nodes = NodeApplyDict.load(self.TWO_NODES_RAW)
        assert isinstance(nodes, NodeApplyDict)

        dumped = nodes.dump()
        assert dumped == self.TWO_NODES.dump()

    def test_node_as_pandas(self) -> None:
        df = self.TWO_NODES.to_pandas()
        expected_columns = {"space", "external_id", "instance_type"}

        missing = set(df.columns) - expected_columns
        assert not missing, f"Missing columns: {missing}"
        extra = expected_columns - set(df.columns)
        assert not extra, f"Extra columns: {extra}"

    def test_node_dump_yaml(self) -> None:
        dumped = self.TWO_NODES.dump_yaml()

        assert dumped == self.TWO_NODES_RAW

    def test_iterate_nodes(self) -> None:
        node_id = next(iter(self.TWO_NODES))
        assert isinstance(node_id, NodeId)

    def test_iterate_items(self) -> None:
        node_id, node = next(iter(self.TWO_NODES.items()))

        assert isinstance(node_id, NodeId)
        assert isinstance(node, NodeApply)

    def test_instantiate_empty(self) -> None:
        empty = NodeApplyDict()
        assert bool(empty) is False

    def test_instantiate_from_list(self) -> None:
        nodes = NodeApplyDict(list(self.TWO_NODES.values()))
        assert len(nodes) == 2

    def test_is_dict(self) -> None:
        assert isinstance(self.TWO_NODES, dict)
