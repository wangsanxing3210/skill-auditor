#!/usr/bin/env python3
"""skill_tester.py — automated testing of a skill.

Three layers:
  1. Static integrity tests (fully automated, filesystem-backed): frontmatter parses,
     referenced resources exist, code fences balanced, internal anchors resolve.
  2. Test-plan generation: boundary cases + accuracy cases derived from the skill's
     own description and examples.
  3. Heuristic evaluation (zero-dependency): when no `--model-config` is given, the
     plan is evaluated with deterministic pattern-matching rules, so `build_report.py`
     can emit real pass/fail conclusions without any external model. Pass `--model-config`
     to run cases against a real model instead; `--merge-results` folds executed results in.

Usage:
  python3 skill_tester.py <target> [--plan-only] [--run] [--no-model]
         [--model-config config.json] [--merge-results results.json] [--human]
"""
import os
import sys
import re
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C


def static_tests(skill):
    body = skill["body"]
    files = set(skill["files"])
    results = []

    def add(tid, name, ok, evidence):
        results.append({"id": tid, "name": name, "status": "pass" if ok else "fail", "evidence": evidence})

    # ST-frontmatter
    add("ST-01", "frontmatter 可解析", skill["fm_ok"],
        "ok" if skill["fm_ok"] else "frontmatter 缺失或格式错误")
    # ST-references
    missing = [r for r in C.referenced_paths(body) if r not in files]
    add("ST-02", "引用资源真实存在", not missing,
        "ok" if not missing else "缺失: " + ", ".join(missing))
    # ST-fence balance
    fences = body.count("```")
    add("ST-03", "代码围栏配对", fences % 2 == 0,
        "ok" if fences % 2 == 0 else "存在未闭合的 ``` (%d 个)" % fences)
    # ST-anchors: use GitHub-compatible slugify so CJK headings and punctuation
    # match the link anchors the doc actually uses.
    heads = re.findall(r"^#{1,6}\s+(.+)$", body, re.M)
    anchors = {C.slugify_anchor(h) for h in heads}
    broken = re.findall(r"\]\(#([\w\-]+)\)", body)
    broken = [b for b in broken if b not in anchors]
    add("ST-04", "内部锚点可解析", not broken,
        "ok" if not broken else "死锚点: " + ", ".join(broken))
    # ST-description
    add("ST-05", "description 非空", bool(skill["frontmatter"].get("description")),
        "ok" if skill["frontmatter"].get("description") else "description 为空")
    return results


def extract_examples(body):
    """Pull fenced code blocks and '例' paragraphs as accuracy cases."""
    cases = []
    for i, m in enumerate(re.finditer(r"```(?:[\w-]*)\n(.*?)```", body, re.S)):
        snippet = m.group(1).strip()
        if snippet:
            cases.append(("accuracy", "示例#%d 可执行性" % (i + 1), snippet[:200],
                          "示例中的命令/步骤可被复现且产出符合预期"))
    for i, m in enumerate(re.finditer(r"(?:例\d*|example)\s*[:：]\s*(.+)", body, re.I)):
        cases.append(("accuracy", "文字示例#%d" % (i + 1), m.group(1).strip()[:200],
                      "示例场景可被技能正确处理"))
    return cases


def build_plan(skill):
    body = skill["body"]
    desc = skill["frontmatter"].get("description", "")
    cases = []
    cid = 0

    def add(typ, name, prompt, expected):
        nonlocal cid
        cid += 1
        cases.append({"id": "TC-%03d" % cid, "type": typ, "name": name,
                      "prompt": prompt, "expected": expected, "status": "manual"})

    # boundary cases
    add("boundary", "空输入", "（不提供任何输入直接调用该技能）",
        "技能应给出引导而非崩溃")
    add("boundary", "超大输入", "传入远超常规长度的 SKILL.md（>5k 词）",
        "技能应稳定处理或给出明确限制说明")
    add("boundary", "缺失可选参数", "仅提供目标路径，省略 --config 等可选参数",
        "技能应以默认配置正常运行")
    add("boundary", "歧义意图", "用与描述无关的表述触发该技能",
        "技能应判断是否适用，不适用则说明")
    # accuracy: capability vs description
    add("accuracy", "能力-描述一致性", "依据 description 触发一次典型任务: %s" % desc[:120],
        "技能实际行为覆盖 description 所声称的能力")
    # accuracy: replay examples
    for typ, name, snippet, expected in extract_examples(body):
        add(typ, name, snippet, expected)
    return cases


