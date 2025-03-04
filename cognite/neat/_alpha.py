import warnings


class ExperimentalFeatureWarning(UserWarning):
    def __init__(self, feature_name: str):
        super().__init__(f"Experimental feature '{feature_name}' is subject to change without notice")

    def warn(self) -> None:
        warnings.warn(self, stacklevel=2)


class ExperimentalFlags:
    manual_rules_edit = ExperimentalFeatureWarning("enable_manual_edit")
    same_space_properties_only_export = ExperimentalFeatureWarning("same-space-properties-only")
    standardize_naming = ExperimentalFeatureWarning("standardize_naming")
    standardize_space_and_version = ExperimentalFeatureWarning("standardize_space_and_version")
    data_model_subsetting = ExperimentalFeatureWarning("data_model_subsetting")
    core_data_model_subsetting = ExperimentalFeatureWarning("core_data_model_subsetting")
    ontology_read = ExperimentalFeatureWarning("ontology_read")
    imf_read = ExperimentalFeatureWarning("imf_read")
    dexpi_read = ExperimentalFeatureWarning("dexpi_read")
    aml_read = ExperimentalFeatureWarning("aml_read")
    csv_read = ExperimentalFeatureWarning("csv_read")
    to_ontology = ExperimentalFeatureWarning("to_ontology")
