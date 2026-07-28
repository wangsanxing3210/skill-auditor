#!/usr/bin/env python3
"""semantic_analyzer.py — prompt semantic analysis.

Detects near-duplicate sentences, repeated phrases, terminology inconsistency,
conflicting instructions, and intent drift. Deterministic (no model calls).

Usage:
  python3 semantic_analyzer.py <skill.md> [--json] [--min-sentence-len N]
"""
import os
import sys
import re
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C

STOP = set("的 了 和 与 及 或 在 是 对 中 一个 一种 可以 我们 你 我 它 这 那 该 等 并 也 都 "
           "the a an of to and or in is are for with this that you we it".split())

# Default term clusters are framework-neutral on purpose: only cross-framework
# generic variants are bundled. Product-specific clusters (e.g. a tool's name)
# belong in config.term_clusters, not here — see references/prompt-semantic-analysis.md.
DEFAULT_CLUSTERS = {
    "Skill": ["Skill", "skill", "技能", "这个技能"],
    "frontmatter": ["frontmatter", "前置元数据", "YAML头", "yaml头"],
}


_PUNCT = "，。！？、；：\"'（）()[]{}…—.,!?;: \t\n\r"
_PUNCT_TRANS = str.maketrans({p: " " for p in _PUNCT})


def tokenize(s):
    s = s.lower().translate(_PUNCT_TRANS)
    toks = set(s.split())
    cjk = re.findall(r"[一-鿿]", s)
    for i in range(len(cjk) - 1):
        toks.add("".join(cjk[i:i + 2]))
    toks.update(cjk)
    return toks


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def split_sentences(body):
    """Split into sentences, skipping code fences, headings, list items, tables."""
    out = []
    in_code = False
    for line in body.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        # skip list items, blockquotes, table rows, numbered items
        if s[0] in "-*•>|" or re.match(r"^\d+[\.\)]", s):
            continue
        for part in re.split(r"(?<=[。！？!?])", line):
            part = part.strip()
            if part:
                out.append(part)
    return out


def near_dup_sentences(sents, th, minlen):
    findings = []
    n = len(sents)
    for i in range(n):
        if len(sents[i]) < minlen:
            continue
        ti = tokenize(sents[i]) - STOP
        if len(ti) < 4:
            continue
        for j in range(i + 1, n):
            if len(sents[j]) < minlen:
                continue
            tj = tokenize(sents[j]) - STOP
            if len(tj) < 4:
                continue
            inter = ti & tj
            if len(inter) < 4:
                continue
            sc = jaccard(ti, tj)
            if sc >= th:
                findings.append(C.make_finding(
                    "SEM-001", "medium", "semantic",
                    "SKILL.md", "近义重复句(相似度 %.2f): '%s' ≈ '%s'" % (sc, sents[i][:40], sents[j][:40]),
                    "合并为一条表述"))
            if len(findings) >= 20:
                return findings
    return findings


def repeated_phrases(body, min_count):
    toks = re.findall(r"[A-Za-z]+|[一-鿿]", body.lower())
    # build word-ish tokens: ascii words + cjk chars
    words = re.findall(r"[a-z0-9]+|[一-鿿]", body.lower())
    counts = {}
    for n in (2, 3):
        for i in range(len(words) - n + 1):
            gram = " ".join(words[i:i + n])
            if all(w in STOP for w in gram.split() if w in STOP and len(w) <= 1):
                # skip pure stopword grams
                if set(gram.split()) <= STOP:
                    continue
            counts[gram] = counts.get(gram, 0) + 1
    findings = []
    for gram, c in sorted(counts.items(), key=lambda x: -x[1]):
        if c >= min_count and len(gram) > 3:
            findings.append(C.make_finding(
                "SEM-002", "low", "semantic", "SKILL.md",
                "高频重复短语 '%s' 出现 %d 次" % (gram, c),
                "合并或代词化，减少重复"))
            if len(findings) >= 10:
                break
    return findings


