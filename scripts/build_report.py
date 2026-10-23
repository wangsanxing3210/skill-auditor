#!/usr/bin/env python3
"""build_report.py — assemble the final Phase 5 deliverable from .skill-audit artifacts.

Reads the JSON artifacts produced by the other scripts plus the optional
optimization-report.md, renders `assets/report_template.md` (a minimal
{{placeholder}} / {% for %} template), and writes the final REPORT.md.

Stdlib only. Zero model / network dependency.

Usage:
  python3 build_report.py <target> [--config config.json] [--out REPORT.md]
"""
import os
import sys
import re
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C


def _load(name, skill_dir):
    p = os.path.join(skill_dir, ".skill-audit", name)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _merge_findings(audit, semantic):
    out = []
    if audit:
        out.extend(audit.get("findings", []))
    if semantic:
        out.extend(semantic.get("semantic_findings", []))
    # de-dup by (rule_id, location)
    seen = set()
    uniq = []
    for f in out:
        k = (f.get("rule_id"), f.get("location"))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(f)
    return uniq


def _dim_score(trace, dim):
    return trace.get("dimensions", {}).get(dim, {}).get("score", "—")


def _dim_evidence(trace, dim):
    ev = trace.get("evidence", {}).get(dim, {})
    if not ev:
        return "（无扣分项）"
    return "; ".join("%s: %s" % (k, v) for k, v in ev.items())


def _build_next_steps(trace, findings, sec_findings=None):
    steps = []
    sec_high = [f for f in (sec_findings or []) if f.get("severity") == "high"]
    if sec_high:
        steps.append("先处理 %d 条 high 级**安全**发现（第 4 节），例如 %s。" %
                     (len(sec_high), sec_high[0].get("rule_id")))
    sev_counts = {}
    for f in findings:
        sev_counts[f.get("severity", "low")] = sev_counts.get(f.get("severity", "low"), 0) + 1
    if sev_counts.get("high"):
        steps.append("优先处理 %d 条 high 级发现（见第 3 节），它们会阻断发布。" %
                     sev_counts["high"])
    elif not sec_high:
        steps.append("当前无 high 级阻断项，可进入优化/发布评估。")
    weakest = trace.get("weakest_dimension")
    if weakest:
        steps.append("针对最弱维度 %s 补强（详见第 2 节 TRACE 证据）。" % weakest)
    steps.append("如需自动优化，运行 optimize_apply.py --dry-run 预览改动，确认后再落盘。")
    return steps[:3]


def _parse_opt_report(path):
    """Return (applied, report_only, change_notes, diff_excerpt) from optimization-report.md."""
    applied, report_only, change_notes, diff_excerpt = "（未运行）", "（未运行）", "（无）", "（无）"
    if not path or not os.path.isfile(path):
        return applied, report_only, change_notes, diff_excerpt
    text = open(path, encoding="utf-8").read()
    m = re.search(r"## 已应用改动\n(.*?)(?:\n## |\Z)", text, re.S)
    if m:
        notes = [ln.strip("- ").strip() for ln in m.group(1).splitlines() if ln.strip().startswith("-")]
        change_notes = "\n  ".join(notes) if notes else "（无自动文本改动）"
    m = re.search(r"## 统一差异.*?\n```diff\n(.*?)```", text, re.S)
    if m:
        diff_excerpt = m.group(1).strip()[:1500]
    # applied / report_only are summarized in the header lines
    m = re.search(r"自动应用策略:\s*(.+)", text)
    if m:
        applied = m.group(1).strip()
    m = re.search(r"仅建议\(人工\):\s*(.+)", text)
    if m:
        report_only = m.group(1).strip()
    return applied, report_only, change_notes, diff_excerpt


def _resolve(expr, ctx):
    """Resolve a dotted expression like 'finding.severity' or 'score_T'."""
    expr = expr.strip()
    # fix the template typo eevidence -> evidence
    if expr.endswith(".eevidence"):
        expr = expr[:-len(".eevidence")] + ".evidence"
    parts = expr.split(".")
    val = ctx
    for p in parts:
        if isinstance(val, dict) and p in val:
            val = val[p]
        else:
            return "—"
    if val is None or val == "":
        return "—"
    if isinstance(val, list):
        return ", ".join(str(x) for x in val) if val else "—"
    return str(val)


def _render(template, ctx):
    # support one-level {% for item in list %}...{% endfor %}
    def repl_loop(m):
        item_var = m.group(1).strip()
        list_expr = m.group(2).strip()
        body = m.group(3)
        items = _resolve(list_expr, ctx)
        if not isinstance(items, list) or not items:
            return ""
        out = []
        for it in items:
            # build a child context: item_var -> it, plus dotted access
            child = dict(ctx)
            child[item_var] = it
            out.append(_render(body, child))
        return "".join(out)

    # find for-loops (non-greedy, no nesting supported)
    template = re.sub(
        r"{%\s*for\s+(\w+)\s+in\s+([\w.]+)\s*%}(.*?){%\s*endfor\s*%}",
        repl_loop, template, flags=re.S)
    # replace {{ expr }}
    template = re.sub(r"{{\s*([\w.]+)\s*}}", lambda m: _resolve(m.group(1), ctx), template)
    return template


