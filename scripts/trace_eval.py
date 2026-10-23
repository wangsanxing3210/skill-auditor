#!/usr/bin/env python3
"""trace_eval.py — SkillHub TRACE 5-dimension evaluation.

Scores a skill on Trust / Reliability / Adaptability / Convention / Effectiveness.
Self-contained: computes metrics directly from the skill, and upgrades severity using
audit/semantic/testplan artifacts in <target>/.skill-audit/ when present.

Usage:
  python3 trace_eval.py <target> [--json] [--config config.json] [--prior trace.json]
"""
import os
import sys
import re
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C

SECRET_RE = re.compile(r"(api[_-]?key|secret|token|password|passwd|sk-[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{8,}|"
                       r"client[_-]?secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{6,}", re.I)
DESTRUCTIVE = ["删除", "外发", "付费", "rm -rf", "delete", "remove", "send", "publish"]
CAUTION = ["确认", "警示", "谨慎", "警告", "warning", "confirm", "careful", "风险提示"]
EXAGG = ["100%", "永远", "绝对", "always accurate", "never fail", "100 percent"]
# 教材/禁止语境：这些行在讲"不要这么写"，不应按夸大承诺扣分
NEG_CONTEXT = ("反模式", "反例", "错误示范", "不要", "禁止", "避免", "示例",
               "anti-pattern", "avoid", "wrong", "bad example", "❌")
PRIVACY = ["个人文件", "Desktop", "隐私", "personal file", "home directory"]


def m_pass(): return 1.0
def m_part(): return 0.5
def m_fail(): return 0.0


def m_near(present, explain):
    """A metric earns full only when concrete structural evidence exists; partial
    when the topic is mentioned but without actionable evidence."""
    if present:
        return m_pass()
    # 'explain' = whether the skill at least acknowledges the concern in text.
    return m_part() if explain else m_fail()


def load_artifacts(skill_dir):
    art = {}
    d = os.path.join(skill_dir, ".skill-audit")
    for name, key in (("audit.json", "audit"), ("semantic.json", "semantic"), ("testplan.json", "test")):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            try:
                art[key] = json.load(open(p, encoding="utf-8"))
            except Exception:
                pass
    return art


def metrics_T(skill, body, art):
    fm = skill["frontmatter"]
    # T1 secrets
    if SECRET_RE.search(body):
        t1 = m_fail()
    else:
        t1 = m_pass()
    # T2 side-effect caution
    has_d = any(w.lower() in body.lower() for w in DESTRUCTIVE)
    has_c = any(w.lower() in body.lower() for w in CAUTION)
    t2 = m_pass() if (not has_d or has_c) else m_part()
    # T3 exaggeration: skip code fences and inline code so quoted examples
    # (e.g. anti-pattern tables that cite "100% 准确" as a bad example) don't
    # trigger a false positive. Also exempt technical-usage contexts where the
    # keyword has a non-exaggerated meaning (e.g. "绝对路径" = absolute path),
    # quoted citations, and lines that are explicitly teaching what NOT to do.
    body_no_code = C.strip_code_fences(body)
    bl_raw = body_no_code.lower()
    hits = []
    for line in body_no_code.splitlines():
        low = line.lower()
        if any(m in low for m in NEG_CONTEXT):
            continue                      # 反模式 / 禁止 / avoid …
        clean = C.strip_quoted_examples(line).lower()
        hits += [w for w in EXAGG if w.lower() in clean]
    # technical exemptions: these patterns are not exaggerations
    # "绝对路径/绝对定位" = absolute path/positioning; "绝对化承诺" = the *name* of the
    # anti-pattern being described, not a promise made by the skill itself.
    tech_context = ("绝对路径" in bl_raw or "绝对定位" in bl_raw or "absolute path" in bl_raw
                    or "绝对化" in bl_raw)
    effective_hits = [w for w in hits if not (w in ("绝对", "always") and tech_context)]
    t3 = m_pass() if not effective_hits else m_fail()
    # T4 privacy note
    has_p = any(w.lower() in body.lower() for w in PRIVACY)
    t4 = m_pass() if (not has_p or has_c) else m_part()
    # T5 cited sources: a real http(s) link OR a references/<file> reference (not just the word "参考")
    has_link = "http://" in body or "https://" in body
    has_ref = bool(re.search(r"references/[A-Za-z0-9_.\-/]+\.[A-Za-z0-9]+", body))
    t5 = m_pass() if (has_link or has_ref) else m_part()
    return {"T1": t1, "T2": t2, "T3": t3, "T4": t4, "T5": t5}


