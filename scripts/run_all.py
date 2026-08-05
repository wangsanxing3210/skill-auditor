#!/usr/bin/env python3
"""run_all.py — one-shot full audit pipeline (zero config, zero model).

Runs every phase in order and emits the final REPORT.md, so beginners and
automation users never need to learn the individual scripts:

  Phase 1  audit_skill.py           -> .skill-audit/audit.json
  Phase 1  semantic_analyzer.py     -> .skill-audit/semantic.json
  Phase 2  trace_eval.py            -> .skill-audit/trace.json
  Phase 3  skill_tester.py --run    -> .skill-audit/testplan.json (heuristic eval)
  Phase 5  build_report.py          -> .skill-audit/REPORT.md

Prints a one-line summary (findings / TRACE / static / cases). Stdlib only.

Usage:
  python3 run_all.py <target> [--out REPORT.md] [--json]
"""
import os
import sys
import json
import argparse
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _run(script, args, cwd=None):
    """Run one sibling script, return (returncode, stdout)."""
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, script)] + args
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="一键跑完 skill-auditor 全流程并生成 REPORT.md")
    ap.add_argument("target", help="Skill 目录或 SKILL.md 路径")
    ap.add_argument("--out", default=None, help="REPORT.md 输出路径（默认 <target>/.skill-audit/REPORT.md）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 摘要")
    args = ap.parse_args()

    try:
        skill = C.load_skill(args.target)
        target = skill["dir"]
    except Exception as e:
        code, message, next_step = C.humanize_error(e, "run_all")
        print("[%s] %s" % (code, message))
        if next_step:
            print("下一步: %s" % next_step)
        sys.exit(1)

    art_dir = os.path.join(target, ".skill-audit")
    os.makedirs(art_dir, exist_ok=True)

    steps = [
        ("audit_skill.py", ["--json", target], "audit.json"),
        ("semantic_analyzer.py", [os.path.join(target, "SKILL.md"), "--json"], "semantic.json"),
        ("trace_eval.py", ["--json", target], "trace.json"),
        ("skill_tester.py", ["--run", target], "testplan.json"),
    ]
    failures = []
    for script, cargs, out_name in steps:
        rc, out = _run(script, cargs)
        if rc != 0:
            failures.append("%s (exit %d)" % (script, rc))
            continue
        with open(os.path.join(art_dir, out_name), "w", encoding="utf-8") as f:
            f.write(out)

    # Phase 5: build report from artifacts
    rc, _ = _run("build_report.py", [target, "--out", args.out] if args.out else [target])
    if rc != 0:
        failures.append("build_report.py (exit %d)" % rc)

    # summary
    audit = _load(os.path.join(art_dir, "audit.json"))
    trace = _load(os.path.join(art_dir, "trace.json"))
    testplan = _load(os.path.join(art_dir, "testplan.json"))
    n_findings = len(audit.get("findings", [])) if audit else 0
    overall = trace.get("overall", "—") if trace else "—"
    grade = trace.get("grade", "—") if trace else "—"
    s = (testplan or {}).get("summary", {})
    static = "%d/%d" % (s.get("static_pass", 0), s.get("static_total", 0))
    cases = "%d 条" % s.get("cases_total", 0)

    report_path = args.out or os.path.join(art_dir, "REPORT.md")
    summary = {
        "ok": not failures,
        "report": report_path,
        "findings": n_findings,
        "trace_overall": overall,
        "grade": grade,
        "static": static,
        "cases": cases,
        "failures": failures,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    print("== 全流程完成 ==")
    print("  报告: %s" % report_path)
    print("  发现: %d 条 | TRACE: %s (%s) | 静态: %s | 用例: %s" %
          (n_findings, overall, grade, static, cases))
    if failures:
        print("  ⚠ 部分步骤失败: %s" % ", ".join(failures))
        sys.exit(1)


if __name__ == "__main__":
    main()
