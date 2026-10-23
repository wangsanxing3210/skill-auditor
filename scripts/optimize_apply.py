#!/usr/bin/env python3
"""optimize_apply.py — apply safe optimizations and emit before/after diff.

Maps audit/semantic findings to optimization strategies and applies *reversible*
transformations by default. Aggressive strategies run only with --aggressive AND
config.strategies.allow_aggressive. Always writes a unified diff + report so changes
are reviewable.

Usage:
  python3 optimize_apply.py <target> --findings findings.json [--dry-run]
         [--aggressive] [--out report.md] [--config config.json]
"""
import os
import sys
import re
import json
import argparse
import difflib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C

STRATEGY_TABLE = {
    "OPT-FRONTMATTER": {"rules": ["STRUCT-001", "STRUCT-002", "STRUCT-003", "STRUCT-004"], "risk": "safe"},
    "OPT-TRIGGER": {"rules": ["PROMPT-001"], "risk": "safe"},
    "OPT-DEDUP-BLOCK": {"rules": ["EFF-001"], "risk": "safe"},
    "OPT-SEM-DEDUP": {"rules": ["SEM-001", "SEM-002"], "risk": "safe"},
    "OPT-TERM-UNIFY": {"rules": ["SEM-003"], "risk": "safe"},
    "OPT-DEADREF-FIX": {"rules": ["STRUCT-007", "STRUCT-008", "STRUCT-009", "EFF-003"], "risk": "safe"},
    "OPT-PHRASE-NORMALIZE": {"rules": ["PROMPT-006"], "risk": "safe"},
    "OPT-REF-EXTERNALIZE": {"rules": ["EFF-002"], "risk": "safe"},
    "OPT-REWRITE-CONFLICT": {"rules": ["SEM-004"], "risk": "aggressive"},
    "OPT-RESTRUCTURE": {"rules": ["PROMPT-004", "EFF-005"], "risk": "aggressive"},
}
RULE_TO_STRATEGY = {}
for sid, info in STRATEGY_TABLE.items():
    for r in info["rules"]:
        RULE_TO_STRATEGY[r] = sid

# Framework-neutral by default. Add product-specific clusters via config.term_clusters.
DEFAULT_TERM_CLUSTERS = {
    "Skill": ["Skill", "skill", "技能", "这个技能"],
    "frontmatter": ["frontmatter", "前置元数据", "YAML头", "yaml头"],
}
PHRASE_MAP = [(r"100\s*%", "尽可能高"), (r"永远", "通常"), (r"绝对", "尽量")]


def build_term_suggestions(raw, clusters=None):
    """Language-aware term unification: only unify within the same script, and never
    cross languages (so '技能' is never rewritten to 'skill'). `clusters` overrides the
    default set (config.term_clusters) so product-specific mappings stay opt-in."""
    sug = {}
    for _canon, variants in (clusters or DEFAULT_TERM_CLUSTERS).items():
        groups = {"ascii": [], "cjk": []}
        for v in variants:
            if re.search(r"[一-鿿]", v):
                groups["cjk"].append(v)
            else:
                groups["ascii"].append(v)
        for grp in groups.values():
            if len(grp) < 2:
                continue
            best = max(grp, key=lambda v: raw.count(v))
            if raw.count(best) == 0:
                continue
            for v in grp:
                if v != best and raw.count(v) > 0:
                    sug[v] = best
    return sug


