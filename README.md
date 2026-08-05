# Static related contents - Properdocs / MkDocs plugin

[![PyPi version badge](https://badgen.net/pypi/v/mkdocs-related-content)](https://pypi.org/project/mkdocs-related-content/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/mkdocs-related-content)](https://pypi.org/project/mkdocs-related-content/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mkdocs-related-content)](https://pypi.org/project/mkdocs-related-content/)

[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=Guts_mkdocs-related-content&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=Guts_mkdocs-related-content)
[![codecov](https://codecov.io/gh/Guts/mkdocs-related-content/branch/main/graph/badge.svg?token=A0XPLKiwiW)](https://codecov.io/gh/Guts/mkdocs-related-content)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![flake8](https://img.shields.io/badge/linter-flake8-green)](https://flake8.pycqa.org/)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Guts/mkdocs-related-content/master.svg)](https://results.pre-commit.ci/latest/github/Guts/mkdocs-related-content/master)
[![📚 Documentation](https://github.com/Guts/mkdocs-related-content/actions/workflows/documentation.yml/badge.svg)](https://github.com/Guts/mkdocs-related-content/actions/workflows/documentation.yml)

A plugin for [MkDocs](https://www.mkdocs.org), the static site generator, which creates [RSS 2.0](https://wikipedia.org/wiki/RSS) and [JSON Feed 1.1](https://www.jsonfeed.org/version/1.1/) feeds using the creation and modification dates from [git log](https://git-scm.com/docs/git-log) and page metadata ([YAML frontmatter](https://www.mkdocs.org/user-guide/writing-your-docs/#yaml-style-meta-data)).

## Installation

```sh
pip install mkdocs-related-content
```

## Development

Once you cloned the repository:

```sh
# install project as editable
python -m pip install -e .

# including development dependencies
python -m pip install -e .[dev]

# including documentation dependencies
python -m pip install -e .[docs]

# including testing dependencies
python -m pip install -e .[test]

# all inclusive
python -m pip install -e .[dev,docs,test]

# install git hooks
pre-commit install
```

Then follow the [contribution guidelines](CONTRIBUTING.md).

### Run the tests

```sh
# install development dependencies
python -m pip install -e .[test]

# run tests
pytest
```

### Build the documentation

```sh
# install dependencies for documentation
python -m pip install -e .[docs]

# build the documentation
mkdocs build
```

### Release workflow

1. Fill the `CHANGELOG.md`
1. Change the version number in `__about__.py`
1. Apply a git tag with the relevant version: `git tag -a 0.3.0 {git commit hash} -m "New awesome feature"`
1. Push tag to main branch: `git push origin 0.3.0`
