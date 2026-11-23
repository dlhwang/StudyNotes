"""python -m study_notes.eval [--case ID]"""

from __future__ import annotations

import argparse
import asyncio
import sys

from study_notes.eval.runner import run_all


def main() -> int:
    parser = argparse.ArgumentParser(description="평가 질문 실행")
    parser.add_argument("--case", help="이 ID만 실행")
    args = parser.parse_args()
    results = asyncio.run(run_all(args.case))
    passed = sum(r.passed for r in results)
    for r in results:
        mark = "통과" if r.passed else "실패"
        sys.stdout.write(f"[{mark}] {r.case.id} {r.case.question}\n")
        if not r.passed:
            sys.stdout.write(f"    의도 {r.intents} (기대 {r.case.expected_intent}), 빠진 말 {r.missing}\n")
            sys.stdout.write(f"    답: {r.answer[:200]}\n")
    sys.stdout.write(f"\n{passed}/{len(results)} 통과\n")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
