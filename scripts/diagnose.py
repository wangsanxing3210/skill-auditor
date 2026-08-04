#!/usr/bin/env python3
"""diagnose.py — one-shot environment & skill health check.

Zero-dependency diagnostic that answers the classic "why isn't this working?"
without needing the user to know anything about Python, paths, or JSON.

Checks:
  1. Python runtime (version, stdlib availability).
  2. Target skill path (SKILL.md present? readable? encoding? frontmatter?).
  3. Config files (JSON validity).
  4. Repository files (dotfiles that skill hosts may reject, e.g. .gitignore).

Usage:
  python3 diagnose.py [target] [--json]

Outputs a plain-language "environment health report" with pass/warn/fail per
check and copy-pasteable fix commands where possible.
"""
import os
import sys
import re
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C

DOTFILE_ISSUES = [".gitignore", ".gitattributes", ".editorconfig", ".npmrc", ".eslintrc"]
FIX_HINTS = {
    "E_NO_SKILL_MD": "ls -la <路径> 看看目录内容；确认里面有 SKILL.md",
    "E_BAD_JSON": "python3 -c 'import json; json.load(open(\"config.json\"))' 定位格式错误行",
    "E_ENCODING": "用编辑器把文件另存为 UTF-8 无 BOM",
    "E_TOO_LARGE": "wc -c SKILL.md 查实际大小；把细节移到 references/",
    "E_PERMISSION": "ls -ld <路径> 查属主权限；换目录或 sudo（慎用）",
}


def _py_version():
    return "%d.%d.%d" % sys.version_info[:3]


def _check_runtime():
    rows = []
    ok = True
    # python version
    v = sys.version_info
    ok_v = v.major == 3 and v.minor >= 9
    rows.append(("pass" if ok_v else "warn",
                 "Python 版本 %s（需要 3.9+）" % _py_version()))
    ok = ok and ok_v
    # stdlib modules
    need = ["json", "re", "argparse", "difflib", "zipfile", "base64"]
    missing = [m for m in need if not _has_module(m)]
    rows.append(("pass" if not missing else "fail",
                 "标准库模块齐全" if not missing else "缺少标准库模块: %s" % ", ".join(missing)))
    ok = ok and not missing
    # scripts importable
    bad_imports = []
    for script in ("audit_skill", "semantic_analyzer", "trace_eval",
                   "skill_tester", "optimize_apply", "build_report"):
        if not _imports_ok(script):
            bad_imports.append(script)
    rows.append(("pass" if not bad_imports else "fail",
                 "全部脚本可导入" if not bad_imports else "导入失败: %s" % ", ".join(bad_imports)))
    ok = ok and not bad_imports
    return ok, rows


def _has_module(name):
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _imports_ok(script):
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), script + ".py")
        with open(p, encoding="utf-8") as f:
            compile(f.read(), p, "exec")
        return True
    except Exception:
        return False


