---
name: skill-auditor
description: 'Meta-skill for auditing, testing, and optimizing other WorkBuddy skills. Use when the user asks to review / audit / improve / optimize a SKILL.md, evaluate a skill''s quality, find redundant or inconsistent prompts, test a skill''s boundary cases, run a SkillHub TRACE evaluation, or produce a before/after comparison report of skill changes. Triggers include "审查这个Skill", "优化 SKILL.md", "给这个 Skill 做个 TRACE 评测", "测一下这个技能的边界情况", "Skill 提示词冗余检测", "对比优化前后".'
agent_created: true
---

# Skill Auditor（元 Skill：审查 · 评测 · 优化）

## Overview

A meta-skill that treats other WorkBuddy skills as the object of analysis. It audits a target
skill's **logic structure, prompt quality, and execution efficiency**, runs an automated
**testing** pass (output-accuracy and boundary-case checks), and — based on the audit + test
results — produces concrete **improvement recommendations** and can **auto-apply** safe
optimizations. All results are rendered as a **before/after comparison report**.

The quality bar is the **SkillHub TRACE** evaluation system: five dimensions —
**T**rust (可信任度), **R**eliability (可靠性), **A**daptability (适用性),
**C**onvention (规范性), **E**ffectiveness (有效性). See `references/trace-framework.md`.

The skill ships with an **extensible audit-rule registry** and **configurable optimization
strategies** (see `references/audit-rules.md` and `references/optimization-strategies.md`), so
the rule set and the auto-apply behavior can be tuned without editing code.

## When To Use

- Review a skill before publishing or after feedback ("帮我看看这个 Skill 写得怎么样").
- Optimize a SKILL.md that has grown bloated or inconsistent ("把提示词里重复的地方合并一下").
- Run a TRACE scorecard for a skill library / marketplace submission.
- Test a skill's robustness ("这个 Skill 在空输入 / 超大输入下会怎样").
- Produce a diffable before/after report of skill edits ("对比优化前后改了什么").

## Design Principles

1. **Audit before change.** Never edit a skill before producing findings; optimizations are
   derived from evidence, not taste.
2. **Safe-by-default auto-apply.** `optimize_apply.py` only applies *reversible, low-risk*
   transformations (dedupe, frontmatter fix, section completion, phrasing normalization) unless
   the operator passes `--aggressive`. High-risk edits are reported, not applied.
3. **Deterministic where possible.** Structural, semantic, and TRACE checks run as scripts
   (stdlib only, no external deps) so results are reproducible and diffable.
4. **Extensible.** New rules = new entry in a config file; new strategy = new strategy block.
   No code change required for routine extension.
5. **Confirm destructive actions, keep a fallback.** Any operation with a side effect
   (e.g. `--aggressive` rewrites, `--out` writes, or `publish`/外发 steps) must be previewed
   with `--dry-run` and explicitly confirmed. Safe rewrites always keep a reversible diff so
   you can fall back on failure (失败可回退); never silently overwrite the user's skill.

## Workflow

```
Phase 0  Locate & parse        → resolve target skill dir, read SKILL.md + bundled resources
Phase 1  Audit                  → structural + prompt-quality + efficiency (audit_skill.py, semantic_analyzer.py)
Phase 2  TRACE evaluation      → 5-dimension scorecard (trace_eval.py)
Phase 3  Automated testing     → static integrity + boundary/accuracy test plan (skill_tester.py)
Phase 4  Recommend + optimize  → build findings, apply safe fixes, emit diff (optimize_apply.py)
Phase 5  Report                → before/after comparison (assets/report_template.md)
```

Run phases in order. Each phase writes JSON artifacts into `<target>/.skill-audit/` so later
phases and the final report can consume them.

### Phase 0 — Locate & Parse

Resolve the target skill directory (the folder containing `SKILL.md`). If the user points at a
file, use its parent. Record the absolute path; all subsequent commands use it.

### Phase 1 — Audit

Run two analyzers and merge their findings:

```bash
python3 <skill_dir>/scripts/audit_skill.py <target> --json > <target>/.skill-audit/audit.json
python3 <skill_dir>/scripts/semantic_analyzer.py <target>/SKILL.md --json > <target>/.skill-audit/semantic.json
```

- `audit_skill.py` covers **structure** (frontmatter validity, required fields, resource
  references resolve, naming conventions), **prompt quality** (trigger clarity, instruction
  form, example coverage, length hygiene), and **efficiency** (duplicated blocks, oversized
  inline content that should be a reference, dead references).
- `semantic_analyzer.py` covers **prompt semantics**: near-duplicate sentences, repeated
  phrases, terminology inconsistency (same concept, different words), and conflicting
  instructions. See `references/prompt-semantic-analysis.md`.

Merge rule: union findings; de-duplicate by `(rule_id, location)`.

### Phase 2 — TRACE Evaluation

```bash
python3 <skill_dir>/scripts/trace_eval.py <target> --json > <target>/.skill-audit/trace.json
```

Produces a 0–100 score per dimension plus a weighted overall, with the evidence behind each
score. Methodology and weights live in `references/trace-framework.md`. Use the scores to
prioritize which findings to fix first (lowest dimension = highest leverage).

