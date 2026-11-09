.PHONY: test smoke

test:
	python -m pytest backend/tests -q

smoke:
	python scripts/smoke.py
