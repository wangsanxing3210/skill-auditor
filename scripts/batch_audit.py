#!/usr/bin/env python3
"""batch_audit.py — 批量并行审计多个 Skill，输出汇总看板。

单个 Skill 用 run_all.py；**一堆** Skill 用本脚本：一条命令把整个技能目录扫一遍，
并行跑（默认 CPU 核数，上限 8），最后给一张 BATCH-AUDIT.md 看板：

  - 总览表：每个技能的 TRACE / 等级 / 高·中·低发现数 / 安全命中 / 静态通过 / 用例 / 耗时
  - 共性问题：同一条规则在几个技能里出现（找系统性短板，而不是逐个修）
  - 待修清单：按严重度排序的具体条目，带文件与行号

设计取向：
  **只读**——只调用各分析脚本读目标，不写任何 artifact 到目标目录（不像 run_all 会
  在目标下建 .skill-audit/）。批量扫别人托管的技能目录时，这一点很重要。
  需要单个技能完整报告时，再对那个目录单独跑 run_all.py。

CI 门禁：--fail-on {none,low,medium,high} 任一技能达到该严重度即失败；
--fail-under <分数> **每个**技能都要达标（不是看平均分）。退出码：门禁 2 / 步骤失败 1。

Usage:
  python3 batch_audit.py <skill目录> [<skill目录> ...]
                        [--root <父目录>]... [--depth 3]
                        [--jobs 4] [--out BATCH-AUDIT.md] [--json]
                        [--fail-on high] [--fail-under 80] [--timeout 180]
"""
import os
import sys
import json
import time
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 批量扫描时不该进入的目录（缓存/依赖/产物/版本库）
SKIP_DIRS = {
    ".git", ".hg", ".svn", ".skill-audit", "__pycache__", "node_modules",
    ".venv", "venv", "env", "dist", "build", ".pytest_cache", ".mypy_cache",
    ".idea", ".vscode", ".cache",
}

SEV_RANK = {"low": 1, "medium": 2, "high": 3}


# ---------------------------------------------------------------- discovery
def discover(roots, depth=3):
    """从若干根路径找 Skill 目录（含 SKILL.md）。

    命中 SKILL.md 的目录即视为一个技能，且不再向下递归——避免把技能里
    自带的示例技能算成两个目标。按真实路径去重。
    """
    found, seen = [], set()

    def add(d):
        real = os.path.realpath(d)
        if real in seen:
            return
        seen.add(real)
        found.append(os.path.abspath(d))

    for root in roots:
        root = os.path.abspath(root)
        if os.path.isfile(root):
            if os.path.basename(root) == "SKILL.md":
                add(os.path.dirname(root))
                continue
            print("[E_NOT_SKILL] %s 不是 SKILL.md，已跳过" % root, file=sys.stderr)
            continue
        if not os.path.isdir(root):
            print("[E_NOT_FOUND] %s 不存在或是文件，已跳过" % root, file=sys.stderr)
            continue
        if os.path.isfile(os.path.join(root, "SKILL.md")):
            add(root)
            continue
        for cur, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
            # 用相对路径的段数算深度，别数字符：Windows 盘符（C:\）与 POSIX 的
            # 分隔符数量不同，按字符数计深度会让 --depth 语义在两个平台上不一致。
            rel = os.path.relpath(cur, root)
            cur_depth = 0 if rel == os.curdir else len(rel.split(os.sep))
            if cur_depth >= depth:
                dirs[:] = []
            if "SKILL.md" in files:
                add(cur)
                dirs[:] = []
    return found


# ---------------------------------------------------------------- one skill
def _run(script, args, timeout):
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, script)] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", env=C.child_env())
    except subprocess.TimeoutExpired:
        return None, "%s 超时（>%ds）" % (script, timeout)
    except OSError as e:
        return None, "%s 无法执行: %s" % (script, e)
    if r.returncode != 0:
        detail = (r.stderr or r.stdout or "").strip().splitlines()
        return None, "%s 退出 %d%s" % (script, r.returncode,
                                       ("：" + detail[-1][:120]) if detail else "")
    try:
        return json.loads(r.stdout), None
    except json.JSONDecodeError:
        return None, "%s 输出不是 JSON" % script