def safe_replace(text, variant, canon):
    """Replace variant with canon. ASCII: word-boundary safe (won't touch
    'skill-inspector' or 'SKILL.md'). Protection: never rewrite inside a Markdown
    heading line, and never lowercase a word that begins a sentence/line (so
    '# Skill Auditor' and 'A Skill that…' stay capitalized). CJK: substring replace."""
    if re.search(r"[a-z]", variant):
        pat = r"(?<![\w./-])" + re.escape(variant) + r"(?![\w./-])"
        changed = 0
        skipped = 0
        lowers = bool(variant[:1].isupper() and canon[:1].islower())

        def repl(m):
            nonlocal changed, skipped
            s = m.start()
            # 1) heading protection: the line this match lives on starts with '#'
            ls = text.rfind("\n", 0, s) + 1
            if text[ls:ls + 1] == "#":
                skipped += 1
                return m.group(0)
            # 2) sentence/line-initial protection: don't lowercase a capitalized first word
            if lowers:
                prev = text[s - 1] if s > 0 else ""
                prev2 = text[s - 2] if s > 1 else ""
                is_initial = (s == 0) or (prev in ".!?。！？\n") or \
                             (prev in " \t" and prev2 in ".!?。！？\n")
                # line-initial: nothing before the match except bullet/quote/number markers
                if not is_initial:
                    lead = text[ls:s]
                    lead_core = re.sub(r"^[\s>\*\+\-]+", "", lead)
                    lead_core = re.sub(r"^\d+\.\s*", "", lead_core)
                    is_initial = (lead_core.strip() == "")
                if is_initial:
                    skipped += 1
                    return m.group(0)
            changed += 1
            return canon

        new = re.sub(pat, repl, text, flags=re.I)
        return new, changed, skipped
    cnt = text.count(variant)
    if cnt:
        return text.replace(variant, canon), cnt, 0
    return text, 0, 0


def strategies_for(findings, config, aggressive):
    allow_agg = config.get("strategies", {}).get("allow_aggressive", False)
    want = set()
    for f in findings:
        sid = RULE_TO_STRATEGY.get(f["rule_id"])
        if not sid:
            continue
        scfg = config.get("strategies", {}).get(sid, {})
        if scfg.get("enabled") is False:
            continue
        risk = STRATEGY_TABLE[sid]["risk"]
        if risk == "safe":
            want.add(sid)
        elif aggressive and allow_agg:
            want.add(sid)
    return want


def apply_frontmatter(raw, skill_dir):
    fm, body, ok = C.parse_frontmatter(raw)
    changed = False
    notes = []
    if not ok:
        fm = {}
    if "name" not in fm or not fm.get("name"):
        fm["name"] = os.path.basename(skill_dir.rstrip("/"))
        changed = True
        notes.append("补全 name: %s" % fm["name"])
    if "description" not in fm or not str(fm.get("description")).strip():
        fm["description"] = "[请补全：说明该技能能力与 WHEN 触发场景]"
        changed = True
        notes.append("补全 description 占位")
    if fm.get("agent_created") is not True:
        fm["agent_created"] = True
        changed = True
        notes.append("补全 agent_created: true")
    if not changed:
        return raw, notes
    lines = ["---"]
    for k, v in fm.items():
        lines.append("%s: %s" % (k, "true" if v is True else ("false" if v is False else v)))
    lines.append("---")
    return "\n".join(lines) + "\n" + body, notes


def _extract_capability_phrases(body):
    """Pull likely capability verbs/nouns from the skill body for trigger-word hints."""
    # Look at the first real paragraph after frontmatter
    cap = body.strip().split("\n\n")[0] if body.strip() else ""
    # Extract short verb+noun or noun chunks
    cands = []
    # Chinese: 2–5 char chunks around action verbs
    for m in re.finditer(r"(?:审查|评测|测试|优化|生成|检查|分析|帮助|辅助|自动)[\u4e00-\u9fa5A-Za-z0-9_\-/]{1,12}", cap):
        cands.append(m.group(0))
    # English: verb + noun phrases
    for m in re.finditer(r"\b(audit|review|test|optimize|generate|check|analyze|help|assist|auto)[\w\-/ ]{1,20}", cap, re.I):
        cands.append(m.group(0).strip())
    return list(dict.fromkeys(c))[:6] if (c := cands) else []