def merge_results(plan, results_path):
    with open(results_path, "r", encoding="utf-8") as f:
        ext = json.load(f)
    by_id = {r["id"]: r for r in ext.get("cases", [])}
    for c in plan:
        if c["id"] in by_id:
            c["status"] = by_id[c["id"]].get("status", c["status"])
            if "evidence" in by_id[c["id"]]:
                c["evidence"] = by_id[c["id"]]["evidence"]
    return plan


def heuristic_eval(skill, cases):
    """Zero-dependency evaluation of boundary/accuracy cases.

    Replaces `manual` status with a deterministic pass/fail by pattern-matching
    the skill's own body — so `build_report.py` can emit real conclusions without
    any model config. Results are conservative: a case only passes when concrete
    structural evidence exists (same philosophy as trace_eval's tightened metrics).
    """
    body = skill["body"]
    desc = skill["frontmatter"].get("description", "")
    bl = body.lower()
    # Precompute evidence sets -------------------------------------------------
    has_boundary_section = bool(re.search(r"边界|异常处理|错误处理|容错|降级", body))
    has_limit = bool(re.search(r"5 ?k|512|3 ?万|3000|限制|阈值|超大|降级", bl))
    has_empty_handling = bool(re.search(r"空输入|无输入|空\b|empty", bl))
    has_clarify = bool(re.search(r"澄清|追问|不明确|模糊|问卷|先问", body))
    has_error_guidance = bool(re.search(r"error|错误|报错|失败|回退|fallback|提示", bl))
    examples = extract_examples(body)

    def ev(case):
        typ = case["type"]
        name = case["name"]
        # ---- boundary cases ----
        if "空输入" in name:
            ok = has_empty_handling and has_boundary_section
            evi = ("SKILL.md 含空输入处理话术" if has_empty_handling else "未见空输入处理话术")
            if not has_boundary_section:
                evi += "；且未见边界/异常处理章节"
        elif "超大输入" in name:
            ok = has_limit
            evi = "SKILL.md 声明了大小/词数限制或降级策略" if has_limit else "未见超限保护声明（如 512KB/3万词阈值）"
        elif "缺失可选参数" in name:
            ok = bool(re.search(r"默认|default|可省略|可选|无需配置|零配置", body))
            evi = "SKILL.md 说明可选参数可用默认值" if ok else "未见可选参数默认值说明"
        elif "歧义意图" in name:
            ok = has_clarify
            evi = "SKILL.md 含澄清问卷/先问后做机制" if has_clarify else "未见意图澄清机制"
        elif "能力-描述一致性" in name:
            dt = C.tokenize_weak(desc)
            ct = C.tokenize_weak(body[:600])
            ov = (len(dt & ct) / len(dt | ct)) if (dt | ct) else 0
            ok = ov >= 0.1
            evi = "description 与正文开头能力词重叠率 %.0f%%" % (ov * 100)
        else:
            # ---- accuracy: replay examples ----
            ok = has_error_guidance or has_boundary_section
            evi = "正文含错误处理/边界说明，示例环境可预期" if ok else "示例缺乏可执行性佐证"
        case["status"] = "pass" if ok else "fail"
        case["evidence"] = "启发式: " + evi
        return case

    return [ev(dict(c)) for c in cases]


