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
	cp README.rst README.rst.tmp
	cat README.rst.tmp | tr '\n' '\r' | sed -e $$'s/.. raw:: html\r*\(    [^\r]*\r\)*\r//g' | tr '\r' '\n' > README.rst
	poetry build
	cp README.rst.tmp README.rst
	rm README.rst.tmp

.PHONY: install
install:
	poetry install --no-interaction -E uvloop -E protobuf -E aiodns -E opentelemetry -E opentelemetry-exporter-prometheus

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
	poetry run pytest -n auto tests -v
	poetry run python -m tomodachi.run tests/run_example_service.py
	poetry run tomodachi run --loop uvloop tests/run_example_service.py

.PHONY: pytest
pytest:
	poetry run pytest -n auto tests -v

.PHONY: _check_release
_check_release:
	if [[ "${VERSION}" == *"dev"* ]]; then \
		echo "Development version (${VERSION}) can not be released."; exit 1; \
	fi
	if [[ "${RELEASED}" ]]; then \
		echo "Version ${VERSION} is already released"; exit 1; \
	fi

.PHONY: _check_build_time
_check_build_time:
	if ! grep __build_time__ tomodachi/__version__.py | grep '= "[^"]' > /dev/null; then \
		echo "Build time value is not set in tomodachi/__version__.py"; exit 1; \
	fi

.PHONY: version
version:
	poetry version `python tomodachi/__version__.py`

.PHONY: _set_dev_version
_set_dev_version:
	if ! [[ "${VERSION}" == *"dev"* ]]; then \
		if ! [[ "${RELEASED}" ]]; then \
			echo "Version ${VERSION} has not been released"; exit 1; \
		fi ; \
		DEV_VERSION=$$(python -c "import sys; v=list(map(int, sys.stdin.read().split('.'))); v[-1] += 1; v.append('dev0'); print(tuple(v))" <<< "$$(python tomodachi/__version__.py)") ; \
		sed -i'' -e "s/^__version_info__\([^=]*\)= [(][^)]*[)]/__version_info__\1= $$DEV_VERSION/" tomodachi/__version__.py ; \
		rm -f tomodachi/__version__.py-e ; \
		poetry version `python tomodachi/__version__.py` ; \
	fi

.PHONY: _post_release_commit_dev_version
_post_release_commit_dev_version:
	if [[ "${VERSION}" == *"dev"* ]]; then \
		git commit -m "post-release commit (sets version to `python tomodachi/__version__.py`)" --allow-empty pyproject.toml tomodachi/__version__.py ; \
	fi

.PHONY: _git_release
_git_release: _check_release _check_build_time
	git commit -m "`python tomodachi/__version__.py`" --allow-empty pyproject.toml poetry.lock tomodachi/__version__.py CHANGES.rst
	git tag -a `python tomodachi/__version__.py` -m `python tomodachi/__version__.py`
	git push
	git push --tags
	$(MAKE) _post_git_release

.PHONY: _post_git_release
_post_git_release: _check_build_time
	$(MAKE) _unset_build_time_value
	$(MAKE) _set_dev_version
	$(MAKE) _post_release_commit_dev_version

.PHONY: _pypi_release
_pypi_release: _check_release _check_build_time
	twine upload dist/tomodachi-`python tomodachi/__version__.py`*

.PHONY: _set_build_time_value
_set_build_time_value:
	sed -i'' -e "s/^__build_time__ = \"[^\"]*\"/__build_time__ = \"`python -c "import datetime; print(datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'))"`\"/" tomodachi/__version__.py
	rm -f tomodachi/__version__.py-e

.PHONY: _unset_build_time_value
_unset_build_time_value:
	sed -i'' -e "s/^__build_time__ = \"[^\"]*\"/__build_time__ = \"\"/" tomodachi/__version__.py
	rm -f tomodachi/__version__.py-e

test: tests
testing: tests
remove: uninstall
linting: lint
linter: lint
develop: install
dev: install
release: _check_release version _set_build_time_value build lint test _pypi_release _git_release
help: default
current-version: help
usage: help
