.PHONY: all test clean tests build dist
ifndef VERBOSE
.SILENT:
endif

SHELL := /bin/bash
VERSION=`python tomodachi/__version__.py`
RELEASED := $(shell git tag | grep ^${VERSION}$$)
PYTEST_INSTALLED := $(shell pip freeze |grep pytest==)

default:
	@echo "Current version info collected: ${VERSION}"
	if [[ "${RELEASED}" ]]; then echo "Version is already released"; else echo "Version can be released"; fi
	@echo ""
	@echo "Usage:"
	@echo "make install        | install package"
	@echo "make uninstall      | remove installed package"
	@echo "make development    | install development dependencies"
	@echo "make test           | run test suite"
	@echo "make lint           | run linters"
	@echo "make release        | tag and push a new version"

build:
	python setup.py sdist bdist_wheel

install:
	pip install -U .

development:
	pip install -r requirements.txt

uninstall:
	pip uninstall -y tomodachi

lint:
	pycodestyle --ignore E203,W503,E501 --exclude proto_build,build,tmp .
	mypy ./
	@echo "ok"

clean:
	rm -rf build dist
	@echo "done"

tests:
	if [[ ! "${PYTEST_INSTALLED}" ]]; then make development; fi
	PYTHONPATH=. py.test -n auto tests/
	PYTHONPATH=. python tomodachi.py run tests/run_example_service.py
	PYTHONPATH=. python setup.py check -r -s

pytest:
	if [[ ! "${PYTEST_INSTALLED}" ]]; then make development; fi
	PYTHONPATH=. py.test -n auto tests/

_check_release:
	if [[ "${RELEASED}" ]]; then echo "Version ${VERSION} is already released"; exit 1; fi

_git_release:
	git commit -m "`python tomodachi/__version__.py`" --allow-empty tomodachi/__version__.py CHANGES.rst
	git tag -a `python tomodachi/__version__.py` -m `python tomodachi/__version__.py`
	git push
	git push --tags

_pypi_release:
	twine upload dist/tomodachi-`python tomodachi/__version__.py`*

test: tests
testing: tests
remove: uninstall
linting: lint
linter: lint
develop: development
dev: development
release: _check_release build lint test _pypi_release _git_release
version: release
help: default
current-version: help
usage: help
dev: development
