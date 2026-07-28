"""Shared helpers for the skill-auditor meta-skill scripts.

Stdlib only. Provides skill loading, frontmatter parsing, config reading, and a
uniform Finding structure so every analyzer emits consistent JSON.
"""
import os
import sys
import json
import re

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
    """Load a target skill into a dict. target may be a dir or SKILL.md path."""
    path = find_skill_md(target)
    if not path:
        raise FileNotFoundError("SKILL.md not found under: %s" % target)
    skill_dir = os.path.dirname(path)
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
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