def apply_trigger_words(raw):
    """When PROMPT-001 fires (no explicit triggers), insert a trigger-word quick-reference
    section right after the frontmatter. Uses description + capability text to seed hints."""
    fm, body, ok = C.parse_frontmatter(raw)
    desc = str(fm.get("description", "")).strip()
    seed = desc or ""
    if len(seed) > 80:
        seed = seed[:80] + "..."
    hints = _extract_capability_phrases(body)
    if seed and seed not in hints:
        hints.insert(0, seed)
    if not hints:
        hints = ["<请根据技能能力补充 3–5 条典型用户说法>"]
    lines = [
        "",
        "## 触发词速查卡",
        "",
        "以下说法可以直接唤起本技能：",
        "",
    ]
    for h in hints[:5]:
        lines.append("- %s" % h)
    lines.append("- 帮我 %s" % hints[0])
    lines.append("- 请你对这个 skill 做 %s" % (hints[0] if len(hints) == 1 else hints[1] if len(hints) > 1 else "审查"))
    lines.append("")
    block = "\n".join(lines)
    if ok:
        # Insert right after the frontmatter closing '---'.
        # raw starts with '---\n...\n---\n<body>'. Find the second '---'.
        first = raw.find("---")
        second = raw.find("---", first + 1)
        insert_at = raw.find("\n", second) + 1 if second != -1 else len(raw)
        new_raw = raw[:insert_at] + block + raw[insert_at:]
    else:
        new_raw = block.lstrip("\n") + raw
    return new_raw, ["自动补全「触发词速查卡」（基于 description + 能力描述生成，请人工审校）"]


def apply_dedup(raw):
    lines = raw.splitlines()
    out = []
    notes = []
    i = 0
    removed = 0
    while i < len(lines):
        j = i
        while j + 1 < len(lines) and lines[j + 1].strip() == lines[i].strip() and lines[i].strip():
            j += 1
        if j - i >= 1:  # run of >=2 identical -> collapse to 1
            removed += (j - i)
            out.append(lines[i])
            i = j + 1
        else:
            out.append(lines[i])
            i += 1
    if removed:
        notes.append("移除 %d 行连续重复文本" % removed)
    return "\n".join(out) + ("\n" if raw.endswith("\n") else ""), notes


def apply_term_unify(raw, suggestions):
    text = raw
    notes = []
    for variant, canon in suggestions.items():
        if not variant or variant == canon:
            continue
        new, cnt, skipped = safe_replace(text, variant, canon)
        text = new
        if cnt:
            note = "术语 '%s' → '%s' (%d 处)" % (variant, canon, cnt)
            if skipped:
                note += "（跳过 %d 处标题/句首大写）" % skipped
            notes.append(note)
    return text, notes


def apply_phrase_normalize(raw):
    text = raw
    notes = []
    for pat, rep in PHRASE_MAP:
        cnt = len(re.findall(pat, text))
        if cnt:
            text = re.sub(pat, rep, text)
            notes.append("弱化绝对化表述 %s → %s (%d 处)" % (pat, rep, cnt))
    return text, notes


def _emit(code, message, next_step, json_mode):
    if json_mode:
        print(json.dumps({"ok": False, "error": {"code": code, "message": message, "next_step": next_step}},
                         ensure_ascii=False, indent=2))
    else:
        print("[%s] %s" % (code, message))
        if next_step:
            print("下一步: %s" % next_step)