def metrics_R(skill, body, art):
    fm = skill["frontmatter"]
    r1 = m_pass() if (skill["fm_ok"] and "name" in fm and "description" in fm) else m_fail()
    # R2 referenced resources exist
    missing = [r for r in C.referenced_paths(body) if r not in set(skill["files"])]
    if missing:
        r2 = m_fail()
    elif C.referenced_paths(body):
        r2 = m_pass()
    else:
        r2 = m_part()
    # R3 error handling: must contain a real error-handling instruction (try/except, "if fails",
    # "on error do X", "fallback to Y"), not just the bare word "错误"
    has_err_directive = bool(re.search(
        r"(try[ :]|except|if .*fail|on error|失败[时则]|出错[时则]|捕获|fallback ?to|回退[到至]|"
        r"容错|友好(地)?报错|友好错误|异常处理|捕获异常|try/except)", body, re.I))
    r3 = m_near(has_err_directive, any(w in body for w in ["错误", "失败", "异常"]))
    r4 = m_pass() if ("```" in body or "示例" in body or "example" in body.lower()) else m_fail()
    # R7 oversized-skill handling: explicit size limit / guard / degraded mode (not just "大文件" mention)
    has_limit = bool(re.search(r"(\b5 ?k\b|> ?\d{3,}|词|size|大小|限制|字节|MB|GB)", body)) and \
                any(w in body for w in ["限制", "阈值", "超限", "超过", "guard", "降级", "资源保护", "大小限制"])
    r7 = m_near(has_limit, any(w in body for w in ["大文件", "超大", "限制", "降级"]))
    # R5 boundary handling: named boundary scenarios (empty/oversized/missing) OR skill_tester
    # actually produced boundary cases in its test plan
    named = bool(re.search(r"(空输入|空\b|empty input|超大(输入|文件|skill)?|缺失(参数|输入|文件)?|"
                           r"boundary|缺失参数|oversized|超长|无输入|异常输入)", body))
    test_cases = (art.get("test") or {}).get("cases", [])
    has_boundary_case = any("boundary" in str(c.get("type", "")).lower() for c in test_cases) if test_cases else False
    r5 = m_pass() if (named or has_boundary_case) else m_part()
    # R6 conflicts from semantic artifact
    sem = (art.get("semantic") or {}).get("semantic_findings", [])
    has_conflict = any(f.get("rule_id") == "SEM-004" for f in sem)
    r6 = m_fail() if has_conflict else m_pass()
    return {"R1": r1, "R2": r2, "R3": r3, "R4": r4, "R5": r5, "R6": r6, "R7": r7}


def metrics_A(skill, body, art):
    # A1 config support: explicit --config flag or a config.json file reference (not just "配置")
    a1 = m_pass() if ("--config" in body or "config.json" in body or "config.example.json" in body) else m_fail()
    # A2 extensibility hook: a real custom-module entry point, not just the word "扩展"
    a2 = m_pass() if ("custom_rules_module" in body or "custom_strategies_module" in body) else m_fail()
    # A3 variant scenarios: >=2 workflow sub-headings
    heads = re.findall(r"^##\s+.*$", body, re.M)
    a3 = m_pass() if len(heads) >= 3 else m_part()
    wc = len(body.split())
    a4 = m_pass() if ("references/" in body and wc <= 5000) else m_part()
    return {"A1": a1, "A2": a2, "A3": a3, "A4": a4}


def metrics_C(skill, body, art):
    fm = skill["frontmatter"]
    c1 = m_pass() if ("name" in fm and "description" in fm and fm.get("agent_created") is True) else m_part()
    desc = fm.get("description", "")
    c2 = m_pass() if any(k in desc for k in ["当", "用于", "触发", "use", "when", "Use"]) else m_part()
    lines = [l for l in body.splitlines() if l.strip() and not l.strip().startswith("#")]
    first = lines[0] if lines else ""
    c3 = m_pass() if not first.strip().lower().startswith(("你应该", "you should", "请", "please ")) else m_part()
    has_dir = lambda d: any(f.startswith(d + "/") or f == d for f in skill["files"])
    need = [d for d in ("scripts", "references", "assets") if d + "/" in body]
    c4 = m_pass() if all(has_dir(d) for d in need) else m_part()
    c5 = m_pass() if not any((ord(ch) > 127 or " " in f) for f in skill["files"] for ch in f.split("/")[-1]) else m_part()
    wc = len(body.split())
    c6 = m_pass() if (wc <= 5000 or "references/" in body) else m_part()
    return {"C1": c1, "C2": c2, "C3": c3, "C4": c4, "C5": c5, "C6": c6}


