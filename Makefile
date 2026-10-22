PY ?= python3

.PHONY: run demo test seed

run:
	PYTHONPATH=src $(PY) -m storyforge.web

seed:
	PYTHONPATH=src $(PY) scripts/seed_demo.py

demo: seed run

test:
	PYTHONPATH=src $(PY) -m unittest discover -s tests -v