def main():
    ap = argparse.ArgumentParser(description="Apply safe optimizations and emit before/after diff.")
    ap.add_argument("target", help="Skill directory or path to SKILL.md")
    ap.add_argument("--findings", required=True, help="Path to findings JSON")
    ap.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    ap.add_argument("--aggressive", action="store_true", help="Allow higher-risk strategies")
    ap.add_argument("--out", default=None, help="Report output path")
    ap.add_argument("--config", default=None, help="Path to config.json")
    ap.add_argument("--json", action="store_true", help="Output JSON summary")
    args = ap.parse_args()

    try:
        cfg = C.read_config(args.config)
        skill = C.load_skill(args.target)
        findings = C.load_findings(args.findings)

        # Build term-unification suggestions (language-aware, identifier-safe).
        # We recompute here rather than trusting semantic.json to avoid cross-language
        # rewrites (e.g. '技能' -> 'skill').
        term_clusters = cfg.get("term_clusters", DEFAULT_TERM_CLUSTERS)
        suggestions = build_term_suggestions(skill["raw"], term_clusters)

        want = strategies_for(findings, cfg, args.aggressive)

        applied = []
        new_text = skill["raw"]
        notes_all = []
        report_only = []

        if "OPT-FRONTMATTER" in want:
            new_text, n = apply_frontmatter(new_text, skill["dir"])
            if n:
                applied.append("OPT-FRONTMATTER"); notes_all += n
        if "OPT-TRIGGER" in want:
            new_text, n = apply_trigger_words(new_text)
            if n:
                applied.append("OPT-TRIGGER"); notes_all += n
        if "OPT-DEDUP-BLOCK" in want:
            new_text, n = apply_dedup(new_text)
            if n:
                applied.append("OPT-DEDUP-BLOCK"); notes_all += n
        if "OPT-SEM-DEDUP" in want:
            # collapse repeated/near-duplicate lines (covers SEM-001/SEM-002 repeated blocks)
            new_text, n = apply_dedup(new_text)
            if n:
                applied.append("OPT-SEM-DEDUP"); notes_all += n
        if "OPT-TERM-UNIFY" in want:
            new_text, n = apply_term_unify(new_text, suggestions)
            if n:
                applied.append("OPT-TERM-UNIFY"); notes_all += n
        if "OPT-PHRASE-NORMALIZE" in want:
            new_text, n = apply_phrase_normalize(new_text)
            if n:
                applied.append("OPT-PHRASE-NORMALIZE"); notes_all += n
        for sid in ("OPT-DEADREF-FIX", "OPT-REWRITE-CONFLICT", "OPT-RESTRUCTURE", "OPT-REF-EXTERNALIZE"):
            if sid in want:
                report_only.append(sid)

        if args.dry_run:
            result = {
                "ok": True, "dry_run": True,
                "would_apply": applied, "report_only": report_only, "notes": notes_all,
            }
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print("DRY-RUN — would apply: %s" % (applied + report_only))
                for n in notes_all:
                    print("  • " + n)
                print("--- unified diff (first 60 lines) ---")
                diff = difflib.unified_diff(skill["raw"].splitlines(), new_text.splitlines(),
                                            "before", "after", lineterm="")
                for i, line in enumerate(diff):
                    if i >= 60:
                        print("  ... (truncated)")
                        break
                    print(line)
            return

        # write back with backup
        backup = skill["skill_md"] + ".bak"
        try:
            with open(backup, "w", encoding="utf-8") as f:
                f.write(skill["raw"])
            with open(skill["skill_md"], "w", encoding="utf-8") as f:
                f.write(new_text)
        except OSError as e:
            raise C.GuardError("E_WRITE", "写入优化结果失败: %s" % e,
                               "检查目标目录写权限，或改用 --dry-run 仅预览") from e

        diff = list(difflib.unified_diff(skill["raw"].splitlines(), new_text.splitlines(),
                                         "before/SKILL.md", "after/SKILL.md", lineterm=""))
        report = build_report(skill["dir"], applied, report_only, notes_all, diff, findings)
        out_path = args.out or os.path.join(skill["dir"], ".skill-audit", "optimization-report.md")
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
    except Exception as e:
        code, message, next_step = C.humanize_error(e, "optimize_apply")
        _emit(code, message, next_step, args.json)
        sys.exit(1)

    if args.json:
        print(json.dumps({"ok": True, "report": out_path, "applied": applied, "report_only": report_only},
                         ensure_ascii=False, indent=2))
    else:
        print("Optimization report written to: %s" % out_path)
        print("Applied: %s" % (applied or ["(none)"]))
        print("Report-only (manual): %s" % (report_only or ["(none)"]))


def build_report(target, applied, report_only, notes, diff, findings):
    sev_order = {"high": 0, "medium": 1, "low": 2}
    finds = sorted(findings, key=lambda f: sev_order.get(f["severity"], 3))
    lines = []
    lines.append("# 优化前后对比报告 (Optimization Report)\n")
    lines.append("- 目标: `%s`" % target)
    lines.append("- 自动应用策略: %s" % (", ".join(applied) or "无"))
    lines.append("- 仅建议(人工): %s" % (", ".join(report_only) or "无"))
    lines.append("")
    lines.append("## 关键发现 (按严重度)\n")
    for f in finds[:30]:
        lines.append("- **[%s] %s** @ %s — %s\n  - 建议: %s" % (
            f["severity"], f["rule_id"], f["location"], f["evidence"], f["recommendation"]))
    lines.append("")
    lines.append("## 已应用改动\n")
    for n in notes:
        lines.append("- " + n)
    if not notes:
        lines.append("- (无自动文本改动)")
    lines.append("")
    lines.append("## 统一差异 (Unified Diff)\n")
    lines.append("```diff")
    lines.extend(diff[:400])
    if len(diff) > 400:
        lines.append("... (truncated)")
    lines.append("```")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
