#!/usr/bin/env python3
"""audit_skill.py — structural / prompt-quality / efficiency audit of a skill.

Usage:
  python3 audit_skill.py <target> [--json] [--config config.json]

Emits a list of findings (JSON when --json) to stdout. Also supports loading a
custom rules module via config.custom_rules_module.
"""
import os
import sys
import re
import json
import argparse
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C


def run_builtin(skill, cfg):
    rules = cfg.get("rules", {})
    th = cfg.get("thresholds", {})
    findings = []
    fm = skill["frontmatter"]
    body = skill["body"]
    raw = skill["raw"]
    files = set(skill["files"])
    skill_dir = skill["dir"]

    def add(rid, sev, cat, loc, ev, rec):
        en, severity = C.ref_enabled(rules, rid, sev)
        if not en:
            return
        findings.append(C.make_finding(rid, severity, cat, loc, ev, rec))

    # --- structure ---
    if not skill["fm_ok"]:
        add("STRUCT-001", "high", "structure", "SKILL.md", "frontmatter 缺失或无法解析",
            "在文件开头补 --- name / description / agent_created: true --- 头")
    if "name" not in fm:
        add("STRUCT-002", "high", "structure", "SKILL.md", "frontmatter 缺 name",
            "补充 name: <skill-id>")
    desc = fm.get("description", "")
    if not desc:
        add("STRUCT-003", "high", "structure", "SKILL.md", "frontmatter 缺 description",
            "补充 description，说明能力与 WHEN 触发场景")
    else:
        if not any(k in desc for k in ("当", "用于", "触发", "use", "when", "Use")):
            add("STRUCT-005", "medium", "structure", "SKILL.md:description",
                "description 未包含触发场景表述", "加入 WHEN 触发条件（何时使用该技能）")
        if desc.strip().lower().startswith(("you ", "你应该", "你应该", "use this")):
            add("STRUCT-006", "medium", "structure", "SKILL.md:description",
                "description 未用第三人称", "改为第三人称：'This skill should be used when...'")
    if fm.get("agent_created") is not True:
        add("STRUCT-004", "low", "structure", "SKILL.md", "缺少 agent_created: true",
            "加入 agent_created: true 以便后续可被修改")

    # referenced resource existence
    for ref in C.referenced_paths(body):
        if ref not in files:
            if ref.startswith("scripts/"):
                add("STRUCT-007", "high", "structure", "SKILL.md", "引用脚本不存在: %s" % ref,
                    "创建该文件或修正路径")
            elif ref.startswith("references/"):
                add("STRUCT-008", "high", "structure", "structure", "引用参考不存在: %s" % ref,
                    "创建该文件或修正路径")
            else:
                add("STRUCT-009", "medium", "structure", "SKILL.md", "引用资产不存在: %s" % ref,
                    "提供资产或修正路径")

    # directory structure
    has = lambda d: any(f.startswith(d + "/") or f == d for f in files)
    expected = []
    if "scripts/" in body:
        expected.append("scripts")
    if "references/" in body:
        expected.append("references")
    if "assets/" in body:
        expected.append("assets")
    for d in expected:
        if not has(d):
            add("STRUCT-010", "low", "structure", skill_dir, "声明使用 %s/ 但目录缺失" % d,
                "创建 %s/ 目录或移除相关声明" % d)

    # path safety (ascii)
    for f in files:
        if any(ord(ch) > 127 for ch in f.split("/")[-1]) or " " in f:
            add("STRUCT-011", "low", "structure", f, "路径含中文/空格: %s" % f,
                "改用 ASCII 无空格文件名")

    # imperative form (first non-empty body line after heading)
    lines = [l for l in body.splitlines() if l.strip() and not l.strip().startswith("#")]
    if lines:
        first = lines[0]
        if first.strip().lower().startswith(("你应该", "you should", "请", "please ")):
            add("STRUCT-012", "medium", "structure", "SKILL.md", "指令以第二人称开头: '%s'" % first[:40],
                "改为祈使/不定式（动词开头）")

    # --- prompt quality ---
    if "[TODO]" in raw or "[todo" in raw.lower():
        add("PROMPT-005", "high", "prompt", "SKILL.md", "存在未填占位 [TODO]",
            "补全占位内容或删除")
    low = desc.lower()
    if any(w in low for w in ("100%", "永远", "绝对", "always accurate", "never fail")):
        add("PROMPT-006", "medium", "prompt", "SKILL.md:description",
            "含绝对化/夸大表述", "弱化绝对化表述，改为可验证说法")
    # example coverage: fenced code or '例'/'example'
    if "```" not in body and "例" not in body and "example" not in body.lower():
        add("PROMPT-003", "medium", "prompt", "SKILL.md", "无示例/可执行片段",
            "增加至少 1 个关键场景示例")
    # deliverable clarity
    if "产出" not in body and "交付" not in body and "输出" not in body and "report" not in body.lower():
        add("PROMPT-007", "medium", "prompt", "SKILL.md", "未说明产出物/成功判据",
            "明确技能的最终交付物")
    wc = len(body.split())
    if wc > th.get("max_skill_words", 5000):
        add("PROMPT-004", "low", "prompt", "SKILL.md", "正文 %d 词，超过 %d" % (wc, th["max_skill_words"]),
            "将细节外置到 references/，SKILL.md 仅保留流程")

    # --- efficiency ---
    blines = body.splitlines()
    i = 0
    seen_block = {}
    while i < len(blines):
        # find a run of >=3 identical consecutive non-empty lines
        j = i
        while j + 1 < len(blines) and blines[j + 1].strip() == blines[i].strip() and blines[i].strip():
            j += 1
        if j - i >= 2:
            add("EFF-001", "medium", "efficiency", "SKILL.md:%d" % (i + 1),
                "连续重复文本块（%d 行）: '%s'" % (j - i + 1, blines[i].strip()[:40]),
                "删除重复，仅保留一份")
            i = j + 1
        else:
            i += 1
    # dead reference to anchors
    anchors = set(re_anchor(body))
    for m in re.findall(r"\]\(#([A-Za-z0-9\-]+)\)", body):
        if m not in anchors:
            add("EFF-003", "low", "efficiency", "SKILL.md", "死锚点链接: #%s" % m,
                "修正或移除该锚点")

    # doc/code flag consistency
    findings += check_doc_arg_consistency(skill, rules)

    return findings


