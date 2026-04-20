# CortexAgent CI Workflows

## ragas_gate.yml — RAGAS Quality Gate

This workflow runs on every pull request to `main` and blocks merges if LLM quality regresses below thresholds.

### What it does

1. Sets up Python 3.11 + dependencies
2. Reconstructs `.env` from GitHub Secrets
3. Validates LLM connectivity (smoke test)
4. Ingests a single SEC 10-K (AAPL only, for speed)
5. Runs RAGAS on the 5-question CI subset
6. Posts results to PR summary
7. **Fails the PR** if any threshold is not met:
   - Faithfulness >= 0.40
   - Answer Relevancy >= 0.20
   - Context Precision >= 0.25

### Required GitHub Secrets

Configure these in your repo:
**Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude Haiku for Writer, Claude Sonnet for Critic/RAGAS judge |
| `GEMINI_API_KEY` | Gemini Flash Lite for Researcher/Analyst |
| `GROQ_API_KEY` | Groq Llama for fallback tier |
| `SEC_IDENTITY` | SEC EDGAR User-Agent (e.g. "Yashwanth your.email@gmail.com") |

### Cost per CI run

Approximately $0.30-0.50 in Anthropic credits (Claude judge calls).
Fully free on Gemini + Groq tiers.

### How to disable temporarily

Rename `ragas_gate.yml` to `ragas_gate.yml.disabled` to stop runs.

### Manual trigger

Use the **Actions** tab → "RAGAS Quality Gate" → "Run workflow" button.

### Concurrency

The workflow uses a concurrency group to cancel in-progress runs when new commits push to the same PR. This saves money and time.