def audit_one(path, timeout=180):
    """审计单个技能：跑 5 个分析脚本，汇总为一行看板数据。"""
    t0 = time.time()
    errors = []
    md = os.path.join(path, "SKILL.md")

    audit, err = _run("audit_skill.py", ["--json", path], timeout)
    if err:
        errors.append(err)
    semantic, err = _run("semantic_analyzer.py", ["--json", md], timeout)
    if err:
        errors.append(err)
    security, err = _run("security_analyzer.py", ["--json", path], timeout)
    if err:
        errors.append(err)
    trace, err = _run("trace_eval.py", ["--json", path], timeout)
    if err:
        errors.append(err)
    testplan, err = _run("skill_tester.py", ["--run", path], timeout)
    if err:
        errors.append(err)

    findings = []
    for payload, key, source in ((audit, "findings", "audit"),
                                 (semantic, "semantic_findings", "semantic"),
                                 (security, "findings", "security")):
        if isinstance(payload, dict):
            for f in payload.get(key) or []:
                f = dict(f)
                f["_source"] = source
                findings.append(f)

    sev_counts = {"high": 0, "medium": 0, "low": 0}
    for f in findings:
        s = f.get("severity", "low")
        sev_counts[s] = sev_counts.get(s, 0) + 1

    n_security = len((security or {}).get("findings") or []) if isinstance(security, dict) else 0
    tl = (trace or {}).get("overall")
    summ = (testplan or {}).get("summary", {}) if isinstance(testplan, dict) else {}

    return {
        "name": os.path.basename(path.rstrip(os.sep)),
        "path": path,
        "trace": tl,
        "grade": (trace or {}).get("grade", "—"),
        "high": sev_counts.get("high", 0),
        "medium": sev_counts.get("medium", 0),
        "low": sev_counts.get("low", 0),
        "security": n_security,
        "static": "%d/%d" % (summ.get("static_pass", 0), summ.get("static_total", 0)),
        "cases": summ.get("cases_total", 0),
        "seconds": round(time.time() - t0, 1),
        "findings": findings,
        "errors": errors,
    }


# ---------------------------------------------------------------- dashboard
def _worst_sev(row):
    rank = 0
    for f in row["findings"]:
        rank = max(rank, SEV_RANK.get(f.get("severity", "low"), 1))
    return rank


def _fmt_trace(v):
    return "—" if v is None else ("%.1f" % v)


