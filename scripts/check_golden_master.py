"""Replay every golden master case against the legacy engine."""
from __future__ import annotations

import sys

from _golden import load_cases, request_from_dict, serialize_quote

from staywell.services.pricing import get_quote


def main():
    cases = load_cases()
    failures = []
    for case in cases:
        actual = serialize_quote(get_quote(request_from_dict(case["request"])))
        if actual != case["expected"]:
            diff = {k: (case["expected"][k], actual.get(k)) for k in case["expected"] if case["expected"][k] != actual.get(k)}
            failures.append((case["id"], diff))
    for case_id, diff in failures:
        print(f"FAIL {case_id}: {diff}")
    print(f"{len(cases) - len(failures)}/{len(cases)} golden master cases match the legacy engine")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
