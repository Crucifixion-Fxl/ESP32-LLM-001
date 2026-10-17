PYTHON ?= python3
UV ?= uv
IDF ?= idf.py
MASTER_BUILD ?= $(CURDIR)/firmware/master/build
NODE_BUILD ?= $(CURDIR)/firmware/node/build

.DEFAULT_GOAL := help
.PHONY: help setup check test test-repository build build-master build-node diagrams diagrams-check

help:
	@printf '%s\n' \
	  'make setup            Install locked host dependencies with uv' \
	  'make check            Check source references, docs, diagrams and shell syntax' \
	  'make test             Run all host regression tests (no board required)' \
	  'make test-repository  Run dependency-free repository tests' \
	  'make build            Build master and node firmware (activate ESP-IDF first)' \
	  'make build-master     Build master firmware only' \
	  'make build-node       Build node firmware only' \
	  'make diagrams         Regenerate documentation SVGs' \
	  'make diagrams-check   Check generated SVGs without writing files'

setup:
	$(UV) sync --locked

check: diagrams-check
	$(PYTHON) scripts/check_repository.py
	bash -n scripts/train_container.sh

test:
	$(UV) run --locked python -m unittest discover -s tests -v

test-repository:
	$(PYTHON) -m unittest discover -s tests -p test_repository.py -v

build: build-master build-node

build-master:
	$(IDF) -C firmware/master -B "$(abspath $(MASTER_BUILD))" build

build-node:
	$(IDF) -C firmware/node -B "$(abspath $(NODE_BUILD))" build

diagrams:
	$(PYTHON) scripts/render_diagrams.py

diagrams-check:
	$(PYTHON) scripts/render_diagrams.py --check
