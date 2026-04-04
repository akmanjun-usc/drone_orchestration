"""
Evaluation report.

Formats EvalSummary objects into a results table that matches
the structure of Table I in the GSCE paper:
  - Rows: task complexity levels (simple / medium / complex)
  - Columns: success rate, constraint violation rate, avg attempts
  - Two column groups: GSCE vs Baseline
"""

from eval.metrics import EvalSummary

_COMPLEXITIES = ["simple", "medium", "complex"]
_COL_W = 10


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _row(
    label: str,
    gsce: EvalSummary,
    base: EvalSummary,
    complexity: str | None = None,
) -> str:
    g = gsce.by_complexity(complexity) if complexity else gsce
    b = base.by_complexity(complexity) if complexity else base

    def avg_attempts(s: EvalSummary) -> str:
        if not s.scores:
            return "—"
        return f"{sum(sc.attempts for sc in s.scores) / len(s.scores):.1f}"

    cols = [
        label.ljust(10),
        _pct(g.success_rate).rjust(_COL_W),
        _pct(g.constraint_violation_rate).rjust(_COL_W),
        avg_attempts(g).rjust(_COL_W),
        " | ",
        _pct(b.success_rate).rjust(_COL_W),
        _pct(b.constraint_violation_rate).rjust(_COL_W),
        avg_attempts(b).rjust(_COL_W),
    ]
    return "  ".join(cols)


def _divider(char: str = "-") -> str:
    return char * 78


def print_report(gsce: EvalSummary, baseline: EvalSummary) -> None:
    """
    Print a formatted comparison report to stdout.

    Args:
        gsce: EvalSummary from the GSCE prompt run.
        baseline: EvalSummary from the baseline prompt run.
    """
    header_label = "Task level".ljust(10)
    col_h = lambda t: t.rjust(_COL_W)

    print()
    print(_divider("="))
    print("  GSCE vs Baseline — Evaluation Results")
    print(_divider("="))
    print(
        f"  {header_label}  "
        f"{'GSCE':^32}  |  {'Baseline':^32}"
    )
    sub_header = (
        "  " + " " * 10 + "  "
        + col_h("success") + "  " + col_h("viol.rate") + "  " + col_h("avg tries")
        + "  |  "
        + col_h("success") + "  " + col_h("viol.rate") + "  " + col_h("avg tries")
    )
    print(sub_header)
    print(_divider())

    for level in _COMPLEXITIES:
        print(_row(level.capitalize(), gsce, baseline, complexity=level))

    print(_divider())
    print(_row("Overall", gsce, baseline))
    print(_divider("="))
    print()

    # Per-task detail
    print("  Per-task breakdown:")
    print(_divider())
    all_ids = sorted(
        set(s.task_id for s in gsce.scores) | set(s.task_id for s in baseline.scores)
    )
    gsce_by_id = {s.task_id: s for s in gsce.scores}
    base_by_id = {s.task_id: s for s in baseline.scores}

    for tid in all_ids:
        g = gsce_by_id.get(tid)
        b = base_by_id.get(tid)
        g_str = ("PASS" if g and g.passed else "FAIL") if g else "n/a"
        b_str = ("PASS" if b and b.passed else "FAIL") if b else "n/a"
        g_msg = g.validation_message if g else ""
        complexity = g.complexity if g else (b.complexity if b else "")
        print(
            f"  [{tid}] ({complexity:7s})  "
            f"GSCE: {g_str:4s}  Baseline: {b_str:4s}"
            + (f"  — {g_msg}" if g_msg else "")
        )

    print(_divider("="))
    print()


def save_report_csv(gsce: EvalSummary, baseline: EvalSummary, path: str = "eval_results.csv") -> None:
    """
    Save per-task results as CSV for further analysis.

    Args:
        gsce: EvalSummary from the GSCE prompt run.
        baseline: EvalSummary from the baseline prompt run.
        path: Output CSV file path.
    """
    import csv

    rows = []
    gsce_by_id = {s.task_id: s for s in gsce.scores}
    base_by_id = {s.task_id: s for s in baseline.scores}
    all_ids = sorted(set(gsce_by_id) | set(base_by_id))

    for tid in all_ids:
        g = gsce_by_id.get(tid)
        b = base_by_id.get(tid)
        rows.append({
            "task_id": tid,
            "complexity": (g or b).complexity,
            "gsce_passed": int(g.passed) if g else "",
            "gsce_attempts": g.attempts if g else "",
            "gsce_violations": len(g.constraint_violations) if g else "",
            "gsce_input_tokens": g.input_tokens if g else "",
            "gsce_output_tokens": g.output_tokens if g else "",
            "baseline_passed": int(b.passed) if b else "",
            "baseline_attempts": b.attempts if b else "",
            "baseline_violations": len(b.constraint_violations) if b else "",
            "baseline_input_tokens": b.input_tokens if b else "",
            "baseline_output_tokens": b.output_tokens if b else "",
            "model": (g or b).model,
        })

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Results saved to {path}")
