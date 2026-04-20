# CortexAgent - Developer Convenience Commands
#
# On Windows without Make: use the PowerShell equivalents in scripts/setup.ps1
# On macOS/Linux: `make <target>`

.PHONY: help setup install ingest test ragas-ci red-team api dashboard demo demo-single health docker-up docker-down docker-logs clean

help:  ## Show this help message
	@echo "CortexAgent - Available Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup:  ## One-command local setup (bash)
	bash scripts/setup.sh

install:  ## Install Python dependencies with uv
	uv pip install -e ".[dev]"

ingest:  ## Download and chunk SEC 10-K filings (one-time)
	python -m rag.ingestion

test:  ## Run pytest test suite
	pytest tests/ -v

ragas-ci:  ## Run RAGAS on the 5-question CI subset
	python -m evaluation.benchmark_runner --dataset evaluation/golden_dataset_ci.json --output evaluation/ci_report.html --max-questions 5

red-team:  ## Run the full 20-prompt red-team adversarial suite
	python -m evaluation.red_team

api:  ## Start the FastAPI backend on 0.0.0.0:8000
	python -m api.main

dashboard:  ## Start the Streamlit dashboard on 0.0.0.0:8501
	streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501

demo:  ## Run the interview-style 2-query live demo
	python scripts/run_demo.py

demo-single:  ## Run the shorter one-query demo for time-boxed interviews
	python scripts/run_demo.py --single

health:  ## Ping the FastAPI health endpoint when the API is running
	curl http://localhost:8000/health

docker-up:  ## Start both API and dashboard via docker-compose
	docker-compose up -d

docker-down:  ## Stop and remove the docker-compose stack
	docker-compose down

docker-logs:  ## Tail logs from both services
	docker-compose logs -f

clean:  ## Remove caches and build artifacts
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
