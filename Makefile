# Earned-Trust PR Factory. Python 3 only; nothing to install.
PY ?= python3

.PHONY: demo review bench dashboard test

demo:            ## offline: 4 briefs, scripted receipts, benchmark, dashboard
	$(PY) factory/et.py demo

review:          ## the 4 briefs from the replay cache
	$(PY) factory/et.py review --offline

bench:
	$(PY) factory/et.py bench

dashboard:
	$(PY) factory/et.py dashboard

test:
	$(PY) -m unittest discover -s factory/tests -t factory
