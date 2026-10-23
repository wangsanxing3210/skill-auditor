#!/usr/bin/env python3
"""run_all.py — one-shot full audit pipeline (zero config, zero model).

Runs every phase in order and emits the final REPORT.md, so beginners and
automation users never need to learn the individual scripts:

  Phase 1  audit_skill.py           -> .skill-audit/audit.json
  Phase 1  semantic_analyzer.py     -> .skill-audit/semantic.json
  Phase 1  security_analyzer.py     -> .skill-audit/security.json
  Phase 2  trace_eval.py            -> .skill-audit/trace.json
  Phase 3  skill_tester.py --run    -> .skill-audit/testplan.json (heuristic eval)
  Phase 5  build_report.py          -> .skill-audit/REPORT.md

Prints a one-line summary (findings / TRACE / static / cases). Stdlib only.

CI 门禁：--fail-on {none,low,medium,high} 按最高严重度卡口，--fail-under <分数>
按 TRACE 总分卡口；触发时进程退出码为 2（步骤失败为 1），便于 pipeline 区分。

Usage:
  python3 run_all.py <target> [--out REPORT.md] [--json]
                     [--fail-on none|low|medium|high] [--fail-under 80]
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
    """Run one sibling script, return (returncode, stdout).

    Encoding is pinned to UTF-8 on both ends: on Windows the default locale
    codec would fail to decode the Chinese JSON payloads these scripts emit.
    """
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, script)] + args
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd,
                       encoding="utf-8", errors="replace", env=C.child_env())
    return r.returncode, r.stdout


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="一键跑完 skill-inspector 全流程并生成 REPORT.md")
    ap.add_argument("target", help="Skill 目录或 SKILL.md 路径")
    ap.add_argument("--out", default=None, help="REPORT.md 输出路径（默认 <target>/.skill-audit/REPORT.md）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 摘要")
    ap.add_argument("--fail-on", choices=["none", "low", "medium", "high"], default="none",
                    help="CI 门禁：发现达到该严重度即以退出码 2 失败（默认 none 不卡）")
    ap.add_argument("--fail-under", type=float, default=None,
                    help="CI 门禁：TRACE 总分低于该值时以退出码 2 失败")
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
        ("security_analyzer.py", ["--json", target], "security.json"),
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
    security = _load(os.path.join(art_dir, "security.json"))
    n_findings = len(audit.get("findings", [])) if audit else 0
    n_security = len(security.get("findings", [])) if security else 0
    overall = trace.get("overall", "—") if trace else "—"
    grade = trace.get("grade", "—") if trace else "—"
    s = (testplan or {}).get("summary", {})
    static = "%d/%d" % (s.get("static_pass", 0), s.get("static_total", 0))
    cases = "%d 条" % s.get("cases_total", 0)

    # CI gates
    sev_rank = {"low": 1, "medium": 2, "high": 3}
    all_findings = (audit or {}).get("findings", []) + (security or {}).get("findings", [])
    worst = max([sev_rank.get(f.get("severity", "low"), 1) for f in all_findings] or [0])
    gate_failed = []
    if args.fail_on != "none" and worst >= sev_rank[args.fail_on]:
        gate_failed.append("存在 ≥%s 级发现" % args.fail_on)
    if args.fail_under is not None and isinstance(overall, (int, float)) and overall < args.fail_under:
        gate_failed.append("TRACE %s < %s" % (overall, args.fail_under))

    report_path = args.out or os.path.join(art_dir, "REPORT.md")
    summary = {
        "ok": not failures and not gate_failed,
        "report": report_path,
        "findings": n_findings,
        "security_findings": n_security,
        "trace_overall": overall,
        "grade": grade,
        "static": static,
        "cases": cases,
        "failures": failures,
        "gate_failed": gate_failed,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        sys.exit(2 if gate_failed else (1 if failures else 0))

    print("== 全流程完成 ==")
    print("  报告: %s" % report_path)
    print("  发现: %d 条 | 安全: %d 条 | TRACE: %s (%s) | 静态: %s | 用例: %s" %
          (n_findings, n_security, overall, grade, static, cases))
    if failures:
        print("  ⚠ 部分步骤失败: %s" % ", ".join(failures))
    if gate_failed:
        print("  ✗ 门禁未通过: %s" % "；".join(gate_failed))
    if failures:
        sys.exit(1)
    if gate_failed:
        sys.exit(2)


if __name__ == "__main__":
    main()
