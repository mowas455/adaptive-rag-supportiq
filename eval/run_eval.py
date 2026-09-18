"""Run the golden Q&A set through the graph and report routing accuracy."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph.build_graph import run_supportiq  # noqa: E402
from src.observability.langfuse_client import get_langfuse  # noqa: E402

GOLDEN_PATH = Path(__file__).resolve().parent / "golden_qa.json"


def main() -> None:
    items = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    rows = []
    by_branch: dict[str, list[bool]] = defaultdict(list)
    langfuse = None
    try:
        langfuse = get_langfuse()
    except Exception:
        langfuse = None

    print(f"Running {len(items)} golden questions…\n")
    for i, item in enumerate(items, 1):
        qid = item["id"]
        question = item["question"]
        expected = item["expected_route"]
        print(f"[{i}/{len(items)}] {qid}: {question}")
        result = run_supportiq(
            question,
            session_id="eval-golden",
            trace_name=f"eval-{qid}",
        )
        actual = result.get("route") or result.get("source_type")
        retried = int(result.get("retry_count") or 0) > 0 or int(
            result.get("regenerate_count") or 0
        ) > 0
        passed = actual == expected
        by_branch[expected].append(passed)
        if result.get("trace_id") and langfuse is not None:
            try:
                langfuse.score(
                    name="routing_accuracy",
                    value=1.0 if passed else 0.0,
                    data_type="NUMERIC",
                    trace_id=result["trace_id"],
                    comment=f"expected={expected} actual={actual}",
                )
                langfuse.flush()
            except Exception as exc:  # noqa: BLE001
                print(f"  (langfuse score failed: {exc})")
        rows.append(
            {
                "id": qid,
                "expected": expected,
                "actual": actual,
                "pass": passed,
                "retry": retried,
                "expect_retry": bool(item.get("expect_retry")),
                "source_type": result.get("source_type"),
                "trace_url": result.get("trace_url"),
            }
        )
        mark = "PASS" if passed else "FAIL"
        print(f"  {mark}  expected={expected} actual={actual} retry={retried}")

    print("\n=== Routing accuracy by branch ===")
    print(f"{'branch':<16} {'n':>4} {'pass':>4} {'acc':>8}")
    total_n = total_p = 0
    for branch in ("vectorstore", "sql_lookup", "web_search"):
        flags = by_branch.get(branch) or []
        n = len(flags)
        p = sum(flags)
        acc = (p / n) if n else 0.0
        total_n += n
        total_p += p
        print(f"{branch:<16} {n:>4} {p:>4} {acc:>7.0%}")
    overall = (total_p / total_n) if total_n else 0.0
    print(f"{'OVERALL':<16} {total_n:>4} {total_p:>4} {overall:>7.0%}")

    print("\n=== Detail ===")
    print(f"{'id':<16} {'exp':<12} {'act':<12} {'ok':<5} {'retry':<6} {'want_retry'}")
    for row in rows:
        print(
            f"{row['id']:<16} {row['expected']:<12} {str(row['actual']):<12} "
            f"{'Y' if row['pass'] else 'N':<5} {'Y' if row['retry'] else 'N':<6} "
            f"{'Y' if row['expect_retry'] else 'N'}"
        )


if __name__ == "__main__":
    main()