def metrics_E(skill, body, art):
    desc = skill["frontmatter"].get("description", "")
    cap_sec = ""
    m = re.search(r"##\s*(Overview|When To Use|概述|何时使用).*?(?=\n##\s|\Z)", body, re.S | re.I)
    if m:
        cap_sec = m.group(0)
    dt = C.tokenize_weak(desc) if hasattr(C, "tokenize_weak") else set(desc.lower().split())
    ct = C.tokenize_weak(cap_sec) if hasattr(C, "tokenize_weak") else set(cap_sec.lower().split())
    ov = (len(dt & ct) / len(dt | ct)) if (dt | ct) else 0
    e1 = m_pass() if ov >= 0.1 or desc else m_part()
    e2 = m_pass() if ("##" in body and any(w in body for w in ["运行", "执行", "步骤", "Run", "执行以下", "使用以下"]) and "```" in body) else m_part()
    e3 = m_pass() if ("##" in body and ("工作流" in body or "Workflow" in body or "示例" in body)) else m_part()
    # E4 measurable deliverable: a dedicated Output/Deliverables section, or a verbatim
    # list of concrete output files/artifacts (not merely the word "报告")
    has_output_section = bool(re.search(r"^##+\s*(Output|Deliverables|产出|交付|交付物|输出)", body, re.M | re.I))
    has_artifact_list = bool(re.search(r"(audit\.json|trace\.json|REPORT\.md|optimization-report\.md|testplan\.json|\.skill-audit/)", body))
    e4 = m_near(has_output_section or has_artifact_list, any(w in body for w in ["产出", "交付", "报告", "report", "REPORT"]))
    return {"E1": e1, "E2": e2, "E3": e3, "E4": e4}


DIM_METRICS = {
    "T": metrics_T, "R": metrics_R, "A": metrics_A, "C": metrics_C, "E": metrics_E,
}


def dim_score(metrics):
    vals = list(metrics.values())
    return round(100.0 * sum(vals) / len(vals), 1)


def grade(overall):
    if overall >= 90: return "A"
    if overall >= 75: return "B"
    if overall >= 60: return "C"
    return "D"


def _emit(code, message, next_step, json_mode):
    if json_mode:
        print(json.dumps({"ok": False, "error": {"code": code, "message": message, "next_step": next_step}},
                         ensure_ascii=False, indent=2))
    else:
        print("[%s] %s" % (code, message))
        if next_step:
            print("下一步: %s" % next_step)


def main():
    ap = argparse.ArgumentParser(
        description="SkillHub TRACE 5-dimension evaluation.")
    ap.add_argument("target", help="Skill directory or path to SKILL.md")
    ap.add_argument("--json", action="store_true", help="Output JSON")
    ap.add_argument("--config", default=None, help="Path to config.json")
    ap.add_argument("--prior", default=None, help="Prior trace.json for delta comparison")
    args = ap.parse_args()

    try:
        cfg = C.read_config(args.config)
        weights = cfg.get("weights", {})
        skill = C.load_skill(args.target)
        body = skill["body"]
        art = load_artifacts(skill["dir"])

        dims = {}
        evidence = {}
        for dim, fn in DIM_METRICS.items():
            ms = fn(skill, body, art)
            dims[dim] = {"score": dim_score(ms), "metrics": {k: round(v, 2) for k, v in ms.items()}}
            for k, v in ms.items():
                if v < 1.0:
                    evidence.setdefault(dim, {})[k] = "metric score %.2f" % v

        overall = 0.0
        for dim in dims:
            w = weights.get(dim, 0.2)
            overall += dims[dim]["score"] * w
        overall = round(overall, 1)

        weakest = min(dims, key=lambda d: dims[d]["score"])
        critical = [d for d in dims if dims[d]["score"] < 50]
        g = grade(overall)

        result = {
            "ok": True,
            "overall": overall, "grade": g, "dimensions": dims,
            "weakest_dimension": weakest, "critical_gaps": critical,
            "evidence": evidence,
        }

        prior = None
        if args.prior and os.path.isfile(args.prior):
            try:
                prior = json.load(open(args.prior, encoding="utf-8"))
            except Exception:
                prior = None
        if prior:
            result["delta"] = round(overall - prior.get("overall", 0), 1)
            result["prior_overall"] = prior.get("overall")
    except Exception as e:
        code, message, next_step = C.humanize_error(e, "trace_eval")
        _emit(code, message, next_step, args.json)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("TRACE scorecard for %s" % skill["dir"])
        for d in "TRACE":
            print("  %s: %s" % (d, dims[d]["score"]))
        print("  Overall: %s (grade %s), weakest=%s" % (overall, g, weakest))
        if critical:
            print("  CRITICAL gaps: %s" % ", ".join(critical))


if __name__ == "__main__":
    main()
