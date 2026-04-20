# Contributing to CortexAgent

Thanks for contributing. CortexAgent is both an engineering project and a portfolio artifact, so contributions should optimize for code quality, clarity, and a readable commit history.

This file is the short practical guide. A more CI-focused contributor note also exists at [`.github/CONTRIBUTING.md`](./.github/CONTRIBUTING.md).

## Project Philosophy

CortexAgent is not a toy chatbot. The project is intended to demonstrate production AI engineering practices:

- grounded retrieval
- explicit orchestration
- evaluation infrastructure
- safety testing
- cost-aware model routing
- observability and auditability

Contributions should preserve that framing. If a change makes the repository feel more like a prompt demo and less like a system, it is probably moving in the wrong direction.

## Before You Start

1. Read the main [README.md](./README.md).
2. Skim the docs in [`docs/`](./docs/).
3. Check whether your change is best framed as:
- a bug fix
- a feature request
- a documentation improvement
- a deployment improvement
- an evaluation or safety improvement

If you are proposing a non-trivial change, open an issue first so the scope is clear before implementation starts.

## Local Setup

Use one of the provided setup paths:

- PowerShell: `scripts/setup.ps1`
- Bash: `scripts/setup.sh`
- Docker: see [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md)

Typical local workflow:

```bash
uv venv
uv pip install -e ".[dev]"
python -m rag.ingestion
python -m api.main
streamlit run dashboard/app.py --server.address 0.0.0.0
```

## Contribution Standards

Every contribution should aim to satisfy four checks:

1. It is technically coherent.
2. It is documented clearly.
3. It does not silently regress evaluation or safety posture.
4. It fits the commit history cleanly.

That means:

- use small, intentional commits
- explain tradeoffs in PR descriptions
- update docs when behavior changes
- avoid speculative refactors unrelated to the scoped task

## Coding Expectations

- Follow the existing Python style and file organization.
- Keep comments rare and useful.
- Prefer explicit names over clever abstractions.
- Preserve auditability when changing agent behavior.
- Do not remove safety checks or evaluation hooks unless there is a documented replacement.

If you touch orchestration, retrieval, evaluation, or safety logic, explain why the change improves the system and how it should be validated.

## Testing Expectations

At minimum, contributors should run the most relevant local checks for their change:

- API smoke test: `python -m api.main`
- dashboard smoke test for UI changes
- `pytest tests/ -v` for unit or integration coverage
- CI-sized RAGAS subset when retrieval or generation behavior changes
- red-team suite when refusal or safety behavior changes

Not every PR needs every test, but every PR should explain what was or was not run.

## Documentation Expectations

Documentation is part of the product surface of this repo. If you change:

- architecture
- retrieval behavior
- evaluation logic
- deployment flow
- environment variables

then update the relevant markdown file in `docs/`, the root README, or both.

## UI Contributions

If you change the Streamlit dashboard:

- include before/after screenshots in the PR when possible
- preserve the premium product feel
- keep recruiter-facing clarity high
- do not regress mobile or LAN-demo usability

## Issue and PR Workflow

- Use the GitHub issue templates when opening new issues.
- Use the pull request template when submitting changes.
- Link issues in PRs when applicable.
- Keep PRs focused on one story whenever possible.

Good examples:

- "improve README product walkthrough screenshots"
- "add Docker deployment scaffolding"
- "tighten feature request templates"

Bad examples:

- "fix stuff"
- "misc cleanup"
- "refactor and docs and tests and UI updates"

## Commit Guidance

Prefer conventional, readable commit messages such as:

- `feat: add Docker deployment scaffolding`
- `docs: strengthen README walkthrough`
- `fix: handle query input state safely in Streamlit`
- `chore: rewrite .env.example with clearer model routing guidance`

## Security and Secrets

- Never commit `.env`.
- Never commit raw provider keys.
- Never paste sensitive logs into issues.
- Sanitize screenshots if they include secrets, emails, or tokens.

## Code of Conduct

By participating in this repository, you agree to follow the project [Code of Conduct](./CODE_OF_CONDUCT.md).

## Questions

If something is unclear, open an issue with context and the smallest reproducible question you can ask. Clear technical questions get better answers and faster merges.
