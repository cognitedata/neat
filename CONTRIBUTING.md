## Development Instructions

### Setup

Get the code!

```bash
git clone https://github.com/cognitedata/neat.git
cd cognite-neat
```

We use [poetry](https://pypi.org/project/poetry/) for dependency- and virtual environment management.

Install dependencies and initialize a shell within the virtual environment, with these commands:

```bash
poetry install
poetry shell
```

Install pre-commit hooks to run static code checks on every commit:

```bash
pre-commit install
```

You can also manually trigger the static checks with:

```bash
pre-commit run --all-files
```


### Testing

Initiate unit tests by running the following command from the root directory:

`pytest`

If you want to generate code coverage reports run:

```
pytest --cov-report html \
       --cov-report xml \
       --cov cognite
```

Open `htmlcov/index.html` in the browser to navigate through the report.

### Release version conventions

See https://semver.org/
