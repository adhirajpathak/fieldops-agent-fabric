.PHONY: install ingest api eval test docker

install:
	python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"

ingest:
	LLM_PROVIDER=mock fieldops-ingest

api:
	LLM_PROVIDER=mock fieldops-api

eval:
	LLM_PROVIDER=mock fieldops-eval

test:
	LLM_PROVIDER=mock pytest -q

docker:
	docker build -t fieldops-agent-fabric .
	docker run --rm -p 8080:8080 fieldops-agent-fabric
