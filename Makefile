.PHONY: install dev test lint seed eval-retrieval eval-generation eval-wtt render-pdfs seed-pdf bench gate train-claim-detector build

install:            ## backend + frontend dependencies
	uv sync --group dev
	cd frontend && npm ci

dev:                ## run the API (http://127.0.0.1:8000/docs)
	uv run uvicorn finsight.main:app --reload

test:
	uv run pytest

lint:
	uv run ruff check .

seed:               ## download the public sample corpus and index it (v2 engine)
	uv run python -m scripts.seed_demo --engine v2

eval-retrieval:     ## hit@k / MRR / nDCG for every retrieval mode
	uv run python -m eval.retrieval

eval-generation:    ## answer correctness, faithfulness, abstention (needs an LLM)
	uv run python -m eval.generation

eval-wtt:           ## Walk the Talk vs human-labelled claims (needs an LLM)
	uv run python -m eval.wtt --engine v2

render-pdfs:        ## render the sample HTML filings to PDF (headless Chrome)
	uv run python -m scripts.render_pdfs

seed-pdf:           ## index the rendered PDFs into their own corpus store
	FINSIGHT_CORPUS=pdf uv run python -m scripts.seed_demo --format pdf --engine v2

bench:              ## retrieval latency percentiles
	uv run python -m eval.bench retrieval

gate:               ## CI retrieval gate against eval/thresholds.json (uses the latest ci run or the given file)
	uv run python -m eval.gate eval/results/retrieval_ci.json --corpus html

train-claim-detector: ## build silver/gold sets and fine-tune the forward-looking-claim classifier
	uv run python -m finsight.ml.claims.dataset && uv run python -m finsight.ml.claims.train

build:
	cd frontend && npm run build