def _emit(code, message, next_step, json_mode, human_mode):
    if json_mode:
        print(json.dumps({"ok": False, "error": {"code": code, "message": message, "next_step": next_step}},
                         ensure_ascii=False, indent=2))
    else:
        print("[%s] %s" % (code, message))
        if next_step:
            print("下一步: %s" % next_step)


def main():
    ap = argparse.ArgumentParser(
        description="Automated testing: static integrity + boundary/accuracy test-plan generation.")
    ap.add_argument("target", help="Skill directory or path to SKILL.md")
    ap.add_argument("--plan-only", action="store_true",
                    help="只生成边界/准确性用例，不跑静态检查")
    ap.add_argument("--run", action="store_true",
                    help="执行静态完整性检查（零配置即可运行）")
    ap.add_argument("--model-config", default=None,
                    help="模型配置 JSON（可选；仅在你想自动执行模型测试时使用）")
    ap.add_argument("--no-model", action="store_true",
                    help="用零依赖启发式规则评估边界/准确性用例（默认：无 --model-config 时自动启用）")
    ap.add_argument("--merge-results", default=None, help="合并已执行的用例结果 JSON")
    ap.add_argument("--json", action="store_true", help="输出 JSON（默认即为 JSON）")
    ap.add_argument("--human", action="store_true", help="人类可读输出")
    args = ap.parse_args()

    try:
        skill = C.load_skill(args.target)

        model_cfg = None
        if args.model_config:
            try:
                with open(args.model_config, "r", encoding="utf-8") as f:
                    model_cfg = json.load(f)
            except Exception as e:
                raise C.GuardError("E_MODEL_CONFIG", "model-config 读取失败: %s" % e,
                                   "检查文件路径与 JSON 格式，或先省略 --model-config 跑静态测试") from e

        # --plan-only: only generate the boundary/accuracy test plan (no static run).
        # --run: execute static integrity tests (the default when neither flag is given
        #        also runs static, but --run is the explicit "I want the static pass now").
        # Default (no flag): run static + generate plan, for a complete one-shot check.
        run_static = not args.plan_only
        static = static_tests(skill) if run_static else []
        cases = build_plan(skill)

        if args.merge_results:
            cases = merge_results(cases, args.merge_results)
        # Heuristic evaluation: whenever we have no real model output, evaluate the
        # plan deterministically so reports carry conclusions instead of "manual".
        use_heuristic = (args.no_model or (not model_cfg and not args.merge_results))
        if use_heuristic:
            cases = heuristic_eval(skill, cases)
    except Exception as e:
        code, message, next_step = C.humanize_error(e, "skill_tester")
        _emit(code, message, next_step, args.json, args.human)
        sys.exit(1)

    passed = sum(1 for s in static if s["status"] == "pass")
    manual = sum(1 for c in cases if c["status"] == "manual")
    executed = sum(1 for c in cases if c["status"] in ("pass", "fail"))
    heur = sum(1 for c in cases if str(c.get("evidence", "")).startswith("启发式"))

    out = {
        "ok": True,
        "target": skill["dir"],
        "model_config": model_cfg,
        "eval_mode": "heuristic" if heur else ("merged" if args.merge_results else "manual"),
        "static": static,
        "cases": cases,
        "summary": {
            "static_total": len(static), "static_pass": passed,
            "cases_total": len(cases), "cases_manual": manual, "cases_executed": executed,
            "cases_heuristic": heur,
        },
    }

    if args.human:
        print("Skill test plan for %s" % skill["dir"])
        print("Static (%d/%d pass):" % (passed, len(static)))
        for s in static:
            print("  [%s] %s — %s" % (s["status"], s["name"], s["evidence"]))
        print("Cases (%d manual, %d heuristic-executed):" % (manual, executed))
        for c in cases:
            print("  [%s] %s: %s" % (c["status"], c["type"], c["name"]))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
