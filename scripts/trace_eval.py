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
PRIVACY = ["个人文件", "Desktop", "隐私", "personal file", "home directory"]


def m_pass(): return 1.0
def m_part(): return 0.5
def m_fail(): return 0.0


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
    # T3 exaggeration
    t3 = m_fail() if any(w.lower() in body.lower() for w in EXAGG) else m_pass()
    # T4 privacy note
    has_p = any(w.lower() in body.lower() for w in PRIVACY)
    t4 = m_pass() if (not has_p or has_c) else m_part()
    # T5 cited sources
    t5 = m_pass() if ("http" in body or "参考" in body or "references/" in body) else m_part()
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
    r3 = m_pass() if any(w in body for w in ["错误", "失败", "回退", "异常处理", "error", "fallback", "容错", "友好错误"]) else m_part()
    r4 = m_pass() if ("```" in body or "示例" in body or "example" in body.lower()) else m_fail()
    # R7 oversized-skill handling: body mentions limits, guards, or degraded mode
    r7 = m_pass() if any(w in body for w in ["大文件", "超大", "限制", "降级", "guard", "大小限制", "资源保护"]) else m_part()
    r5 = m_pass() if any(w in body for w in ["边界", "空输入", "超大", "缺失", "boundary", "empty input", "缺失参数"]) else m_fail()
    # R6 conflicts from semantic artifact
    sem = (art.get("semantic") or {}).get("semantic_findings", [])
    has_conflict = any(f.get("rule_id") == "SEM-004" for f in sem)
    r6 = m_fail() if has_conflict else m_pass()
    return {"R1": r1, "R2": r2, "R3": r3, "R4": r4, "R5": r5, "R6": r6, "R7": r7}


def metrics_A(skill, body, art):
    a1 = m_pass() if any(w in body for w in ["config", "参数", "--config", "可配置", "配置"]) else m_fail()
    a2 = m_pass() if any(w in body for w in ["自定义模块", "custom_rules_module", "扩展", "extensible", "可扩展"]) else m_fail()
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
    e2 = m_pass() if any(w in body for w in ["运行", "执行", "步骤", "Run", "执行以下", "使用以下"]) else m_part()
    e3 = m_pass() if ("##" in body and ("工作流" in body or "Workflow" in body or "示例" in body)) else m_part()
    e4 = m_pass() if any(w in body for w in ["产出", "交付", "报告", "交付物", "report", "REPORT"]) else m_part()
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
