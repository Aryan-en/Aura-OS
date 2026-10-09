.PHONY: help install dev test lint daemon ping status clean ui rpi-setup rpi-hwcheck rpi-daemon rpi-ui rpi-services-install rpi-services-start rpi-services-status rpi-services-stop

# Prioritize the project virtual environment, then Conda, then system python
PYTHON ?= $(shell \
	if [ -f ".venv/bin/python3" ]; then echo ".venv/bin/python3"; \
	elif [ -f "/opt/anaconda3/bin/python3" ]; then echo "/opt/anaconda3/bin/python3"; \
	else which python3; fi)

help:
	@echo "AURA OS Development Commands:"
	@echo "  make install             - Setup virtualenv and install dependencies"
	@echo "  make test                - Run all unit tests with pytest"
	@echo "  make lint                - Run code style checks"
	@echo "  make daemon              - Run aurad daemon locally"
	@echo "  make ping                - Ping running aurad daemon via CLI"
	@echo "  make status              - Inspect running aurad daemon status"
	@echo "  make ui                  - Launch web-based desktop HUD simulator"
	@echo "  make clean               - Clean temporary artifacts and cache"
	@echo ""
	@echo "Raspberry Pi 5 Commands:"
	@echo "  make rpi-setup           - Run automated Pi 5 provisioning script"
	@echo "  make rpi-hwcheck         - Run Pi 5 hardware diagnostics & check devices"
	@echo "  make rpi-daemon          - Run aurad locally with Pi 5 hardware profile"
	@echo "  make rpi-ui              - Run HUD server bound to 0.0.0.0:8765 for LAN"
	@echo "  make rpi-services-install- Deploy systemd user services for aurad and HUD"
	@echo "  make rpi-services-start  - Start systemd background services"
	@echo "  make rpi-services-status - Inspect status of systemd services"
	@echo "  make rpi-services-stop   - Stop systemd services"

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

rpi-setup:
	bash scripts/rpi5/setup.sh

rpi-hwcheck:
	$(PYTHON) scripts/rpi5/test_hardware.py

rpi-daemon:
	$(PYTHON) -m aura.core.main --config config/rpi5.yaml

rpi-ui:
	$(PYTHON) -m aura.ui.server --host 0.0.0.0 --port 8765

rpi-services-install:
	mkdir -p $(HOME)/.config/systemd/user
	cp services/systemd/aura-core.service $(HOME)/.config/systemd/user/
	cp services/systemd/aura-ui.service $(HOME)/.config/systemd/user/
	systemctl --user daemon-reload
	@echo "Systemd user services installed. Enable with: systemctl --user enable aura-core aura-ui"

rpi-services-start:
	systemctl --user start aura-core aura-ui

rpi-services-status:
	systemctl --user status aura-core aura-ui

rpi-services-stop:
	systemctl --user stop aura-core aura-ui

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build dist *.egg-info .coverage
