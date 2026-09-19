.PHONY: install dev test lint seed eval-retrieval eval-generation build

install:            ## backend + frontend dependencies
	uv sync --group dev
	cd frontend && npm ci

dev:                ## run the API (http://127.0.0.1:8000/docs)
	uv run uvicorn finsight.main:app --reload

test:
	uv run pytest

lint:
	uv run ruff check .

seed:               ## download the public sample corpus and index it
	uv run python -m scripts.seed_demo

eval-retrieval:     ## hit@k / MRR / nDCG for every retrieval mode
	uv run python -m eval.retrieval

eval-generation:    ## answer correctness, faithfulness, abstention (needs an LLM)
	uv run python -m eval.generation

build:
	cd frontend && npm run build