def build_dashboard(rows, roots, jobs, elapsed, gate_msgs):
    ts = time.strftime("%Y-%m-%d %H:%M")
    ok_rows = [r for r in rows if r["trace"] is not None]
    scores = [r["trace"] for r in ok_rows]
    avg = (sum(scores) / len(scores)) if scores else None
    worst_row = min(ok_rows, key=lambda r: r["trace"]) if ok_rows else None
    bad = [r for r in rows if r["errors"]]

    L = []
    L.append("# 批量审计看板")
    L.append("")
    L.append("- 生成时间：%s" % ts)
    L.append("- 扫描范围：%d 个技能（根路径：%s）" % (len(rows), "、".join(roots)))
    L.append("- 并行度：%d · 总用时 %.1fs" % (jobs, elapsed))
    if avg is not None:
        L.append("- TRACE 平均 %.1f · 最低 %s（%s）%s" % (
            avg, _fmt_trace(worst_row["trace"]), worst_row["name"],
            (" · 运行异常 %d 个" % len(bad)) if bad else ""))
    L.append("")
    L.append("## 总览（按 TRACE 从低到高）")
    L.append("")
    L.append("> 高/中/低 含语义发现（SEM-*）；`--fail-on` 的口径与此一致，比单技能 run_all 更严格。")
    L.append("")
    L.append("| 技能 | TRACE | 等级 | 高/中/低 | 安全 | 静态 | 用例 | 耗时 |")
    L.append("|------|-------|------|----------|------|------|------|------|")
    for r in sorted(rows, key=lambda x: (x["trace"] is None, x["trace"] if x["trace"] is not None else 0)):
        L.append("| %s | %s | %s | %d/%d/%d | %d | %s | %d | %.1fs |" % (
            r["name"], _fmt_trace(r["trace"]), r["grade"],
            r["high"], r["medium"], r["low"], r["security"],
            r["static"], r["cases"], r["seconds"]))
    L.append("")

    # 共性问题：同一条规则横跨几个技能
    by_rule = {}
    for r in rows:
        for f in r["findings"]:
            rid = f.get("rule_id", "?")
            slot = by_rule.setdefault(rid, {"count": 0, "skills": set(),
                                            "sev": f.get("severity", "low")})
            slot["count"] += 1
            slot["skills"].add(r["name"])
    if by_rule:
        L.append("## 共性问题（同一条规则命中多个技能 = 系统性短板，优先统一修）")
        L.append("")
        L.append("| 规则 | 严重度 | 次数 | 涉及技能 |")
        L.append("|------|--------|------|----------|")
        for rid, slot in sorted(by_rule.items(),
                                key=lambda kv: (-SEV_RANK.get(kv[1]["sev"], 1), -kv[1]["count"]))[:15]:
            names = "、".join(sorted(slot["skills"])[:6])
            more = " 等 %d 个" % len(slot["skills"]) if len(slot["skills"]) > 6 else ""
            L.append("| %s | %s | %d | %s%s |" % (rid, slot["sev"], slot["count"], names, more))
        L.append("")

    # 待修清单
    todo = []
    for r in rows:
        for f in r["findings"]:
            if f.get("severity") in ("high", "medium"):
                todo.append((SEV_RANK.get(f["severity"], 1), r["name"], f))
    todo.sort(key=lambda x: -x[0])
    if todo:
        L.append("## 待修清单（high / medium，最多 30 条）")
        L.append("")
        for _, name, f in todo[:30]:
            L.append("- **%s** `%s` @ %s — %s" % (
                name, f.get("rule_id", "?"), f.get("location", "—"),
                (f.get("evidence") or "")[:110]))
        L.append("")

    if bad:
        L.append("## 运行异常")
        L.append("")
        for r in bad:
            L.append("- **%s**：%s" % (r["name"], "；".join(r["errors"])))
        L.append("")

    L.append("## 怎么用这份看板")
    L.append("")
    L.append("1. 先看「共性问题」——一条规则跨多个技能，改一次规范比逐个修省事。")
    L.append("2. 再看 `high` 条目，按「待修清单」从上往下修。")
    L.append("3. 需要单个技能的完整体检报告时：`python3 scripts/run_all.py <该技能目录>`。")
    L.append("")
    L.append("> 本看板由 `batch_audit.py` 生成，只读扫描，未改动任何目标目录。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="批量并行审计多个 Skill 并输出汇总看板")
    ap.add_argument("targets", nargs="*", help="技能目录（或 SKILL.md 路径），可多个")
    ap.add_argument("--root", action="append", default=[], help="父目录，递归查找其中的技能（可多次指定）")
    ap.add_argument("--depth", type=int, default=3, help="--root 下的递归深度（默认 3）")
    ap.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 4), help="并行度（默认 CPU 核数，上限 8）")
    ap.add_argument("--timeout", type=int, default=180, help="单个脚本超时秒数（默认 180）")
    ap.add_argument("--out", default=None, help="看板输出路径（默认 ./BATCH-AUDIT.md）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 摘要（不写看板）")
    ap.add_argument("--fail-on", choices=["none", "low", "medium", "high"], default="none",
                    help="CI 门禁：任一技能出现该严重度即失败")
    ap.add_argument("--fail-under", type=float, default=None,
                    help="CI 门禁：每个技能的 TRACE 都要 ≥ 该值")
    args = ap.parse_args()

    roots = list(args.targets) + list(args.root)
    if not roots:
        ap.error("至少给一个技能目录或 --root")

    targets = discover(roots, args.depth)
    if not targets:
        print("[E_NO_SKILL] 在这些路径下没找到任何含 SKILL.md 的技能：%s" % "、".join(roots))
        print("下一步: ls -la <路径> 确认目录结构；技能目录里必须有 SKILL.md。")
        sys.exit(1)

    jobs = max(1, min(args.jobs, 16, len(targets)))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        rows = list(pool.map(lambda p: audit_one(p, args.timeout), targets))
    elapsed = time.time() - t0

    # 门禁
    gate = []
    if args.fail_on != "none":
        bad = [r["name"] for r in rows if _worst_sev(r) >= SEV_RANK[args.fail_on]]
        if bad:
            gate.append("以下技能存在 ≥%s 级发现：%s" % (args.fail_on, "、".join(bad)))
    if args.fail_under is not None:
        low = [("%s(%s)" % (r["name"], _fmt_trace(r["trace"])))
               for r in rows if r["trace"] is None or r["trace"] < args.fail_under]
        if low:
            gate.append("TRACE 未达 %s：%s" % (args.fail_under, "、".join(low)))

    failed = [r for r in rows if r["errors"]]

    if args.json:
        print(json.dumps({
            "ok": not gate and not failed,
            "count": len(rows),
            "jobs": jobs,
            "seconds": round(elapsed, 1),
            "average_trace": (round(sum(r["trace"] for r in rows if r["trace"] is not None)
                                    / max(1, len([r for r in rows if r["trace"] is not None])), 1)),
            "rows": [{k: v for k, v in r.items() if k != "findings"} for r in rows],
            "gate_failed": gate,
        }, ensure_ascii=False, indent=2))
        sys.exit(2 if gate else (1 if failed else 0))

    out_path = args.out or os.path.abspath("BATCH-AUDIT.md")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(build_dashboard(rows, roots, jobs, elapsed, gate))

    print("== 批量审计完成 ==")
    print("  技能: %d 个 | 并行: %d | 用时 %.1fs" % (len(rows), jobs, elapsed))
    print("  看板: %s" % out_path)
    for r in sorted(rows, key=lambda x: (x["trace"] is None, x["trace"] if x["trace"] is not None else 0))[:5]:
        print("  %-28s TRACE %-5s %s  安全 %d" % (r["name"], _fmt_trace(r["trace"]),
                                                  r["grade"], r["security"]))
    if failed:
        print("  ⚠ 运行异常: %s" % "、".join(r["name"] for r in failed))
    if gate:
        print("  ✗ 门禁未通过: %s" % "；".join(gate))
    sys.exit(2 if gate else (1 if failed else 0))


if __name__ == "__main__":
    main()
