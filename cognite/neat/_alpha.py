import warnings


class AlphaWarning(UserWarning):
    def __init__(self, feature_name: str):
        super().__init__(f"Alpha feature '{feature_name}' is subject to change without notice")

    def warn(self) -> None:
        warnings.warn(self, stacklevel=2)


class AlphaFlags:
    manual_rules_edit = AlphaWarning("enable_manual_edit")
    same_space_properties_only_export = AlphaWarning("same-space-properties-only")
