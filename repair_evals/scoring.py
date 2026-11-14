"""Field-aware deterministic scoring; no model judge or prose interpretation."""
import math


def compare(expected, actual):
    mismatches = []
    checked = 0

    def walk(want, got, path):
        nonlocal checked
        if isinstance(want, dict):
            checked += 1
            if not isinstance(got, dict):
                mismatches.append(path + ": expected object")
                return
            if set(want) != set(got):
                mismatches.append(path + ": keys differ")
            for key, value in want.items():
                if key in got:
                    walk(value, got[key], path + "." + key)
            return
        if isinstance(want, list):
            checked += 1
            if not isinstance(got, list) or len(want) != len(got):
                mismatches.append(path + ": array shape differs")
                return
            for i, (a, b) in enumerate(zip(want, got)):
                walk(a, b, f"{path}[{i}]")
            return
        checked += 1
        if isinstance(want, bool) or want is None or isinstance(want, str):
            good = type(want) is type(got) and want == got
        elif isinstance(want, (int, float)):
            good = (isinstance(got, (int, float)) and not isinstance(got, bool)
                    and math.isfinite(got) and math.isclose(want, got, rel_tol=1e-7, abs_tol=1e-8))
        else:
            good = type(want) is type(got) and want == got
        if not good:
            mismatches.append(path + ": value differs")

    walk(expected, actual, "output")
    return {"passed": not mismatches, "score": max(0., 1 - len(mismatches) / max(1, checked)),
            "checks": checked, "mismatch_count": len(mismatches), "mismatches": mismatches[:12]}
