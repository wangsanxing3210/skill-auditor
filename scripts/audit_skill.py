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
        if re.search(r"(?:^|[\s，。；])(?:i can|you can|you should|我可以|你可以|你能|你应该)",
                     desc.strip().lower()):
            add("STRUCT-006", "medium", "structure", "SKILL.md:description",
                "description 用第一/第二人称，弱化被发现与被路由", 
                "改为第三人称能力描述：'审查…的技能，当用户需要…时使用'")
    if fm.get("agent_created") is not True:
        add("STRUCT-004", "low", "structure", "SKILL.md", "缺少 agent_created: true",
            "加入 agent_created: true 以便后续可被修改")

    # --- 规范合规（对标 agentskills.io 规范与主流 marketplace 校验项） ---
    name = (fm.get("name") or "").strip()
    if name:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or not 1 <= len(name) <= 64:
            add("STRUCT-015", "medium", "structure", "SKILL.md:name",
                "name 不符合规范：%r（应为 1-64 字符、小写字母数字与连字符、无首尾或连续连字符）" % name,
                "改成 kebab-case 标识，如 my-skill-name")
        dir_name = os.path.basename(os.path.abspath(skill_dir))
        if dir_name and dir_name != name and re.fullmatch(r"[a-z0-9][a-z0-9-]*", dir_name):
            add("STRUCT-016", "low", "structure", "SKILL.md:name",
                "name 与所在目录名不一致：name=%s，目录=%s" % (name, dir_name),
                "把目录名改成与 name 一致，或反之（多数宿主以 name 作为唯一标识）")
    if desc:
        if len(desc) > 1024:
            add("STRUCT-017", "medium", "structure", "SKILL.md:description",
                "description 长度 %d 字符，超过 1024 上限" % len(desc),
                "把触发细节移到正文 Trigger 段落，description 保留能力 + WHEN")
        elif len(desc) < 20:
            add("STRUCT-017", "low", "structure", "SKILL.md:description",
                "description 仅 %d 字符，过短不利于被发现" % len(desc),
                "补一句 WHEN 触发场景与 3-5 个关键词")
    n_body_lines = len(body.splitlines())
    if n_body_lines > 500:
        add("STRUCT-018", "low", "structure", "SKILL.md",
            "正文 %d 行，超过 500 行惯例上限" % n_body_lines,
            "把细节拆到 references/，SKILL.md 只留流程与指针")

    # 机器绝对路径：换台机器就失效（~/ 形式的家目录相对路径不在此列）
    # 覆盖 POSIX（/Users、/home、/root、file:///）、Windows 盘符（C:\ 与 C:/）、UNC（\\host\share）。
    # 盘符前加负向断言，避免把 https:// 里的 "s:/" 误判成 D 盘路径。
    for m in re.finditer(r"(?:/Users/|/home/|/root/|file:///)"
                         r"|(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s)\"'`]+"
                         r"|\\\\[A-Za-z0-9_.\-]+\\[^\s\"'`]+", raw):
        add("STRUCT-019", "low", "structure", "SKILL.md",
            "正文出现机器绝对路径: %s" % m.group(0)[:60],
            "改用相对路径（scripts/x.py）或 <skill-dir> 占位，避免换机失效")
        break

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
    # PROMPT-001: trigger phrases are explicit (lists user utterances that invoke the skill)
    trigger_signals = ("触发词", "触发方式", "triggers include", "触发", "when to use", "when to")
    if not any(s in body for s in trigger_signals):
        add("PROMPT-001", "medium", "prompt", "SKILL.md", "未列出可触发该技能的用户表述/触发词",
            "补充「触发词速查卡」或 When To Use 段落，给出典型用户说法")
    # PROMPT-002: role/target stated up front
    if not any(s in body for s in ("Overview", "概述", "这个技能做什么", "角色", "目标", "用途")):
        add("PROMPT-002", "medium", "prompt", "SKILL.md", "开头未说明技能角色/目标",
            "在 Overview 或开头段落说明「这个技能做什么、适用谁」")

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

    # EFF-002: oversized inline content that should be externalized to references/
    # Heuristic: any fenced code block > 40 lines, or any single section body that is
    # very long without a references/ pointer, signals content better placed in references/.
    fence_blocks = re.findall(r"```(?:[A-Za-z0-9_-]*)\n(.*?)```", body, re.S)
    big_blocks = [b for b in fence_blocks if b.strip() and len(b.strip().splitlines()) > 40]
    if big_blocks:
        add("EFF-002", "medium", "efficiency", "SKILL.md",
            "存在 %d 个超长内联代码块（>40 行），可外置到 references/" % len(big_blocks),
            "将大段可复用内容拆分为 references/ 下的独立文件，SKILL.md 仅引用入口")

    # EFF-005: 渐进式披露的另一半——外置了却没人引用，等于死资源
    referenced = set(C.referenced_paths(body))
    for f in sorted(files):
        if not (f.startswith("references/") or f.startswith("assets/")):
            continue
        if f in referenced:
            continue
        add("EFF-005", "low", "efficiency", f,
            "孤立资源：文件存在，但 SKILL.md 从未引用它",
            "在 SKILL.md 正文链接该文件（让加载链路可达），或删除无用资源")

    # repository metadata files that some skill hosts skip (e.g. .gitignore, LICENSE)
    for f in files:
        name = os.path.basename(f)
        if name == ".gitignore" or (name == "LICENSE" and not os.path.splitext(name)[1]):
            add("STRUCT-014", "low", "structure", f,
                "仓库元数据文件 '%s' 可能被 Skill 宿主跳过（不支持的文件类型）" % name,
                "该文件对 Skill 运行无影响；如希望宿主识别，可改放仓库根目录或改为带扩展名的文件（如 LICENSE.md）")

    return findings


