# Reading Toolkit YAML

NEAT can read Cognite Toolkit module YAML directly via `neat.physical_data_model.read.yaml()` with `format="toolkit"`.

```python
neat.physical_data_model.read.yaml(
    "path/to/modules/my_module/data_modeling/my_model",
    format="toolkit",
)
```

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

## Governed spaces

Toolkit modules are often **multi-space**: the data model space plus domain spaces for containers and views.

When reading toolkit YAML, NEAT automatically adds every space found in the imported module (`spaces`, `views`, and `containers`) to governed spaces metadata. Validators then treat those local spaces as NEAT-governed — you do **not** need `enable_governed_spaces=True` in `NeatConfig` for this behavior.

Explicit `governedSpaces` from NEAT Excel metadata are left unchanged.

## Excel export for multi-space models

By default, `write.excel()` only exports view properties in the **data model space** (`skip_other_spaces=True`).

For multi-space toolkit modules, export all spaces with:

```python
neat.physical_data_model.write.excel("model.xlsx", skip_other_spaces=False)
```