def re_anchor(body):
    return re.findall(r"^#{1,6}\s+.*?(?:\n|$)", body, re.M)


def parse_declared_flags(path):
    """Return set of --flags declared via add_argument in a python script.

    Returns None if the file is unreadable (cannot verify); an empty set if the
    script does not use argparse (cannot verify either, so the caller skips).
    """
    try:
        src = open(path, encoding="utf-8").read()
    except Exception:
        return None
    if "argparse" not in src:
        return set()
    flags = set()
    for m in re.finditer(r"add_argument\(\s*", src):
        window = src[m.end():m.end() + 240]
        for tok in re.findall(r'["\'](--[A-Za-z][\w-]*)["\']', window):
            flags.add(tok)
    return flags


def check_doc_arg_consistency(skill, rules):
    """STRUCT-013: CLI flags demonstrated in SKILL.md must be real.

    Scans SKILL.md command examples for `scripts/X.py ... --flag` and verifies
    each flag is declared via add_argument in that script. Catches the classic
    doc/code drift where a SKILL.md documents a flag the script never implemented
    (the very bug found during skill-auditor's own self-audit).
    """
    findings = []
    body = skill["body"]
    skill_dir = skill["dir"]
    for m in re.finditer(r"(scripts/[A-Za-z0-9_.\-]+\.py)", body):
        script_rel = m.group(1)
        ls = body.rfind("\n", 0, m.start()) + 1
        le = body.find("\n", m.end())
        if le == -1:
            le = len(body)
        line = body[ls:le]
        line_no = body[:ls].count("\n") + 1
        flags_in_doc = re.findall(r"(--[A-Za-z][\w-]*)", line)
        if not flags_in_doc:
            continue
        script_abs = os.path.join(skill_dir, script_rel)
        if not os.path.isfile(script_abs):
            continue  # STRUCT-007 already reports the missing script
        declared = parse_declared_flags(script_abs)
        if not declared:
            continue  # unreadable or no argparse -> cannot verify, skip
        for fl in flags_in_doc:
            if fl in declared:
                continue
            en, sev = C.ref_enabled(rules, "STRUCT-013", "high")
            if not en:
                continue
            findings.append(C.make_finding(
                "STRUCT-013", sev, "structure",
                "SKILL.md:%d (%s %s)" % (line_no, script_rel, fl),
                "SKILL.md 演示了参数 %s，但 %s 未通过 add_argument 声明" % (fl, script_rel),
                "在 %s 中补 add_argument('%s', ...) 或修正 SKILL.md 示例命令" % (script_rel, fl)))
    return findings


def run_custom(skill, cfg):
    mod = cfg.get("custom_rules_module")
    if not mod or not os.path.isfile(mod):
        return []
    spec = importlib.util.spec_from_file_location("custom_rules", mod)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if not hasattr(m, "check"):
        return []
    return m.check(skill, {"config": cfg, "thresholds": cfg.get("thresholds", {})}) or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    cfg = C.read_config(args.config)
    skill = C.load_skill(args.target)
    findings = run_builtin(skill, cfg)
    findings += run_custom(skill, cfg)

    # de-dup by (rule_id, location)
    seen = set()
    uniq = []
    for f in findings:
        key = (f["rule_id"], f["location"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)

    if args.json:
        print(json.dumps({"target": skill["dir"], "count": len(uniq), "findings": uniq},
                         ensure_ascii=False, indent=2))
    else:
        print("Audit findings for %s (%d):" % (skill["dir"], len(uniq)))
        for f in uniq:
            print("  [%s] %s @ %s — %s" % (f["severity"], f["rule_id"], f["location"], f["evidence"]))


if __name__ == "__main__":
    main()
