.PHONY: help install dev test lint daemon ping status clean ui

# Prioritize the project virtual environment, then Conda, then system python
PYTHON ?= $(shell \
	if [ -f ".venv/bin/python3" ]; then echo ".venv/bin/python3"; \
	elif [ -f "/opt/anaconda3/bin/python3" ]; then echo "/opt/anaconda3/bin/python3"; \
	else which python3; fi)

help:
	@echo "AURA OS Development Commands:"
	@echo "  make install     - Setup virtualenv and install dependencies"
	@echo "  make test        - Run all unit tests with pytest"
	@echo "  make lint        - Run code style checks"
	@echo "  make daemon      - Run aurad daemon locally"
	@echo "  make ping        - Ping running aurad daemon via CLI"
	@echo "  make status      - Inspect running aurad daemon status"
	@echo "  make ui          - Launch web-based desktop HUD simulator"
	@echo "  make clean       - Clean temporary artifacts and cache"

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/unit/ -v

lint:
	$(PYTHON) -m ruff check aura tests

daemon:
	$(PYTHON) -m aura.core.main

ping:
	$(PYTHON) -m aura.cli ping

status:
	$(PYTHON) -m aura.cli status

ui:
	$(PYTHON) -m aura.ui.server

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build dist *.egg-info .coverage
