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
MAX_SENTENCES = 1_500                 # semantic analyzer sample budget per run
MAX_BODY_WORDS_FOR_HEAVY = 30_000     # above this, switch to sampled analysis
MAX_SENTENCES_BEFORE_HEAVY = 3_000    # above this sentence count, also sample

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
    """Convert common exceptions into plain-language messages + next steps.

    The returned message is aimed at end users who may not be technical. The
    optional internal error code is still returned but not embedded in the text.
    """
    if isinstance(exc, GuardError):
        # GuardError already carries user-friendly wording; just keep it.
        return exc.code, str(exc), exc.next_step
    if isinstance(exc, FileNotFoundError):
        return (
            "E_NOT_FOUND",
            "没找着目标 Skill。你指定的路径里似乎没有 SKILL.md。",
            "请检查一下路径：如果是目录，确保里面包含 SKILL.md；也可以直接拖进 SKILL.md 的完整路径。",
        )
    if isinstance(exc, PermissionError):
        return (
            "E_PERMISSION",
            "当前账号没法读/写这个路径，通常是权限不够。",
            "换个有权限的目录，或者在命令行用 ls -la 看看当前用户是否有读写权限。",
        )
    if isinstance(exc, json.JSONDecodeError):
        return (
            "E_BAD_JSON",
            "配置文件格式不对，JSON 在第 %s 行附近解析失败了。" % exc.lineno,
            "常见原因是多了/少了逗号、引号没成对。可以用任意 JSON 校验器（如 json.cn）粘贴检查。",
        )
    if isinstance(exc, UnicodeDecodeError):
        return (
            "E_ENCODING",
            "文件编码识别不了。skill-auditor 只认 UTF-8 编码的文本。",
            "用编辑器把 SKILL.md / 配置文件另存为'UTF-8 无 BOM'后再试一次。",
        )
    if isinstance(exc, MemoryError):
        return (
            "E_MEMORY",
            "内存不够用了，文件太大导致处理到一半卡住。",
            "先关掉其他占用内存的程序；或者把 SKILL.md 拆成多个 references/ 文件，只留核心内容在正文。",
        )
    return (
        "E_UNEXPECTED",
        "运行中出了点意外，工具没料到这种情况。",
        "可以重试一下；如果每次必现，请把完整报错和用到的命令一起反馈。",
    )


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
            "%s 有点大（%.1f KB），超过了当前 %.1f KB 的处理限制。" % (label, size / 1024, MAX_SKILL_BYTES / 1024),
            "① 精简 SKILL.md 正文，把细节移到 references/；② 或在 config.json 中提高阈值（advanced）。"
        )
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError as e:
        raise GuardError("E_ENCODING", "%s 编码识别不了。skill-auditor 只认 UTF-8 编码的文本。" % label,
                         "用编辑器把文件另存为'UTF-8 无 BOM'后再试一次。") from e
    except OSError as e:
        raise GuardError("E_READ", "%s 读取出错了：%s" % (label, e),
                         "检查文件权限与磁盘状态，或换一个路径重试。") from e


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
            "没找着目标 Skill。你指定的路径 '%s' 里似乎没有 SKILL.md。" % target,
            "请检查一下路径：如果是目录，确保里面包含 SKILL.md；也可以直接拖进 SKILL.md 的完整路径。"
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


def slugify_anchor(text):
    """GitHub-compatible heading anchor slug: lowercase, spaces->'-', keep
    [\\w-] (incl. CJK), drop everything else, collapse hyphens, strip ends."""
    s = (text or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^\w\-]", "", s, flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def strip_code_fences(text):
    """Remove fenced code blocks (``` ... ```) and inline code (`...`) so that
    quoted example content (which may legitimately contain trigger tokens)
    doesn't trip keyword-based checks like T3 (exaggeration)."""
    if not text:
        return ""
    # fenced blocks
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    # inline code
    text = re.sub(r"`[^`]+`", " ", text)
    return text


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
