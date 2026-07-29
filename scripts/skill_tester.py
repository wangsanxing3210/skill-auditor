#!/usr/bin/env python3
"""skill_tester.py — automated testing of a skill.

Two layers:
  1. Static integrity tests (fully automated, filesystem-backed): frontmatter parses,
     referenced resources exist, code fences balanced, internal anchors resolve.
  2. Test-plan generation: boundary cases + accuracy cases derived from the skill's
     own description and examples. These are marked `manual` for an agent/model to
     execute (see SKILL.md Phase 3 note); `--merge-results` folds executed results in.

Usage:
  python3 skill_tester.py <target> [--plan-only] [--run] [--merge-results results.json] [--human]
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
    # ST-anchors
    heads = re.findall(r"^#{1,6}\s+(.+)$", body, re.M)
    anchors = set()
    for h in heads:
        a = re.sub(r"[^\w\-]", "-", h.strip().lower())
        anchors.add(a)
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
    except Exception as e:
        code, message, next_step = C.humanize_error(e, "skill_tester")
        _emit(code, message, next_step, args.json, args.human)
        sys.exit(1)

    passed = sum(1 for s in static if s["status"] == "pass")
    manual = sum(1 for c in cases if c["status"] == "manual")
    executed = sum(1 for c in cases if c["status"] in ("pass", "fail"))

    out = {
        "ok": True,
        "target": skill["dir"],
        "model_config": model_cfg,
        "static": static,
        "cases": cases,
        "summary": {
            "static_total": len(static), "static_pass": passed,
            "cases_total": len(cases), "cases_manual": manual, "cases_executed": executed,
        },
    }

    if args.human:
        print("Skill test plan for %s" % skill["dir"])
        print("Static (%d/%d pass):" % (passed, len(static)))
        for s in static:
            print("  [%s] %s — %s" % (s["status"], s["name"], s["evidence"]))
        print("Cases (%d manual, %d executed):" % (manual, executed))
        for c in cases:
            print("  [%s] %s: %s" % (c["status"], c["type"], c["name"]))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