def main():
    ap = argparse.ArgumentParser(description="Assemble Phase 5 REPORT.md from .skill-audit artifacts.")
    ap.add_argument("target", help="Skill directory or path to SKILL.md")
    ap.add_argument("--config", default=None, help="Path to config.json (used only for display)")
    ap.add_argument("--out", default=None, help="Output REPORT.md path")
    args = ap.parse_args()

    try:
        skill = C.load_skill(args.target)
        skill_dir = skill["dir"]
        audit = _load("audit.json", skill_dir)
        semantic = _load("semantic.json", skill_dir)
        trace = _load("trace.json", skill_dir)
        testplan = _load("testplan.json", skill_dir)
        opt_path = os.path.join(skill_dir, ".skill-audit", "optimization-report.md")

        findings = _merge_findings(audit, semantic)

        # skill identity
        fm = skill["frontmatter"]
        skill_name = fm.get("name") or os.path.basename(skill_dir.rstrip("/"))

        # test summary
        static_pass = static_total = cases_total = cases_executed = cases_manual = 0
        cases_heuristic = 0
        test_summary = "（未运行测试阶段）"
        if testplan:
            s = testplan.get("summary", {})
            static_pass = s.get("static_pass", 0)
            static_total = s.get("static_total", 0)
            cases_total = s.get("cases_total", 0)
            cases_executed = s.get("cases_executed", 0)
            cases_manual = s.get("cases_manual", 0)
            cases_heuristic = s.get("cases_heuristic", 0)
            eval_mode = testplan.get("eval_mode", "manual")
            if cases_manual:
                test_summary = "仍有 %d 条用例待人工/模型执行（边界与准确性需实跑）" % cases_manual
            elif eval_mode == "heuristic":
                test_summary = ("全部 %d 条用例已由零依赖启发式规则自动判定（含 %d 条静态检查）；"
                                "如需真实模型输出测试，可用 --model-config 升级" % (cases_executed, static_pass))
            else:
                test_summary = "全部用例已执行"

        # coverage: extract SEM-INFO sampling note from semantic.json (if any)
        coverage = "全文已扫描（无需采样）"
        if semantic:
            for f in semantic.get("semantic_findings", []):
                if f.get("rule_id") == "SEM-INFO":
                    ev = f.get("evidence", "")
                    if "分段采样" in ev:
                        coverage = ev.split("，已启用")[-1] if "已启用" in ev else ev
                    break

        applied, report_only, change_notes, diff_excerpt = _parse_opt_report(opt_path)

        # --- 安全审查（OWASP Agentic Skills） ---
        security = _load("security.json", skill_dir)
        sec_findings = (security or {}).get("findings", [])
        sec_summary = (security or {}).get("summary", {})
        if security is None:
            security_line = "（未运行安全扫描）"
        elif not sec_findings:
            security_line = "未命中已知高危模式（SEC-001~008）；这不等于安全，仅代表没撞上规则集"
        else:
            by_sev = sec_summary.get("by_severity", {})
            security_line = "命中 %d 条（high %d / medium %d / low %d）" % (
                len(sec_findings), by_sev.get("high", 0), by_sev.get("medium", 0), by_sev.get("low", 0))
        sec_ast = sec_summary.get("by_owasp", {})
        security_ast_line = ("、".join("%s×%d" % (k, v) for k, v in sorted(sec_ast.items()))
                             or "（无）")

        ctx = {
            "skill_name": skill_name,
            "skill_path": skill_dir,
            "scope": "—",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "config_path": args.config or "（默认配置）",
            "overall": trace.get("overall", "—") if trace else "—",
            "grade": trace.get("grade", "—") if trace else "—",
            "score_T": _dim_score(trace, "T") if trace else "—",
            "score_R": _dim_score(trace, "R") if trace else "—",
            "score_A": _dim_score(trace, "A") if trace else "—",
            "score_C": _dim_score(trace, "C") if trace else "—",
            "score_E": _dim_score(trace, "E") if trace else "—",
            "evidence_T": _dim_evidence(trace, "T") if trace else "—",
            "evidence_R": _dim_evidence(trace, "R") if trace else "—",
            "evidence_A": _dim_evidence(trace, "A") if trace else "—",
            "evidence_C": _dim_evidence(trace, "C") if trace else "—",
            "evidence_E": _dim_evidence(trace, "E") if trace else "—",
            "weakest_dimension": trace.get("weakest_dimension", "—") if trace else "—",
            "critical_gaps": ", ".join(trace.get("critical_gaps", [])) or "（无）" if trace else "—",
            "prior_overall": trace.get("prior_overall", "—") if trace else "—",
            "delta": trace.get("delta", "—") if trace else "—",
            "findings": findings,
            "security_line": security_line,
            "security_ast_line": security_ast_line,
            "security_findings": sec_findings,
            "static_pass": static_pass,
            "static_total": static_total,
            "cases_total": cases_total,
            "cases_executed": cases_executed,
            "cases_manual": cases_manual,
            "cases_heuristic": cases_heuristic,
            "test_summary": test_summary,
            "coverage": coverage,
            "applied_strategies": applied,
            "report_only_strategies": report_only,
            "change_notes": change_notes,
            "diff_excerpt": diff_excerpt,
            "next_steps": _build_next_steps(trace or {}, findings, sec_findings),
        }
        # flatten next_steps into next_step_1/2/3
        for i, step in enumerate(ctx["next_steps"][:3], 1):
            ctx["next_step_%d" % i] = step

        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "assets", "report_template.md")
        with open(template_path, encoding="utf-8") as f:
            template = f.read()
        report = _render(template, ctx)

        out_path = args.out or os.path.join(skill_dir, ".skill-audit", "REPORT.md")
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
    except Exception as e:
        code, message, next_step = C.humanize_error(e, "build_report")
        print("[%s] %s" % (code, message))
        if next_step:
            print("下一步: %s" % next_step)
        sys.exit(1)

    print("REPORT written to: %s" % out_path)
    print("Findings merged: %d | TRACE overall: %s" % (len(findings), ctx.get("overall")))


if __name__ == "__main__":
    main()
