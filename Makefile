SHELL := /bin/bash
ifndef VERBOSE
.SILENT:
endif

VERSION := $(shell python tomodachi/__version__.py)
RELEASED := $(shell git tag | grep ^${VERSION}$$)

default:
	@echo "Current version info collected: ${VERSION}."
	if [[ "${VERSION}" == *"dev"* ]]; then \
		echo "Development version (${VERSION}) can not be released."; \
	elif [[ "${RELEASED}" ]]; then \
		echo "Version ${VERSION} has been released."; \
	else \
		echo "No tag found for ${VERSION}. Version can be released."; \
	fi
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
	poetry run black tomodachi/ examples/ tests/

.PHONY: isort
isort:
	poetry run isort tomodachi/ examples/ tests/

.PHONY: flake8
flake8:
	poetry run flake8 tomodachi/ tests/

.PHONY: mypy
mypy:
	poetry run mypy tomodachi/ tests/type_hinting_validation.py

lint: flake8 mypy

.PHONY: tests
tests:
	poetry run pytest tests -v
	poetry run python -m tomodachi.run tests/run_example_service.py
	poetry run tomodachi run --loop uvloop tests/run_example_service.py

.PHONY: pytest
pytest:
	poetry run pytest tests -v

.PHONY: _check_release
_check_release:
	if [[ "${VERSION}" == *"dev"* ]]; then \
		echo "Development version (${VERSION}) can not be released."; exit 1; \
	fi
	if [[ "${RELEASED}" ]]; then \
		echo "Version ${VERSION} is already released"; exit 1; \
	fi

.PHONY: version
version:
	poetry version `python tomodachi/__version__.py`

.PHONY: _git_release
_git_release: _check_release
	git commit -m "`python tomodachi/__version__.py`" --allow-empty pyproject.toml poetry.lock tomodachi/__version__.py CHANGES.rst
	git tag -a `python tomodachi/__version__.py` -m `python tomodachi/__version__.py`
	git push
	git push --tags

.PHONY: _pypi_release
_pypi_release: _check_release
	twine upload dist/tomodachi-`python tomodachi/__version__.py`*

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