### Phase 3 — Automated Testing

```bash
python3 <skill_dir>/scripts/skill_tester.py <target> --plan-only > <target>/.skill-audit/testplan.json
```

`skill_tester.py` runs two layers:

1. **Static integrity tests (fully automated, high value):** every `scripts/`, `references/`,
   `assets/` path referenced in SKILL.md actually exists; examples are internally consistent;
   no broken internal anchors; frontmatter parses.
2. **Test-plan generation:** derives boundary cases (empty input, oversized skill, missing
   optional args, ambiguous intent) and accuracy cases (does the skill do what its description
   claims?) from the skill's own description and examples.

To actually execute the plan against a model, pass `--run` together with a model config
(`--model-config config.json`); otherwise the plan is emitted for an agent to execute manually
(see Phase 3 execution note below). Boundary/accuracy results are recorded in `testplan.json`
as `pass | fail | manual`.

> **Phase 3 execution note:** True output testing requires loading the target skill into a
> model session and running each case. When `--run` is not configured, the agent should: read
> `testplan.json`, execute the `manual` cases by invoking the target skill in a sandbox (or
> reasoning over its instructions), and write `pass/fail` + evidence back, then re-run
> `skill_tester.py --merge-results` to fold results into the report.

### Phase 4 — Recommend & Auto-Apply

Compile findings from Phases 1–3 into a single `findings.json`, then optimize:

```bash
# dry-run first (shows what would change, no writes)
python3 <skill_dir>/scripts/optimize_apply.py <target> \
    --findings <target>/.skill-audit/findings.json --dry-run

# apply safe optimizations + write diff + before/after report
python3 <skill_dir>/scripts/optimize_apply.py <target> \
    --findings <target>/.skill-audit/findings.json \
    --out <target>/.skill-audit/optimization-report.md
```

`optimize_apply.py` maps each finding to a strategy (see `references/optimization-strategies.md`)
and applies only **reversible** transformations by default. It writes a unified diff and a
human-readable before/after report. To also apply higher-risk rewrites, pass `--aggressive`
(and review the diff before committing).

If the user only wants recommendations (no edits), stop after the dry-run and present the
findings + TRACE scores directly.

### Phase 5 — Report

Assemble the final deliverable from `assets/report_template.md`:

- Skill identity (name, path, scope).
- TRACE scorecard table (5 dimensions + overall, with prior-vs-after if available).
- Top findings by severity, each with rule_id, location, evidence, recommendation.
- Testing summary (static pass rate + manual-case outcomes).
- Before/after diff excerpt for applied optimizations.
- Configurable next-step suggestions.

Write the report to `<target>/.skill-audit/REPORT.md` and present it.

## Configuration

All extensibility lives in a JSON config (copy `assets/config.example.json` to
`<target>/.skill-audit/config.json` and edit):

- `rules`: enable/disable audit rules by `rule_id`, set per-rule severity thresholds.
- `weights`: override TRACE dimension weights (must sum to 1.0).
- `strategies`: toggle which optimization strategies run, and whether `--aggressive` is allowed.
- `thresholds`: length/duplication/consistency numeric cutoffs.

Pass `--config <path>` to any script that supports it (`audit_skill.py`, `trace_eval.py`,
`optimize_apply.py`).

## Extensibility

- **Add an audit rule:** append an entry to `config.rules` with a new `rule_id` and point the
  script at a custom check module via `config.custom_rules_module` (a Python file exporting
  `def check(skill, ctx) -> list[Finding]`). `audit_skill.py` imports and runs it.
- **Add an optimization strategy:** add a `strategy_id` block to `config.strategies` and a
  corresponding transform in a custom module referenced by `config.custom_strategies_module`
  (exports `def transform(skill, finding, ctx) -> (new_text, change_note)`).
- **Custom TRACE weights / rubric:** edit `config.weights` and `config.trace_rubric`.

## Output Artifacts

All intermediate artifacts land in `<target>/.skill-audit/`:

```
.skill-audit/
  config.json          # active configuration
  audit.json           # Phase 1 structural/prompt/efficiency findings
  semantic.json        # Phase 1 semantic findings
  trace.json           # Phase 2 TRACE scorecard
  testplan.json        # Phase 3 test plan + results
  findings.json        # merged findings (Phase 4 input)
  optimization-report.md  # Phase 4 before/after + diff
  REPORT.md            # Phase 5 final deliverable
```

## Scripts Reference

| Script | Purpose | Key flags |
|--------|---------|-----------|
| `audit_skill.py` | Structure / prompt-quality / efficiency audit | `--json`, `--config`, `--rules-only` |
| `semantic_analyzer.py` | Redundancy, terminology, conflict detection | `--json`, `--min-sentence-len` |
| `trace_eval.py` | TRACE 5-dimension scoring | `--json`, `--config`, `--prior trace.json` |
| `skill_tester.py` | Static integrity + test-plan generation | `--plan-only`, `--run`, `--model-config`, `--merge-results` |
| `optimize_apply.py` | Apply safe optimizations + diff + report | `--dry-run`, `--aggressive`, `--out`, `--config` |

All scripts are Python 3.9+ stdlib-only. No network or external packages required for
audit / semantic / TRACE / static-test phases.
