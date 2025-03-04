import warnings


class AlphaWarning(UserWarning):
    def __init__(self, feature_name: str):
        super().__init__(f"Alpha feature '{feature_name}' is subject to change without notice")

    def warn(self) -> None:
        warnings.warn(self, stacklevel=2)


class AlphaFlags:
    manual_rules_edit = AlphaWarning("enable_manual_edit")
    same_space_properties_only_export = AlphaWarning("same-space-properties-only")
    standardize_naming = AlphaWarning("standardize_naming")
    standardize_space_and_version = AlphaWarning("standardize_space_and_version")
    data_model_subsetting = AlphaWarning("data_model_subsetting")
    ontology_read = AlphaWarning("ontology_read")
    imf_read = AlphaWarning("imf_read")
    dexpi_read = AlphaWarning("dexpi_read")
    aml_read = AlphaWarning("aml_read")
    csv_read = AlphaWarning("csv_read")
    to_ontology = AlphaWarning("to_ontology")
