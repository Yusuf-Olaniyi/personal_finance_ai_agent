import asyncio
import json
import os
import sys
from collections import defaultdict

from finance_coach.agents.advisor import FinanceAdvisor
from evals.checks import CHECK_NAMES, Check, run_checks
from evals.scenarios import SCENARIOS

from evals.checks import CHECK_NAMES, Check, run_checks, ungrounded_numbers

DELAY = float(os.getenv("EVAL_DELAY", "60"))      # free tier: about 1 pipeline run per minute
THRESHOLD = float(os.getenv("EVAL_THRESHOLD", "0.9"))
MAX_ATTEMPTS = int(os.getenv("EVAL_ATTEMPTS", "3"))


def is_infra_failure(warnings) -> bool:
    return any("rate limit" in w.lower() for w in warnings)


async def run_once(sc):
    """Returns (result, checks, infra_failed)."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = await FinanceAdvisor().analyze(**sc["inputs"])
        except Exception as e:
            crash = [Check(n, False, f"crash: {type(e).__name__}: {e}") for n in CHECK_NAMES]
            return None, crash, False
        if is_infra_failure(result["warnings"]):
            if attempt < MAX_ATTEMPTS:
                print(f"  rate limited; waiting {DELAY:.0f}s (attempt {attempt}/{MAX_ATTEMPTS})", flush=True)
                await asyncio.sleep(DELAY)
                continue
            return result, [], True
        return result, run_checks(result), False


async def main(n_runs: int):
    stats = defaultdict(lambda: defaultdict(list))
    failures, records, infra_failed = [], [], 0

    for sc in SCENARIOS:
        for i in range(1, n_runs + 1):
            result, checks, infra = await run_once(sc)
            review_notes = []
            output = None
            if result is not None:
                output = {"budget": result["budget"].model_dump(),
                          "savings": result["savings"].model_dump(),
                          "debt": result["debt"].model_dump() if result["debt"] else None,
                          "warnings": result["warnings"]}
            review = ungrounded_numbers(result) if (result is not None and not infra) else []
            if review:
                review_notes.append(f"[{sc['name']} run {i}] {review}")
            if infra:
                infra_failed += 1
            else:
                for c in checks:
                    stats[sc["name"]][c.name].append(c.passed)
                    if not c.passed:
                        failures.append(f"[{sc['name']} run {i}] {c.name}: {c.detail}")
            records.append({"scenario": sc["name"], "run": i, "infra_failed": infra,
                            "output": output, "checks": [c._asdict() for c in checks], "review_notes": review_notes})
            print(f"finished {sc['name']} run {i}/{n_runs}" + (" (INFRA FAILED)" if infra else ""), flush=True)
            
            if review_notes:
                print("\nREVIEW (amounts in the advice that are not in the facts or plans):")
                print("\n".join(review_notes))
            await asyncio.sleep(DELAY)

    total = passed = 0
    print("\n===== RESULTS (completed runs only) =====")
    for name, by_check in stats.items():
        s_pass = sum(sum(v) for v in by_check.values())
        s_total = sum(len(v) for v in by_check.values())
        total, passed = total + s_total, passed + s_pass
        print(f"{name:18} {s_pass}/{s_total} checks passed")
        for cname, vals in by_check.items():
            if not all(vals):
                print(f"    {cname}: {sum(vals)}/{len(vals)}")

    print(f"\nRuns lost to rate limits after retries: {infra_failed}")
    if total == 0:
        print("No completed runs, so nothing to score.")
        sys.exit(2)

    rate = passed / total
    print(f"OVERALL QUALITY: {passed}/{total} = {rate:.0%} (threshold {THRESHOLD:.0%})")
    if failures:
        print("\nFAILURE DETAILS (first 15):")
        print("\n".join(failures[:15]))
    with open("eval_results.json", "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)
    print("\nFull outputs saved to eval_results.json")
    sys.exit(0 if rate >= THRESHOLD else 1)


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 2))