def _slugify_anchor(text):
    return C.slugify_anchor(text)


def re_anchor(body):
    """Return set of GitHub-style heading anchors present in body."""
    out = set()
    for m in re.finditer(r"^#{1,6}\s+(.+?)\s*$", body, re.M):
        out.add(_slugify_anchor(m.group(1)))
    return out


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
    (the very bug found during skill-inspector's own self-audit).
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


def to_sarif(findings, tool_name="skill-inspector"):
    """Render findings as SARIF 2.1.0 so CI / GitHub Security tab can consume them.

    Level mapping: high -> error, medium -> warning, low -> note.
    Location "SKILL.md:12" is turned into a physicalLocation with startLine.
    """
    level = {"high": "error", "medium": "warning", "low": "note"}
    rules, results, seen = [], [], set()
    for f in findings:
        rid = f.get("rule_id", "UNKNOWN")
        if rid not in seen:
            seen.add(rid)
            rule = {
                "id": rid,
                "name": rid.replace("-", "_"),
                "shortDescription": {"text": "%s（%s）" % (rid, f.get("category", ""))},
                "properties": {"tags": ["skill-audit", f.get("category", "general")]},
            }
            if f.get("owasp"):
                rule["properties"]["tags"].append("OWASP-Agentic-Skills-" + f["owasp"])
                rule["shortDescription"]["text"] = "%s（%s）" % (rid, f.get("title", f.get("category", "")))
            rules.append(rule)
        loc = f.get("location", "")
        path, _, line = loc.partition(":")
        try:
            start = int(re.sub(r"\D.*", "", line) or 1)
        except ValueError:
            start = 1
        results.append({
            "ruleId": rid,
            "level": level.get(f.get("severity", "low"), "note"),
            "message": {"text": "%s → %s" % (f.get("evidence", ""), f.get("recommendation", ""))},
            "locations": [{"physicalLocation": {
                "artifactLocation": {"uri": path or "SKILL.md"},
                "region": {"startLine": max(1, start)},
            }}],
        })
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{
            "tool": {"driver": {
                "name": tool_name,
                "informationUri": "https://github.com/wangsanxing3210",
                "rules": rules,
            }},
            "results": results,
        }],
    }


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
        description="Structural / prompt-quality / efficiency audit of a skill.")
    ap.add_argument("target", help="Skill directory or path to SKILL.md")
    ap.add_argument("--json", action="store_true", help="Output JSON（等价 --format json）")
    ap.add_argument("--format", choices=["text", "json", "sarif"], default=None,
                    help="输出格式：text / json / sarif（SARIF 2.1.0，供 CI 与 GitHub Security 用）")
    ap.add_argument("--config", default=None, help="Path to config.json")
    args = ap.parse_args()
    fmt = args.format or ("json" if args.json else "text")

    try:
        cfg = C.read_config(args.config)
        skill = C.load_skill(args.target)
        findings = run_builtin(skill, cfg)
        findings += run_custom(skill, cfg)
    except Exception as e:
        code, message, next_step = C.humanize_error(e, "audit_skill")
        _emit(code, message, next_step, fmt != "text")
        sys.exit(1)

    # de-dup by (rule_id, location)
    seen = set()
    uniq = []
    for f in findings:
        key = (f["rule_id"], f["location"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)

    if fmt == "json":
        print(json.dumps({"ok": True, "target": skill["dir"], "count": len(uniq), "findings": uniq},
                         ensure_ascii=False, indent=2))
    elif fmt == "sarif":
        print(json.dumps(to_sarif(uniq), ensure_ascii=False, indent=2))
    else:
        print("Audit findings for %s (%d):" % (skill["dir"], len(uniq)))
        for f in uniq:
            print("  [%s] %s @ %s — %s" % (f["severity"], f["rule_id"], f["location"], f["evidence"]))


if __name__ == "__main__":
    main()
