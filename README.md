# Static related contents - Properdocs / MkDocs plugin

[![PyPi version badge](https://badgen.net/pypi/v/mkdocs-related-content)](https://pypi.org/project/mkdocs-related-content/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/mkdocs-related-content)](https://pypi.org/project/mkdocs-related-content/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mkdocs-related-content)](https://pypi.org/project/mkdocs-related-content/)

[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=Guts_mkdocs-related-content&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=Guts_mkdocs-related-content)
[![codecov](https://codecov.io/gh/Guts/mkdocs-related-content/branch/main/graph/badge.svg?token=A0XPLKiwiW)](https://codecov.io/gh/Guts/mkdocs-related-content)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Guts/mkdocs-related-content/master.svg)](https://results.pre-commit.ci/latest/github/Guts/mkdocs-related-content/master)
[![📚 Documentation](https://github.com/Guts/mkdocs-related-content/actions/workflows/documentation.yml/badge.svg)](https://github.com/Guts/mkdocs-related-content/actions/workflows/documentation.yml)

A plugin for [Properdocs](https://properdocs.org) / [MkDocs](https://www.mkdocs.org), the static site generator, which computes, for every tagged page, a list of related pages based on shared tags, and exposes it to the Jinja context so your theme can render a "Related content" / "See also" section.

## Installation

```sh
pip install mkdocs-related-content
```

## Usage

Then in your `mkdocs.yml`:

```yaml
plugins:
  - related-content
```

### Example

Two pages sharing a tag:

```yaml
# docs/api-auth.md
---
tags:
    - API
    - authentication
    - Python
---
```

```yaml
# docs/api-oauth.md
---
tags:
    - API
    - oAuth
---
```

Both pages `api-auth.md` and `api-oauth.md` share the `api` tag: each will list the other as related content ([Jaccard similarity score](https://fr.wikipedia.org/wiki/Indice_et_distance_de_Jaccard) of `0.25`), regardless of the order pages are declared in `nav`.

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
