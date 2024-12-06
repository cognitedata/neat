# kNowlEdge grAph Transformer (NEAT)

[![release](https://img.shields.io/github/actions/workflow/status/cognitedata/neat/release.yaml?style=for-the-badge)](https://github.com/cognitedata/neat/actions/workflows/release.yaml)
[![Documentation Status](https://readthedocs.com/projects/cognite-neat/badge/?version=latest&style=for-the-badge)](https://cognite-neat.readthedocs-hosted.com/en/latest/?badge=latest)
[![Github](https://shields.io/badge/github-cognite/neat-green?logo=github&style=for-the-badge)](https://github.com/cognitedata/neat)
[![PyPI](https://img.shields.io/pypi/v/cognite-neat?style=for-the-badge)](https://pypi.org/project/cognite-neat/)
[![Downloads](https://img.shields.io/pypi/dm/cognite-neat?style=for-the-badge)](https://pypistats.org/packages/cognite-neat)
[![Docker Pulls](https://img.shields.io/docker/pulls/cognite/neat?style=for-the-badge)](https://hub.docker.com/r/cognite/neat)
[![GitHub](https://img.shields.io/github/license/cognitedata/neat?style=for-the-badge)](https://github.com/cognitedata/neat/blob/master/LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge)](https://github.com/ambv/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=for-the-badge)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/mypy-checked-000000.svg?style=for-the-badge&color=blue)](http://mypy-lang.org)

NEAT is a domain expert centric and developer friendly solution for rapid:

- semantic data modeling
- creation, transformation and enrichment of knowledge graphs
- and ingestion of the models and graphs into [Cognite Data Fusion](https://www.cognite.com/en/product/cognite_data_fusion_industrial_dataops_platform)

NEAT is using open and globally recognized standards maintained by the [World Wide Web Consortium (W3C)](https://www.w3.org/RDF/).
NEAT represents an essential tool for creation of standardized, machine-actionable, linked and semantic (meta)data.

> NEAT is an acronym derived from k**N**owl**Ed**ge gr**A**ph **T**ransformer hallucinated by GenAI.

## Installation

```bash
pip install cognite-neat
```

## Usage

The user interface for `NEAT` is a notebook-based environment. Once you have set up your notebook
environment, you start by creating a `CogniteClient` and instantiate a `NeatSession` object.

```python
from cognite.neat import NeatSession, get_cognite_client

client = get_cognite_client(".env")

neat = NeatSession(client)

neat.read.cdf.data_model(("my_space", "MyDataModel", "v1"))
```

## Documentation

For more information, see the [documentation](https://cognite-neat.readthedocs-hosted.com/en/latest/)
