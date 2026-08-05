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


def sample_sentences_for_heavy(sents, budget=C.MAX_SENTENCES):
    """Return a representative sample of sentences for oversized skills.

    Rather than only scanning the first part, we take proportional slices from
    the beginning, middle, and end so late sections are not silently ignored.
    """
    n = len(sents)
    if n <= budget:
        return sents, [(0, n)]
    # keep head, mid, tail; each third gets budget/3 sentences
    third = budget // 3
    head = sents[:third]
    mid_start = max(third, (n - third) // 2)
    mid = sents[mid_start:mid_start + third]
    tail_start = n - third
    tail = sents[tail_start:]
    sampled = head + mid + tail
    ranges = [(0, third), (mid_start, mid_start + len(mid)), (tail_start, n)]
    return sampled, ranges


def near_dup_sentences(sents, th, minlen, heavy=False):
    findings = []
    n = len(sents)
    if heavy:
        sents, ranges = sample_sentences_for_heavy(sents)
        n = len(sents)
    else:
        ranges = None
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
                return findings, ranges
    return findings, ranges


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
        best_ratio = counts[best] / total if total else 1.0
        off = [v for v in variants if v != best and counts[v] > 0]
        if off:
            for v in off:
                suggestions[v] = best
            # Confidence: low when the "best" form is barely dominant.
            confidence = "高" if best_ratio >= 0.7 else ("中" if best_ratio >= 0.5 else "低（建议人工复核）")
            findings.append(C.make_finding(
                "SEM-003", "medium", "semantic", "SKILL.md",
                "术语不一致: %s 混用 (%s)；规范写法置信度 %s" % (
                    canon, ", ".join("%s×%d" % (v, counts[v]) for v in variants), confidence),
                "统一为 '%s'%s" % (best, "；若置信度低，请人工确认规范写法" if "低" in confidence else "")))
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
            if tp and tn and jaccard(tp, tn) >= 0.4:
                findings.append(C.make_finding(
                    "SEM-004", "high", "semantic", "SKILL.md",
                    "疑似冲突指令: '%s' vs '%s'（请人工复核，可能为正常正负场景说明）" % (p[:40], n[:40]),
                    "确认确为冲突后，保留更安全/更具体的版本，删除或弱化另一条"))
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
        description="Prompt semantic analysis: redundancy, terminology, conflict detection.")
    ap.add_argument("skill_md", help="Path to SKILL.md")
    ap.add_argument("--json", action="store_true", help="Output JSON")
    ap.add_argument("--min-sentence-len", type=int, default=None, help="Minimum sentence length")
    ap.add_argument("--config", default=None, help="Path to config.json")
    args = ap.parse_args()

    try:
        cfg = C.read_config(args.config)
        th = cfg.get("thresholds", {})
        minlen = args.min_sentence_len or th.get("min_sentence_len", 8)
        dup_j = th.get("dup_sentence_jaccard", 0.6)
        rep_min = th.get("repeat_phrase_min_count", 4)
        drift = th.get("drift_threshold", 0.2)

        raw = C.safe_read_text(args.skill_md, label="SKILL.md")
        _, body, _ = C.parse_frontmatter(raw)
        sents_full = split_sentences(body)
        heavy = C.body_too_heavy(body) or len(sents_full) > C.MAX_SENTENCES_BEFORE_HEAVY
        findings = []
        if heavy:
            sents_sampled, dup_ranges = sample_sentences_for_heavy(sents_full, budget=C.MAX_SENTENCES)
            sampled_blocks = ["第 %d–%d 句" % (start + 1, end) for start, end in dup_ranges]
            reason = "正文超过 %d 词" % C.MAX_BODY_WORDS_FOR_HEAVY if C.body_too_heavy(body) else "句子数超过 %d" % C.MAX_SENTENCES_BEFORE_HEAVY
            findings.append(C.make_finding(
                "SEM-INFO", "low", "semantic", "SKILL.md",
                "%s，已启用分段采样：近义句重复（O(n²)）只在重点段 %s 深度检查；"
                "术语一致性、冲突指令、高频短语、意图漂移已对全文做全量浅扫兜底。" % (
                    reason, "、".join(sampled_blocks)),
                "如需更深度的逐句两两比较，可将大段正文外置到 references/ 后重跑"))
        else:
            sents_sampled = sents_full
        # O(n²) 近义句重复：heavy 时仅采样段；否则全量
        findings += near_dup_sentences(sents_sampled, dup_j, minlen, heavy=heavy)[0]
        # O(n) 全量检查：heavy 与正常模式下都对全文执行（全量浅扫兜底）
        findings += repeated_phrases(body, rep_min)
        clusters = cfg.get("term_clusters", DEFAULT_CLUSTERS)
        term_f, suggestions = term_consistency(body, clusters)
        findings += term_f
        findings += conflict_instructions(sents_full)
        findings += intent_drift(body, drift)
    except Exception as e:
        code, message, next_step = C.humanize_error(e, "semantic_analyzer")
        _emit(code, message, next_step, args.json)
        sys.exit(1)

    if args.json:
        print(json.dumps({"ok": True, "semantic_findings": findings,
                          "term_unify_suggestions": suggestions},
                         ensure_ascii=False, indent=2))
    else:
        print("Semantic findings (%d):" % len(findings))
        for f in findings:
            print("  [%s] %s — %s" % (f["severity"], f["rule_id"], f["evidence"]))


if __name__ == "__main__":
    main()
