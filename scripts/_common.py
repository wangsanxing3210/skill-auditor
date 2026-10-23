"""Shared helpers for the skill-inspector meta-skill scripts.

Stdlib only. Provides skill loading, frontmatter parsing, config reading,
cross-platform stdio/encoding helpers, and a uniform Finding structure so every
analyzer emits consistent JSON.
"""
import os
import sys
import json
import re

IS_WINDOWS = os.name == "nt"


def ensure_utf8_stdio():
    """把 stdout/stderr 固定为 UTF-8（Windows 兼容的关键一步）。

    为什么需要：Windows 上 Python 默认按本地代码页（cp936 / cp1252）写标准输出，
    报告里的中文会直接抛 UnicodeEncodeError，整个工具在 Windows 上"能跑但会崩"。
    被重定向到文件或管道时（CI 日志），固定 UTF-8 也保证字节跨平台一致。
    控制台流本身走 WindowsConsoleIO（UTF-8 通道），重设无副作用。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def child_env():
    """子进程环境变量：强制 UTF-8，避免 Windows 下中文输出乱码或解码失败。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def posix_rel(path, start):
    """相对路径统一用 `/` 分隔。

    报告里的文件位置、`references/` 链接检查、`.skill-audit/` 排除都按 `/` 写；
    Windows 的 `os.path.relpath` 会给反斜杠，若不归一，这些匹配会静默失效。
    """
    return os.path.relpath(path, start).replace(os.sep, "/")


# 导入即生效：所有脚本都从这里进来，一处修好全部脚本受益。
ensure_utf8_stdio()

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
        "paraphrase_jaccard": 0.55,
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


def humanize_error(exc, tool_name="skill-inspector"):
    """Convert common exceptions into plain-language messages + next steps.

    The returned message is aimed at end users who may not be technical. The
    optional internal error code is still returned but not embedded in the text.
    `next_step` includes copy-pasteable shell commands where relevant.
    """
    if isinstance(exc, GuardError):
        # GuardError already carries user-friendly wording; just keep it.
        return exc.code, str(exc), exc.next_step
    if isinstance(exc, FileNotFoundError):
        return (
            "E_NOT_FOUND",
            "没找着目标 Skill。你指定的路径里似乎没有 SKILL.md。",
            "先确认一下：ls -la <你的路径> 看看目录里有什么；如果是目录，里面必须有 SKILL.md 才能审。",
        )
    if isinstance(exc, PermissionError):
        return (
            "E_PERMISSION",
            "当前账号没法读/写这个路径，通常是权限不够。",
            "用 ls -ld <路径> 看属主和权限；没有权限就换个目录，或用 sudo 授权（慎用）。",
        )
    if isinstance(exc, json.JSONDecodeError):
        return (
            "E_BAD_JSON",
            "配置文件格式不对，JSON 在第 %s 行附近解析失败了。" % exc.lineno,
            "快速自检：python3 -c 'import json; json.load(open(\"config.json\"))' —— 若报错会指出具体行；"
            "常见原因是逗号/引号不成对，修好后再跑。",
        )
    if isinstance(exc, UnicodeDecodeError):
        return (
            "E_ENCODING",
            "文件编码识别不了。skill-inspector 只认 UTF-8 编码的文本。",
            "用编辑器把 SKILL.md / 配置文件另存为'UTF-8 无 BOM'后再试一次。",
        )
    if isinstance(exc, MemoryError):
        return (
            "E_MEMORY",
            "内存不够用了，文件太大导致处理到一半卡住。",
            "先关掉其他占用内存的程序；或把 SKILL.md 拆成多个 references/ 文件，只留核心内容在正文。",
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
            "先看实际大小：wc -c %s ；然后① 精简 SKILL.md 正文，把细节移到 references/；② 或在 config.json 中提高阈值（advanced）。"
            % os.path.basename(path)
        )
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError as e:
        raise GuardError("E_ENCODING", "%s 编码识别不了。skill-inspector 只认 UTF-8 编码的文本。" % label,
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


def _strip_yaml_quotes(val):
    """去掉 YAML 标量两侧的成对引号（'x' / "x"），保留内部引号。

    早期版本把引号一起返回，导致 description 长度、第一/第二人称、
    绝对化词等后续判断都带着引号噪声——属真实缺陷，故在此统一处理。
    """
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        return val[1:-1]
    return val


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
            val = _strip_yaml_quotes(val.strip())
            if isinstance(val, str) and val.lower() in ("true", "false"):
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
            files.append(posix_rel(full, skill_dir))
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


def strip_quoted_examples(text):
    """Remove text inside quotation marks (中文/英文引号) — a claim that appears
    quoted is a citation/example, not the skill's own promise.

    Used by keyword checks such as T3 so that prose like 反模式「保证 100% 正确」
    does not count as an exaggeration made by the skill itself.
    """
    if not text:
        return ""
    text = re.sub(r"「[^」\n]{0,200}」", " ", text)
    text = re.sub(r"『[^』\n]{0,200}』", " ", text)
    text = re.sub(r"“[^”\n]{0,200}”", " ", text)
    text = re.sub(r"‘[^’\n]{0,200}’", " ", text)
    text = re.sub(r'"[^"\n]{0,200}"', " ", text)
    text = re.sub(r"'[^'\n]{0,200}'", " ", text)
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
