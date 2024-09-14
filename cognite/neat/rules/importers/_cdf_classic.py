from cognite.neat.constants import CLASSIC_CDF_NAMESPACE
from cognite.neat.issues import IssueList
from cognite.neat.issues.errors import NeatValueError
from cognite.neat.rules._shared import ReadRules
from cognite.neat.rules.models import InformationInputRules
from cognite.neat.rules.models.information import (
    InformationInputClass,
    InformationInputMetadata,
    InformationInputProperty,
)
from cognite.neat.store import NeatGraphStore
from cognite.neat.utils.rdf_ import remove_namespace_from_uri

from ._base import BaseImporter


class CDFClassicGraphImporter(BaseImporter[InformationInputRules]):
    def __init__(self, store: NeatGraphStore) -> None:
        self._store = store

    def to_rules(self) -> ReadRules[InformationInputRules]:
        issues = IssueList()
        if not self._store.queries.has_namespace(CLASSIC_CDF_NAMESPACE):
            issues.append(NeatValueError("The store does not contain the classic CDF namespace"))
            return ReadRules(None, issues, read_context={})

        rules = InformationInputRules(
            metadata=InformationInputMetadata.load(self._default_metadata()),
            properties=[],
            classes=[],
        )
        self._add_source_system(rules)
        self._add_dataset(rules)
        self._add_asset(rules)
        self._add_event(rules)
        self._add_sequence(rules)
        self._add_file(rules)

        return ReadRules(rules, issues, read_context={})

    def _add_source_system(self, rules: InformationInputRules) -> None:
        types_ = self._store.queries.types_with_property(CLASSIC_CDF_NAMESPACE.source)
        if not types_:
            return
        rules.classes.append(
            InformationInputClass(
                class_="SourceSystem",
                parent="cdf_cdm:SourceSystem",
            ),
        )
        # TODO: Is this the correct syntax for the transformation?
        transformation = [
            f"classic_cdf:{remove_namespace_from_uri(type_)}(source) -> classic_cdf:SourceSystem(name)"
            for type_ in types_
        ]
        rules.properties.append(
            InformationInputProperty(
                class_="SourceSystem",
                property_="source",
                value_type="string",
                transformation=",".join(transformation),
            ),
        )

    def _add_dataset(self, rules: InformationInputRules) -> None:
        from cognite.neat.graph.extractors import DataSetExtractor

        if not self._store.queries.has_type(CLASSIC_CDF_NAMESPACE[DataSetExtractor._default_rdf_type]):
            return

        rules.classes.append(
            InformationInputClass(
                class_="DataSet",
                parent=None,
            ),
        )
        rules.properties.extend(
            [
                InformationInputProperty("DataSet", "name", "string"),
                InformationInputProperty("DataSet", "description", "string"),
                InformationInputProperty("DataSet", "external_id", "string"),
                InformationInputProperty("DataSet", "write_protected", "boolean"),
                InformationInputProperty("DataSet", "metadata", "json"),
            ]
        )

    def _add_asset(self, rules: InformationInputRules) -> None:
        from cognite.neat.graph.extractors import AssetsExtractor

        if not self._store.queries.has_type(CLASSIC_CDF_NAMESPACE[AssetsExtractor._default_rdf_type]):
            return

        rules.classes.append(
            InformationInputClass(
                class_="Asset",
                parent="cdf_cdm:CogniteAsset",
            ),
        )

        rules.properties.extend(
            [
                InformationInputProperty("Asset", "name", "string"),
            ]
        )

    def _add_event(self, rules: InformationInputRules) -> None:
        pass

    def _add_sequence(self, rules: InformationInputRules) -> None:
        pass

    def _add_file(self, rules: InformationInputRules) -> None:
        pass
