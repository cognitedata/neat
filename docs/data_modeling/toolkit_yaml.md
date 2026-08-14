# Reading Toolkit YAML

NEAT can read Cognite Toolkit module YAML directly via `neat.physical_data_model.read.yaml()` with `format="toolkit"`.

```python
neat.physical_data_model.read.yaml(
    "path/to/modules/my_module/data_modeling/my_model",
    format="toolkit",
)
```

Pass the **module** (or `data_modeling`) directory, not a parent folder of the Toolkit project. `cdf.toml` `default_config_yaml` (often `config.sandbox.yaml`) is used as the environment overlay unless you pass `toolkit_env`. Optional `toolkit_env="sandbox"` selects `config.sandbox.yaml` explicitly.

Non-schema YAML (`config.*.yaml`, `build_info.*.yaml`, …) is ignored during directory reads.

## Template variables

Toolkit modules use `{{ variable }}` placeholders in YAML files. When `format="toolkit"`, NEAT resolves these from Toolkit config before import:

- `default.config.yaml` at the toolkit project root
- Environment overlays such as `config.dev.yaml` (selected via `toolkit_env`, or from `cdf.toml` when present)
- Module-level overrides under `variables.modules`

Optional parameters on `read.yaml()`:

| Parameter | Purpose |
|-----------|---------|
| `toolkit_env` | Select a config overlay (e.g. `"dev"`, `"prod"`) |
| `toolkit_config` | Merge an explicit config YAML on top of defaults |
| `toolkit_version` | Override `version` and `viewVersion` template variables |
