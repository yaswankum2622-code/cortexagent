# Contributing to CortexAgent

## Development workflow

1. Create a feature branch from `main`
2. Make your changes
3. Run local quality check before pushing:

```bash
python -m evaluation.benchmark_runner \
  --dataset evaluation/golden_dataset_ci.json \
  --output evaluation/ci_report.html \
  --max-questions 5
```

4. Open a PR to `main`
5. Wait for the **RAGAS Quality Gate** to pass
6. Merge once green

## Quality contract

The RAGAS Quality Gate enforces these thresholds on every PR:

- **Faithfulness >= 0.85** — answers must be grounded in retrieved context
- **Answer Relevancy >= 0.80** — answers must address the user's question
- **Context Precision >= 0.75** — retrieved chunks must actually be useful

If your PR fails the gate, look at the uploaded `ragas-ci-report` artifact to see which questions regressed.

## Why a quality gate?

LLM systems can degrade silently when prompts, models, or retrieval logic change. The RAGAS gate ensures regressions are caught at PR time, not in production. This is the same pattern used by Anthropic and other production AI teams.
