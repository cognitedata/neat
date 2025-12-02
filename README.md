# kNowlEdge grAph Transformer (NEAT)

[![release](https://img.shields.io/github/actions/workflow/status/cognitedata/neat/release.yaml?style=for-the-badge)](https://github.com/cognitedata/neat/actions/workflows/release.yaml)
[![Documentation Status](https://readthedocs.com/projects/cognite-neat/badge/?version=latest&style=for-the-badge)](https://cognite-neat.readthedocs-hosted.com/en/latest/?badge=latest)
[![Github](https://shields.io/badge/github-cognite/neat-green?logo=github&style=for-the-badge)](https://github.com/cognitedata/neat)
[![PyPI](https://img.shields.io/pypi/v/cognite-neat?style=for-the-badge)](https://pypi.org/project/cognite-neat/)
[![Downloads](https://img.shields.io/pypi/dm/cognite-neat?style=for-the-badge)](https://pypistats.org/packages/cognite-neat)
[![GitHub](https://img.shields.io/github/license/cognitedata/neat?style=for-the-badge)](https://github.com/cognitedata/neat/blob/master/LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge)](https://github.com/ambv/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=for-the-badge)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/mypy-checked-000000.svg?style=for-the-badge&color=blue)](http://mypy-lang.org)



There was no easy way to make knowledge graphs, especially data models, and onboard them to
[Cognite Data Fusion](https://www.cognite.com/en/product/cognite_data_fusion_industrial_dataops_platform), so we have built NEAT!


NEAT is great for data model development, validation and deployment. It comes with an evergrowing library of validators,
which will assure that your data model adheres to the best practices and that is performant. Unlike other solutions,
which require you to be a technical wizard or modeling expert, NEAT provides you a guiding data modeling experience.

We offer various interfaces on how you can develop your data model, where majority of our users prefer
a combination of Jupyter Notebooks, leveraging NEAT features through so called [NeatSession](https://cognite-neat.readthedocs-hosted.com/en/latest/reference/NeatSession/session.html),  with [a Spreadsheet data model template](https://cognite-neat.readthedocs-hosted.com/en/latest/excel_data_modeling/data_model.html).


Only Data modeling? There was more before!?
True, NEAT v0.x (legacy) offered a complete knowledge graph
tooling. Do not worry though, all the legacy features are still available and will be gradually
ported to NEAT v1.x according to the [roadmap](https://cognite-neat.readthedocs-hosted.com/en/latest/roadmap.html).


## Usage
The user interface for `NEAT` features is through `NeatSession`, which is typically instantiated in a notebook-based environment due to simplified interactivity with `NEAT`
and navigation of the session content. Once you have set up your notebook environment, and installed neat via:

```bash
pip install cognite-neat
```

you start by creating a `CogniteClient` and instantiate a `NeatSession` object:

```python
from cognite.neat import NeatSession, get_cognite_client

client = get_cognite_client(".env")

neat = NeatSession(client)

neat.physical_data_model.read.cdf("cdf_cdm", "CogniteCore", "v1")
```

## Documentation


For more information, see the [documentation](https://cognite-neat.readthedocs-hosted.com/en/latest/)
