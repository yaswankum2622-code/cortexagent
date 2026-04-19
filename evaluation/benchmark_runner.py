"""CLI entry point for RAGAS evaluation. Used both for local runs and GitHub Actions CI gate."""

import argparse
import json
import os
import sys
from pathlib import Path

from config.logging_setup import configure_logging
from config.settings import settings


def main() -> int:
    """Run the evaluation pipeline and return a CI-friendly exit code."""
    os.environ["CORTEX_EVAL_MODE"] = "1"
    print("[EVAL_MODE] CortexAgent Writer configured for concise output (250 word target)")

    from evaluation.ragas_eval import (
        check_thresholds,
        generate_html_report,
        run_orchestrator_on_dataset,
        run_ragas_eval,
    )

    parser = argparse.ArgumentParser(description="Run RAGAS evaluation on a golden dataset.")
    parser.add_argument("--dataset", required=True, help="Path to golden_dataset JSON")
    parser.add_argument("--output", required=True, help="Path for HTML report output")
    parser.add_argument(
        "--max-questions",
        type=int,
        default=None,
        help="Limit to first N questions (for CI)",
    )
    parser.add_argument(
        "--save-raw",
        default=None,
        help="Optional path to save raw JSON results",
    )
    parser.add_argument(
        "--raw-answers",
        action="store_true",
        help="Disable preprocessing - send raw Markdown reports to RAGAS (for comparison)",
    )
    args = parser.parse_args()

    configure_logging(settings.log_level)

    print("=" * 70)
    print("CortexAgent - RAGAS Evaluation")
    print(f"Dataset: {args.dataset}")
    print(f"Max questions: {args.max_questions or 'all'}")
    print(f"Output: {args.output}")
    print("=" * 70)

    orchestrator_results = run_orchestrator_on_dataset(
        args.dataset,
        max_questions=args.max_questions,
    )
    eval_results = run_ragas_eval(
        orchestrator_results,
        use_preprocessing=not args.raw_answers,
    )

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    generate_html_report(eval_results, args.output)

    if args.save_raw:
        Path(args.save_raw).parent.mkdir(parents=True, exist_ok=True)
        with open(args.save_raw, "w", encoding="utf-8") as handle:
            json.dump(eval_results, handle, indent=2)
        print(f"Raw JSON saved to: {args.save_raw}")

    aggregate = eval_results.get("aggregate", {})
    print("\n" + "=" * 70)
    print("AGGREGATE SCORES")
    print("=" * 70)
    for metric, score in aggregate.items():
        print(f"  {metric:<22}: {score:.3f}")

    passed, failures = check_thresholds(eval_results)
    print("\n" + ("PASSED all thresholds." if passed else "FAILED thresholds:"))
    for failure in failures:
        print(f"  - {failure}")

    errored = int(eval_results.get("errored_questions", 0) or 0)
    if errored > 0:
        print(f"\n{errored} question(s) errored: {eval_results.get('errored_ids', [])}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
