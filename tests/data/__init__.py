from collections.abc import Iterable
from pathlib import Path

from ._graph import car as _car
from ._instances import classic_windfarm as _classic_windfarm
from ._schema.non_neat import windturbine as _windturbine

_data_dir = Path(__file__).resolve(strict=True).parent
_graph_dir = _data_dir / "_graph"
_schema_dir = _data_dir / "_schema"
_instances_dir = _data_dir / "_instances"


class GraphData:
    aml_raw_graph_ttl = _graph_dir / "aml_raw_graph.ttl"
    aml_example_aml = _graph_dir / "aml_example.aml"
    dexpi_example_xml = _graph_dir / "dexpi_example.xml"
    dexpi_raw_graph_ttl = _graph_dir / "dexpi_raw_graph.ttl"
    low_quality_graph_ttl = _graph_dir / "low-quality-graph.ttl"
    car = _car
    car_py = _graph_dir / "car.py"
    iodd_Piab_piCOMPACT10X_20230509_IODD1_1_xml = _graph_dir / "iodd_Piab-piCOMPACT10X-20230509-IODD1.1.xml"


class InstanceData:
    classic_windfarm = _classic_windfarm

    class AssetCentricCDF:
        _asset_centric_cdf = _instances_dir / "asset_centric_cdf"
        assets_yaml = _asset_centric_cdf / "assets.yaml"
        events_yaml = _asset_centric_cdf / "events.yaml"
        files_yaml = _asset_centric_cdf / "files.yaml"
        labels_yaml = _asset_centric_cdf / "labels.yaml"
        relationships_yaml = _asset_centric_cdf / "relationships.yaml"
        sequence_rows_yaml = _asset_centric_cdf / "sequence_rows.yaml"
        sequences_yaml = _asset_centric_cdf / "sequences.yaml"
        timeseries_yaml = _asset_centric_cdf / "timeseries.yaml"


_non_neat = _schema_dir / "non_neat"
_dtdl = _non_neat / "dtdl"


class SchemaData:
    class Conceptual:
        _conceptual = _schema_dir / "conceptual"
        only_concepts_xlsx = _conceptual / "only_concepts.xlsx"
        info_arch_car_rules_xlsx = _conceptual / "info-arch-car-rules.xlsx"
        information_unknown_value_type_xlsx = _conceptual / "information-unknown-value-type.xlsx"
        info_with_cdm_ref_xlsx = _conceptual / "info_with_cdm_ref.xlsx"
        broken_concepts_xlsx = _conceptual / "broken_concepts.xlsx"

    class NonNeatFormats:
        class DTDL:
            energy_grid = _dtdl / "energy-grid"
            temperature_controller = _dtdl / "TemperatureController.zip"

        referencing_core_yamls = _non_neat / "referencing_core"
        cognite_core_v1_zip = _non_neat / "cognite_core_v1.zip"
        windturbine = _windturbine

    partial_model_dir = _schema_dir / "partial_model"

    class Physical:
        _physical = _schema_dir / "physical"
        car_dms_rules_xlsx = _physical / "car_dms_rules.xlsx"
        car_dms_rules_deprecated_xlsx = _physical / "car_dms_rules_deprecated.xlsx"
        dm_raw_filter_xlsx = _physical / "dm_raw_filter.xlsx"
        dm_view_space_different_xlsx = _physical / "dm_view_space_different.xlsx"
        dms_unknown_value_type_xlsx = _physical / "dms-unknown-value-type.xlsx"
        isa_plus_cdm_xlsx = _physical / "isa_plus_cdm.xlsx"
        missing_in_model_value_xlsx = _physical / "missing-in-model-value.xlsx"
        physical_singleton_issue_xlsx = _physical / "physical_singleton_issue.xlsx"
        mixed_up_version_xlsx = _physical / "mixed-up-version.xlsx"
        pump_example_duplicated_resources_xlsx = _physical / "pump_example_duplicated_resources.xlsx"
        pump_example_with_missing_cells_xlsx = _physical / "pump_example_with_missing_cells.xlsx"
        pump_example_with_missing_cells_raise_issues = _physical / "pump_example_with_missing_cells_raise_issues.xlsx"
        strongly_connected_model_folder = _physical / "strongly_connected_model"

    class Conversion:
        conversion = _schema_dir / "conversion"

        @classmethod
        def iterate(cls) -> Iterable[tuple[Path, Path]]:
            conceptual: Path
            for conceptual in cls.conversion.glob("*.yaml"):
                if conceptual.is_dir():
                    continue
                if not conceptual.stem.endswith(".conceptual"):
                    continue
                stem = conceptual.stem.removesuffix(".conceptual")
                physical = conceptual.with_stem(f"{stem}.physical")
                if not physical.exists():
                    raise ValueError(
                        f"Missing physical file for {conceptual}. This is required to test the conversion."
                    )
                yield conceptual, physical

    class PhysicalInvalid:
        _physical_invalid = _schema_dir / "physical_invalid"
        inconsistent_container_dms_rules_xlsx = _physical_invalid / "inconsistent_container_dms_rules.xlsx"
        invalid_metadata_xlsx = _physical_invalid / "invalid_metadata.xlsx"
        invalid_property_dms_rules_xlsx = _physical_invalid / "invalid_property_dms_rules.xlsx"
        missing_view_container_dms_rules_xlsx = _physical_invalid / "missing_view_container_dms_rules.xlsx"
        too_many_container_per_view_xlsx = _physical_invalid / "too_many_containers_per_view.xlsx"

    class PhysicalYamls:
        _physical_yaml = _schema_dir / "physical_yamls"

        @classmethod
        def iterate(cls) -> Iterable[tuple[Path, Path | None]]:
            path: Path
            for path in cls._physical_yaml.glob("*.yaml"):
                if path.is_dir():
                    continue
                if path.stem.endswith(".expected_issues"):
                    continue
                issues = path.with_stem(f"{path.stem}.expected_issues")
                yield path, issues if issues.exists() else None
