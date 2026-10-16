# Pipeline DVF — chaque cible délègue à run.py (utilisable aussi sous Windows :
# `python run.py <cible>`).
PYTHON ?= python

.PHONY: all db-up download clean load analyze export export-web check test notebook validate-pbi web-dev db-down

all:
	$(PYTHON) run.py all

db-up:
	$(PYTHON) run.py db-up

download:
	$(PYTHON) run.py download

clean:
	$(PYTHON) run.py clean

load:
	$(PYTHON) run.py load

analyze:
	$(PYTHON) run.py analyze

export:
	$(PYTHON) run.py export

export-web:
	$(PYTHON) run.py export-web

check:
	$(PYTHON) run.py check

test:
	$(PYTHON) run.py test

notebook:
	$(PYTHON) run.py notebook

validate-pbi:
	$(PYTHON) run.py validate-pbi

web-dev:
	cd web && npm install && npm run dev

db-down:
	docker compose down
