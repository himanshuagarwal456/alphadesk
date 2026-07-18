"""CLI entry: ``alphadesk-evals``.

Runs dataset inventory checks and offline contract fixtures. Live LLM scoring
is intentionally out of scope for the alpha harness — CI must stay keyless.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tradingagents.evals.contracts import run_contract_checks
from tradingagents.evals.dataset import DEFAULT_DATASET, load_eval_dataset
from tradingagents.evals.governance import EVAL_SUITE_VERSION


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AlphaDesk evaluation harness")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to securities dataset JSON",
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=_fixture_dir(),
        help="Directory of contract payload fixtures (*.json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable summary JSON on stdout",
    )
    args = parser.parse_args(argv)

    cases = load_eval_dataset(args.dataset)
    fixture_results = []
    failures = 0
    for path in sorted(args.fixtures.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        expect_pass = payload.pop("expect_pass", True)
        result = run_contract_checks(payload)
        ok = result.passed if expect_pass else not result.passed
        if not ok:
            failures += 1
        fixture_results.append(
            {
                "fixture": path.name,
                "expect_pass": expect_pass,
                "passed": result.passed,
                "ok": ok,
                "violations": [v.model_dump() for v in result.violations],
            }
        )

    summary = {
        "eval_suite_version": EVAL_SUITE_VERSION,
        "dataset_cases": len(cases),
        "dataset_path": str(args.dataset),
        "fixture_count": len(fixture_results),
        "failures": failures,
        "fixtures": fixture_results,
        "cap_buckets": sorted({c.cap_bucket for c in cases}),
        "scenarios": sorted({c.scenario for c in cases}),
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"AlphaDesk evals ({EVAL_SUITE_VERSION})")
        print(f"  dataset: {len(cases)} cases from {args.dataset}")
        print(f"  fixtures: {len(fixture_results)} checked, {failures} failed")
        for item in fixture_results:
            mark = "ok" if item["ok"] else "FAIL"
            print(f"    [{mark}] {item['fixture']}")
            if not item["ok"]:
                for vio in item["violations"]:
                    print(f"       - {vio['check']}: {vio['message']}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
