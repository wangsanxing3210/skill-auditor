"""Shared helpers for the skill-auditor meta-skill scripts.

Stdlib only. Provides skill loading, frontmatter parsing, config reading, and a
uniform Finding structure so every analyzer emits consistent JSON.
"""
import os
import sys
import json
import re

# Resource guards: keep the tool responsive on oversized skills.
MAX_SKILL_BYTES = 512 * 1024          # ~512 KB SKILL.md soft cap
MAX_SENTENCES = 2_000                 # semantic analyzer early-exit threshold
MAX_BODY_WORDS_FOR_HEAVY = 50_000     # above this, skip O(n^2) heavy checks

DEFAULT_CONFIG = {
    "rules": {},
    "weights": {"T": 0.22, "R": 0.24, "A": 0.18, "C": 0.18, "E": 0.18},
    "strategies": {"allow_aggressive": False},
    "thresholds": {
        "dup_sentence_jaccard": 0.6,
        "repeat_phrase_min_count": 4,
        "drift_threshold": 0.2,
        "min_sentence_len": 8,
        "max_skill_words": 5000,
    },
}


class GuardError(Exception):
    """A user-friendly error with a concrete next-step recommendation."""
    def __init__(self, code, message, next_step=""):
        super().__init__(message)
        self.code = code
        self.next_step = next_step


def humanize_error(exc, tool_name="skill-auditor"):
    """Convert common exceptions into plain-language messages + next steps."""
    if isinstance(exc, GuardError):
        return exc.code, str(exc), exc.next_step
    if isinstance(exc, FileNotFoundError):
        return "E_NOT_FOUND", "找不到目标 Skill 或 SKILL.md", "请确认路径正确，或给出包含 SKILL.md 的目录"
    if isinstance(exc, PermissionError):
        return "E_PERMISSION", "没有权限读取/写入该路径", "检查文件权限，或换一个你有写权限的目录"
    if isinstance(exc, json.JSONDecodeError):
        return "E_BAD_JSON", "JSON 配置文件解析失败（%s 附近）" % exc.lineno, "用 JSON 校验器检查 config / model-config 文件格式"
    if isinstance(exc, UnicodeDecodeError):
        return "E_ENCODING", "文件编码不是 UTF-8，无法读取", "将 SKILL.md 转为 UTF-8 编码后再试"
    if isinstance(exc, MemoryError):
        return "E_MEMORY", "系统内存不足，无法处理该文件", "关闭其他程序，或换一台内存更大的机器；也可拆分 SKILL.md"
    return "E_UNEXPECTED", "运行中遇到意外错误: %s" % exc, "请重试；若持续出现，请截图错误信息反馈"


def safe_read_text(path, label="文件"):
    """Read a text file with size guard and clear error messages."""
    try:
        size = os.path.getsize(path)
    except OSError as e:
        raise GuardError("E_STAT", "无法读取 %s 大小: %s" % (label, e),
                         "检查路径是否存在且有读取权限") from e
    if size > MAX_SKILL_BYTES:
        raise GuardError(
            "E_TOO_LARGE",
            "%s 大小 %.1f KB，超过当前限制 %.1f KB" % (label, size / 1024, MAX_SKILL_BYTES / 1024),
            "① 精简 SKILL.md 正文，把细节移到 references/；② 或在 config.json 中提高阈值（advanced）"
        )
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError as e:
        raise GuardError("E_ENCODING", "%s 编码错误: %s" % (label, e),
                         "将文件保存为 UTF-8 无 BOM 格式后再试") from e
    except OSError as e:
        raise GuardError("E_READ", "读取 %s 失败: %s" % (label, e),
                         "检查文件权限与磁盘状态") from e


def find_skill_md(target):
    """Resolve the SKILL.md path from a dir or a file."""
    if os.path.isfile(target):
        return target
    cand = os.path.join(target, "SKILL.md")
    return cand if os.path.isfile(cand) else None


def parse_frontmatter(text):
    """Parse a simple YAML frontmatter. Returns (frontmatter_dict, body, ok)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, False
    fm = {}
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
        line = lines[i]
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if val.lower() in ("true", "false"):
                val = val.lower() == "true"
            fm[key] = val
    if end is None:
        return {}, text, False
    body = "\n".join(lines[end + 1:])
    return fm, body, True


def load_skill(target):
    """Load a target skill into a dict. target may be a dir or SKILL.md path.

    Applies a soft size guard on SKILL.md; oversized files raise GuardError with
    actionable guidance instead of crashing later during O(n^2) analysis.
    """
    path = find_skill_md(target)
    if not path:
        raise GuardError(
            "E_NO_SKILL_MD",
            "在 '%s' 下找不到 SKILL.md" % target,
            "请给出 Skill 目录（含 SKILL.md）或直接给出 SKILL.md 的完整路径"
        )
    skill_dir = os.path.dirname(path)
    raw = safe_read_text(path, label="SKILL.md")
    fm, body, ok = parse_frontmatter(raw)
    files = []
    for root, _, fnames in os.walk(skill_dir):
        for fn in fnames:
            full = os.path.join(root, fn)
            files.append(os.path.relpath(full, skill_dir))
    return {
        "dir": skill_dir,
        "skill_md": path,
        "raw": raw,
        "frontmatter": fm,
        "body": body,
        "fm_ok": ok,
        "files": files,
    }


def body_too_heavy(body):
    """Return True if the body is large enough that O(n^2) checks should degrade."""
    return len(body.split()) > MAX_BODY_WORDS_FOR_HEAVY


def read_config(path):
    """Read JSON config and merge over defaults (shallow)."""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            user = json.load(f)
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


def make_finding(rule_id, severity, category, location, evidence, recommendation):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "category": category,
        "location": location,
        "evidence": evidence,
        "recommendation": recommendation,
    }


def load_findings(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        # support both {"findings":[...]} and {"audit_findings":[...], ...}
        out = []
        for key in ("findings", "audit_findings", "semantic_findings"):
            if key in data and isinstance(data[key], list):
                out.extend(data[key])
        return out
    return data


def write_json(obj, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def referenced_paths(body):
    """Extract referenced resource paths (scripts/ references/ assets/)."""
    pats = [
        r"scripts/[A-Za-z0-9_./\-]+\.\w+",
        r"references/[A-Za-z0-9_./\-]+\.\w+",
        r"assets/[A-Za-z0-9_./\-]+",
    ]
    found = []
    for p in pats:
        found.extend(re.findall(p, body))
    return sorted(set(found))


def tokenize_weak(text):
    """Lightweight token set for overlap checks (ascii words + cjk chars)."""
    text = (text or "").lower()
    toks = set(re.findall(r"[a-z0-9]+", text))
    toks.update(re.findall(r"[一-鿿]", text))
    return toks


def ref_enabled(rules, rule_id, default_sev="medium"):
    """Return (enabled, severity) for a rule from config.rules."""
    entry = (rules or {}).get(rule_id)
    if entry is None:
        return True, default_sev
    if entry.get("enabled") is False:
        return False, default_sev
    return True, entry.get("severity", default_sev)
