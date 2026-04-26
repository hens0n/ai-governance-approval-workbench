.PHONY: install test run demo reset

install:
	python -m pip install -e '.[dev]'

test:
	pytest

run:
	uvicorn app.main:app --reload --port 8000

demo:
	docker compose -f docker/compose.yml up --build

reset:
	rm -rf data
	mkdir -p data/attachments
