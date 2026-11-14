# Sancho. Python 3 only; nothing to install.
PY ?= python3

.PHONY: demo review bench dashboard test

demo:            ## offline: 4 briefs, scripted receipts, benchmark, dashboard
	$(PY) factory/sancho.py demo

review:          ## the 4 briefs from the replay cache
	$(PY) factory/sancho.py review --offline

bench:
	$(PY) factory/sancho.py bench

dashboard:
	$(PY) factory/sancho.py dashboard

test:
	$(PY) -m unittest discover -s factory/tests -t factory
