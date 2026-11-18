PY ?= python3

.PHONY: run demo test seed

run:
	PYTHONPATH=src $(PY) -m storyforge.web

seed:
	PYTHONPATH=src $(PY) scripts/seed_demo.py

demo: export PB_PROVIDER = stub
demo: seed
	PYTHONPATH=src $(PY) -m storyforge.web

test:
	PYTHONPATH=src $(PY) -m pytest -q tests
