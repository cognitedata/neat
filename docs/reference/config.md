# NeatConfig

`NeatConfig` allows you to configure your NEAT session with specific data modeling modes and validation rules. It provides pre-defined governance profiles that combine validation settings with data modeling behavior, or you can define custom profiles via a TOML configuration file.



::: cognite.neat.NeatConfig

```python
from cognite.neat import NeatConfig

config = NeatConfig.create_predefined(profile = "legacy-additive")
```

## Custom Configuration via TOML File

::: cognite.neat.get_neat_config_from_file

You can define custom profiles in a TOML configuration file. The configuration file can be placed in your project root (e.g., `pyproject.toml` or `neat.toml`).

### Basic TOML Structure

```toml
[tool.neat]
# Reference a profile (either built-in or custom)
profile = "my-custom-profile"

[tool.neat.modeling]
# Data modeling mode
# Options: "additive", "rebuild"
mode = "additive"

[tool.neat.validation]
# Validation rules to exclude (supports wildcards with *)
exclude = []
```

Custom Profile Example
Define your own profiles with specific validation rules:

```toml
[tool.neat]
profile = "my-smart-profile"

[tool.neat.profiles.my-smart-profile.modeling]
mode = "additive"

[tool.neat.profiles.my-smart-profile.validation]
exclude = ["NEAT-DMS-AI-READINESS-*", "NEAT-DMS-CONNECTIONS-REVERSE-008"]
```

#### Validation Exclusion Patterns

The `exclude` list supports wildcard patterns:

- "NEAT-DMS-AI-READINESS-*" - Excludes all AI-readiness validation rules
- "NEAT-DMS-CONNECTIONS-002" - Excludes a specific validation rule
- "*" - Excludes all validation rules (use with caution)

#### Loading Custom Configuration

```python
from cognite.neat import get_neat_config_from_file

# Load from pyproject.toml or neat.toml
config = get_neat_config_from_file("pyproject.toml", profile="my-smart-profile")
```

!!! warning "Built-in Profiles Cannot Be Redefined"
    The pre-defined profiles:

    - `legacy-additive`
    - `legacy-rebuild`
    - `deep-additive`
    - `deep-rebuild`

    are hardcoded and cannot be overridden in TOML files. Use custom profile names for your configurations.