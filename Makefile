SHELL := /bin/bash
ifndef VERBOSE
.SILENT:
endif

VERSION := $(shell python tomodachi/__version__.py)
RELEASED := $(shell git tag | grep ^${VERSION}$$)

default:
	@echo "Current version info collected: ${VERSION}."
	if [[ "${RELEASED}" ]]; then echo "Version is already released."; else echo "Version can be released."; fi
	@echo ""
	@echo "Usage:"
	@echo "  make install        | install package"
	@echo "  make test           | run test suite"
	@echo "  make lint           | run linters"
	@echo "  make black          | formats code using black"
	@echo "  make isort          | sorts import"
	@echo "  make release        | tag and push a new version"

.PHONY: build
build:
	rm -rf build dist
	poetry build

.PHONY: install
install:
	poetry install --no-interaction -E uvloop -E protobuf -E aiodns

.PHONY: clean
clean:
	rm -rf build dist
	@echo "done"

.PHONY: black
black:
	poetry run black tomodachi.py tomodachi/ examples/ tests/

.PHONY: isort
isort:
	poetry run isort tomodachi.py tomodachi/ examples/ tests/

.PHONY: lint
lint:
	poetry run flake8 tomodachi/ tests/
	poetry run mypy ./

.PHONY: mypy
mypy:
	poetry run mypy ./


.PHONY: tests
tests:
	poetry run pytest tests -v
	poetry run python tomodachi.py run tests/run_example_service.py
	poetry run python tomodachi.py run --loop uvloop tests/run_example_service.py

.PHONY: pytest
pytest:
	poetry run pytest tests -v

.PHONY: _check_release
_check_release:
	if [[ "${RELEASED}" ]]; then echo "Version ${VERSION} is already released"; exit 1; fi

.PHONY: version
version:
	poetry version `python tomodachi/__version__.py`

.PHONY: _git_release
_git_release:
	git commit -m "`python tomodachi/__version__.py`" --allow-empty pyproject.toml poetry.lock tomodachi/__version__.py CHANGES.rst
	git tag -a `python tomodachi/__version__.py` -m `python tomodachi/__version__.py`
	git push
	git push --tags

.PHONY: _pypi_release
_pypi_release:
	poetry run twine upload dist/tomodachi-`python tomodachi/__version__.py`*

test: tests
testing: tests
remove: uninstall
linting: lint
linter: lint
develop: install
dev: install
release: _check_release version build lint test _pypi_release _git_release
help: default
current-version: help
usage: help