def _check_target(path):
    rows = []
    ok = True
    if not path:
        rows.append(("warn", "未指定目标 Skill，跳过路径检查（用 python3 diagnose.py <路径> 指定）"))
        return True, rows
    # path exists?
    if not os.path.exists(path):
        rows.append(("fail", "路径不存在: %s" % path))
        rows.append(("info", "试试：ls -la <父目录> 或 cd ~/.workbuddy/skills && ls"))
        return False, rows
    skill_md = path if os.path.isfile(path) else os.path.join(path, "SKILL.md")
    if not os.path.isfile(skill_md):
        rows.append(("fail", "没找到 SKILL.md（路径 %s 不是文件，也不含 SKILL.md）" % path))
        rows.append(("info", "试试：ls -la %s" % path))
        return False, rows
    rows.append(("pass", "找到 SKILL.md: %s" % skill_md))
    # readable + encoding
    try:
        with open(skill_md, "r", encoding="utf-8") as f:
            raw = f.read()
        rows.append(("pass", "SKILL.md 可读，UTF-8 解析正常（%.1f KB）" % (len(raw.encode("utf-8")) / 1024)))
    except UnicodeDecodeError:
        rows.append(("fail", "SKILL.md 不是 UTF-8 编码，无法解析"))
        rows.append(("info", "用编辑器另存为 UTF-8 无 BOM 后再试"))
        return False, rows
    except OSError as e:
        rows.append(("fail", "SKILL.md 读取失败: %s" % e))
        rows.append(("info", "检查文件权限：ls -l %s" % skill_md))
        return False, rows
    # frontmatter
    fm, body, ok_fm = C.parse_frontmatter(raw)
    if not ok_fm:
        rows.append(("warn", "frontmatter 缺失或格式异常（仍可审正文，但 frontmatter 相关规则会失分）"))
    else:
        need_fields = [k for k in ("name", "description") if not fm.get(k)]
        if need_fields:
            rows.append(("warn", "frontmatter 缺字段: %s（会触发 STRUCT-002/003）" % ", ".join(need_fields)))
        else:
            rows.append(("pass", "frontmatter 正常（含 name + description）"))
    # oversized?
    if len(raw.encode("utf-8")) > C.MAX_SKILL_BYTES:
        rows.append(("warn", "SKILL.md 超过 512 KB，会触发 E_TOO_LARGE；建议拆分到 references/"))
    # dotfiles that hosts may reject
    files = []
    for root, _, fnames in os.walk(os.path.dirname(skill_md)):
        for fn in fnames:
            files.append(os.path.relpath(os.path.join(root, fn), os.path.dirname(skill_md)))
    bad_dot = [f for f in files if os.path.basename(f) in DOTFILE_ISSUES]
    if bad_dot:
        rows.append(("warn", "包含宿主可能拒绝的 dotfile: %s（上传 SkillHub 前建议移出发行包）" % ", ".join(bad_dot)))
    # config files valid JSON?
    for cfg in ("config.json", "model-config.json"):
        p = os.path.join(os.path.dirname(skill_md), cfg)
        if os.path.isfile(p):
            try:
                json.load(open(p, encoding="utf-8"))
                rows.append(("pass", "%s 是合法 JSON" % cfg))
            except Exception as e:
                rows.append(("fail", "%s JSON 解析失败: %s" % (cfg, e)))
                rows.append(("info", "试试：python3 -c 'import json; json.load(open(\"%s\"))'" % cfg))
                ok = False
    return ok, rows


def main():
    ap = argparse.ArgumentParser(description="一键环境与 Skill 健康诊断")
    ap.add_argument("target", nargs="?", default=None, help="Skill 目录或 SKILL.md 路径（可省略）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    checks = []
    ok_runtime, rows_runtime = _check_runtime()
    checks.append(("runtime", ok_runtime, rows_runtime))
    ok_target, rows_target = _check_target(args.target)
    checks.append(("target", ok_target, rows_target))

    all_ok = all(ok for _, ok, _ in checks)
    n_warn = sum(1 for _, ok, rows in checks if ok for st, _ in rows if st == "warn")
    n_fail = sum(1 for _, ok, rows in checks if ok for st, _ in rows if st == "fail")
    # failures inside failed groups also counted above only for ok groups; recount properly:
    n_fail = 0
    n_warn = 0
    for _, _, rows in checks:
        for st, _ in rows:
            if st == "fail":
                n_fail += 1
            elif st == "warn":
                n_warn += 1

    result = {
        "ok": all_ok,
        "summary": {"fails": n_fail, "warns": n_warn},
        "checks": [{"name": name, "rows": [{"status": st, "message": msg} for st, msg in rows]}
                   for name, ok, rows in checks],
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("== 环境健康报告 ==")
    for name, ok, rows in checks:
        print("\n[%s] %s" % ("✓" if ok else "✗", name))
        for st, msg in rows:
            icon = {"pass": "  ✓", "warn": "  ⚠", "fail": "  ✗", "info": "  ·"}[st]
            print("%s %s" % (icon, msg))
    print("\n结论：%s（%d 个问题，%d 个警告）" % (
        "环境正常，可以开始审查" if all_ok else "存在需要处理的问题", n_fail, n_warn))


if __name__ == "__main__":
    main()
