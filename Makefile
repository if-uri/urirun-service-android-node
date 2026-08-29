.PHONY: install test run clean

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

install:
	$(PIP) install -e ".[test]"

test:
	$(PIP) install -e ".[test]" >/dev/null
	$(PYTHON) -m pytest -q tests

run:
	$(PYTHON) -m urirun_service_android_node.core

clean:
	rm -rf build dist *.egg-info .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
