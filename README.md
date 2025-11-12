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

- data modeling
- extraction, transformation and loading of instances
- and ingestion of the models and instances (i.e. knowledge graphs) into [Cognite Data Fusion](https://www.cognite.com/en/product/cognite_data_fusion_industrial_dataops_platform)

NEAT is using open and globally recognized standards maintained by the [World Wide Web Consortium (W3C)](https://www.w3.org/RDF/).
NEAT represents an essential tool for creation of standardized, machine-actionable, linked and semantic (meta)data.

> NEAT is a funny acronym derived from k**N**owl**Ed**ge gr**A**ph **T**ransformer produced using [ACRONIMIFY](https://acronymify.com/NEAT/?q=knowledge+graph+transformer).


## History

NEAT emerged from years of experience in semantic tooling and knowledge graph development. The foundation was laid in 2020 with [sheet2rdf](https://github.com/nikokaoja/sheet2rdf), an Excel-based tool that trained data stewards to build domain-specific knowledge graphs and supported CI/CD processes in the Dutch Covid program and european wind energy community.

By mid of 2022, sheet2rdf was used in several POCs in Cognite. As Cognite's Data Modeling Service (DMS) development progressed, the need for simplified data modeling experience led to demonstration of proto-NEAT, known as [sheet2fdm](https://github.com/cognitedata/sheet2fdm), an extension of sheet2rdf, enabling semantic data model definitions in OWL, SHACL, Python and GraphQL (see e.g., [wind energy data model](https://cognitedata.github.io/wind-energy-data-model/)) using a simplified version of sheet2rdf Excel template.

Presented in various forums in 2022, this approach paved the way for NEAT’s formal development in November 2022 to enable cost-saving and empowerment of Cognite customers to self-sufficiently maintain and onboard knowledge graphs to Cognite Data Fusion.

## Authorship

### Authors
The plot below shows the NEAT authorship from the start until present day.

![NEAT authorship](./artifacts/figs/authorship.png)

#### Current authors
- [Nikola Vasiljević](www.linkedin.com/in/thisisnikola)
- [Anders Albert](https://www.linkedin.com/in/anders-albert-00790483/)

#### Former authors
- [Aleksandrs Livincovs](https://www.linkedin.com/in/aleksandrslivincovs/)
- [Julia Graham](https://www.linkedin.com/in/julia-graham-959a78a7/)
- [Rogerio Júnior](https://www.linkedin.com/in/rogerio-saboia-j%C3%BAnior-087118a7/)

### Contributors
We are very grateful for the contributions made by:

- [Kristina Tomičić](https://www.linkedin.com/in/kristina-tomicic-6bb443108/), who implemented Data Model and Instances visualization
- [Marie Solvik Lepoutre](https://www.linkedin.com/in/mslepoutre/), who improved RDF triples projections to Cognite Data Fusion
- [Bård Henning Tvedt](https://www.linkedin.com/in/bhtvedt/), who implemented IMF importer
- [Hassan Gomaa](https://www.linkedin.com/in/dr-hassan-gomaa-232638121/), who extended the DEXPI extractor


## Sponsors
NEAT is developed and maintained by Cognite. We are grateful for the past support of our sponsors, who funded us to develop NEAT and to make it open source.

- [Statnett](https://www.statnett.no/) - the MIMIR team ([Ola Hagen Øyan](https://www.linkedin.com/in/ola-%C3%B8yan-b0205b19/), [Olav Westeng Alstad](https://www.linkedin.com/in/olav-w-alstad-52329191/),[Andreas Kimsås](https://www.linkedin.com/in/andreas-kims%C3%A5s-964a0b2/) and [Anders Willersrud](https://www.linkedin.com/in/anders-willersrud-13a20220/)) – who supported the development of NEAT from end of 2022 to mid of 2023 and its integration with Statnett's infrastructure, where NEAT was battle-tested as a tool for non-sematic experts to define data models and transform large knowledge graphs representing the entire Norwegian power grid system. Without Statnett's support NEAT would not exist in the first place, and would not be open-source.
- [Aker Solutions](https://www.akersolutions.com/) – the IMod Team (currently lead by [Maria Kenderkova](https://www.linkedin.com/in/maria-kenderkova/)), who funded development of NEAT from mid of 2023 till end of 2024 (multi-level and role-based data modeling, support for ontologies, IMF, DEXPI, AML,...) , as well who were early adopters and embraced NEAT and who were patient with us when things did not work so well. Aker Solutions was instrumental to elevating NEAT to a product level, and who selflessly advocate for NEAT globally.


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