def term_consistency(body, clusters):
    suggestions = {}
    findings = []
    for canon, variants in clusters.items():
        counts = {}
        for v in variants:
            # case-sensitive count so 'Skill' and 'skill' are not double-counted
            counts[v] = body.count(v)
        total = sum(counts.values())
        if total == 0:
            continue
        best = max(counts, key=counts.get)
        off = [v for v in variants if v != best and counts[v] > 0]
        if off:
            for v in off:
                suggestions[v] = best
            findings.append(C.make_finding(
                "SEM-003", "medium", "semantic", "SKILL.md",
                "术语不一致: %s 混用 (%s)" % (canon, ", ".join("%s×%d" % (v, counts[v]) for v in variants)),
                "统一为 '%s'" % best))
    return findings, suggestions


POS = ["必须", "应该", "应当", "始终", "只能", "需要", "务必", "must", "should", "always"]
NEG = ["禁止", "不要", "绝不", "不可", "避免", "严禁", "never", "must not", "don't"]


def conflict_instructions(sents):
    findings = []
    pos = [s for s in sents if any(w in s for w in POS)]
    neg = [s for s in sents if any(w in s for w in NEG)]
    for p in pos:
        tp = tokenize(p) - STOP
        for n in neg:
            tn = tokenize(n) - STOP
            if tp and tn and jaccard(tp, tn) >= 0.3:
                findings.append(C.make_finding(
                    "SEM-004", "high", "semantic", "SKILL.md",
                    "冲突指令: '%s' vs '%s'" % (p[:40], n[:40]),
                    "保留更安全/更具体的版本，删除另一条"))
    return findings


def intent_drift(body, th):
    # capability keywords from Overview / When To Use
    cap = ""
    m = re.search(r"##\s*(Overview|When To Use|概述|何时使用).*?(?=\n##\s|\Z)", body, re.S | re.I)
    if m:
        cap = m.group(0)
    cap_tokens = tokenize(cap) - STOP
    findings = []
    for sec in re.findall(r"##\s+[^\n]+\n(.*?)(?=\n##\s|\Z)", body, re.S):
        if len(sec.split()) < 30:
            continue
        st = tokenize(sec) - STOP
        if cap_tokens:
            ov = jaccard(st, cap_tokens)
            if ov < th:
                findings.append(C.make_finding(
                    "SEM-005", "low", "semantic", "SKILL.md",
                    "段落与声明能力关键词重叠度低 (%.2f)" % ov,
                    "确认是否偏离技能能力范围，必要时精简"))
    return findings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skill_md")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-sentence-len", type=int, default=None)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    cfg = C.read_config(args.config)
    th = cfg.get("thresholds", {})
    minlen = args.min_sentence_len or th.get("min_sentence_len", 8)
    dup_j = th.get("dup_sentence_jaccard", 0.6)
    rep_min = th.get("repeat_phrase_min_count", 4)
    drift = th.get("drift_threshold", 0.2)

    with open(args.skill_md, "r", encoding="utf-8") as f:
        body = f.read()
    # strip frontmatter for semantic analysis
    _, body, _ = C.parse_frontmatter(body)

    sents = split_sentences(body)
    findings = []
    findings += near_dup_sentences(sents, dup_j, minlen)
    findings += repeated_phrases(body, rep_min)
    clusters = cfg.get("term_clusters", DEFAULT_CLUSTERS)
    term_f, suggestions = term_consistency(body, clusters)
    findings += term_f
    findings += conflict_instructions(sents)
    findings += intent_drift(body, drift)

    if args.json:
        print(json.dumps({"semantic_findings": findings,
                          "term_unify_suggestions": suggestions},
                         ensure_ascii=False, indent=2))
    else:
        print("Semantic findings (%d):" % len(findings))
        for f in findings:
            print("  [%s] %s — %s" % (f["severity"], f["rule_id"], f["evidence"]))


if __name__ == "__main__":
    main()
