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
    low_quality_graph_ttl = _graph_dir / "low_quality_graph.ttl"
    imf_temp_transmitter_complete_ttl = _graph_dir / "IMF_TempTransmitterComplete.ttl"
    car = _car
    car_py = _graph_dir / "car.py"
    iodd_Piab_piCOMPACT10X_20230509_IODD1_1_xml = "iodd_Piab-piCOMPACT10X-20230509-IODD1.1.xml"


class InstanceData:
    power_grip_example_json = _data_dir
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
        asset_architect_test_xlsx = _conceptual / "asset_architect_test.xlsx"
        info_arch_car_rules_xlsx = _conceptual / "info-arch-car-rules.xlsx"
        information_unknown_value_types_xlsx = _conceptual / "information_unknown_value_types.xlsx"
        nordic44_inferred_xlsx = _conceptual / "nordic44_inferred.xlsx"
        sheet2cdf_transformation_rules_xlsx = _conceptual / "sheet2cdf_transformation_rules.xlsx"
        sheet2cdf_transformation_rule_date_xlsx = _conceptual / "sheet2cdf_transformation_rule_date.xlsx"

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
        missing_in_model_value_xlsx = _physical / "missing_in_model_value.xlsx"
        mixed_up_version_xlsx = _physical / "mixed-up-version.xlsx"
        pump_example_xlsx = _physical / "pump_example.xlsx"
        pump_example_duplicated_resources_xlsx = _physical / "pump_example_duplicated_resources.xlsx"
        pump_example_with_missing_cells_xlsx = _physical / "pump_example_with_missing_cells.xlsx"
        pump_example_with_missing_cells_raise_issues = _physical / "pump_example_with_missing_cells_raise_issues.xlsx"

    class PhysicalInvalid:
        _physical_invalid = _schema_dir / "physical_invalid"
        inconsistent_container_dms_rules_xlsx = _physical_invalid / "inconsistent_container_dms_rules.xlsx"
        invalid_metadata_xlsx = _physical_invalid / "invalid_metadata.xlsx"
        invalid_property_dms_rules_xlsx = _physical_invalid / "invalid_property_dms_rules.xlsx"
        missing_view_container_dms_rules_xlsx = _physical_invalid / "missing_view_container_dms_rules.xlsx"
        too_many_container_per_view_xlsx = _physical_invalid / "too_many_container_per_view.xlsx"
