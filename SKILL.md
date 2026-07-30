---
name: skill-auditor
version: 1.5.0
description: 'Meta-skill for auditing, testing, and optimizing any other skill — framework-agnostic, not bound to a single agent tool. Works on SKILL.md-based skills from WorkBuddy, OpenClaw, and similar frameworks. Use when the user asks to review / audit / improve / optimize a SKILL.md, evaluate a skill''s quality, find redundant or inconsistent prompts, test a skill''s boundary cases, run a TRACE evaluation, or produce a before/after comparison report of skill changes. Triggers include "审查这个Skill", "优化 SKILL.md", "给这个 Skill 做个 TRACE 评测", "测一下这个技能的边界情况", "Skill 提示词冗余检测", "对比优化前后".'
agent_created: true
---

# Skill Auditor（元 Skill：审查 · 评测 · 优化）

## Overview

A meta-skill that treats other skills as the object of analysis — framework-agnostic, applicable to any SKILL.md-based skill (WorkBuddy, OpenClaw, and similar tools). It audits a target
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

> **安全与伦理声明**：全部分析在本地完成，不联网、不上传你的 Skill 内容；自动优化始终保留可逆 diff 与 `.bak` 备份，绝不静默覆盖。仅"模型测试"阶段需你显式提供 `--model-config`，且该步可完全跳过。

## 触发词速查卡

| 你想让 skill-auditor 做什么 | 可以直接这样说 | 它会执行的阶段 |
|----------------------------|----------------|---------------|
| 审查一个 Skill | "审查一下 ~/.workbuddy/skills/foo" / "帮我看看这个 Skill 写得怎么样" | Phase 0–1 |
| 跑 TRACE 评分 | "给这个 Skill 做个 TRACE 评测" / "评一下质量" | Phase 2 |
| 测边界情况 | "测一下这个技能的边界情况" / "空输入/大文件会怎样" | Phase 3 |
| 优化并预览 | "把提示词里重复的地方合并一下，先给我看看" | Phase 4 dry-run |
| 确认落盘 | "确认优化" / "就按这个改" | Phase 4 apply |
| 对比前后 | "对比优化前后改了什么" | Phase 5 |

> 提示：不需要记特殊命令，用自然语言描述意图即可；skill-auditor 会先澄清模糊点再动手。

## 30 秒快速开始

第一次用，记住三件事：

1. **怎么启动**：直接对某个 Skill 说"审查这个 Skill""给这个 Skill 做个 TRACE 评测""测一下这个技能的边界情况"，或"对比优化前后"；等价说法都能触发（见上方触发词速查卡）。
2. **你会得到什么**：一份结构化报告——审计发现（结构/提示词/效率）+ TRACE 五维评分 + 测试结论；需要时才出前后 diff。
3. **想改就改，但先看清**：优化默认只给建议与 dry-run 预览；真正落盘需你确认，且每次改动都可回退。

**零配置开箱可用**：审查、语义分析、TRACE 评测、静态完整性测试都不需要任何外部模型或网络，下载即用；只有"模型输出测试"才需要可选的 `--model-config`。

**稳定性与资源保护**：SKILL.md 超过 512 KB 或正文超过 5 万词时，语义分析会自动降级为"采样模式"，避免占用过多内存；所有错误都会给出明确错误码 + 下一步操作建议，不会直接崩溃。

> **新手推荐阅读路径**：`## 能力边界与异常处理` → `## 示例（Few-shot）` → 需要完整场景案例看 `COOKBOOK.md` → 遇到卡点查 `FAQ.md` → 自定义看 `## Configuration`。

## When To Use

- Review a skill before publishing or after feedback ("帮我看看这个 Skill 写得怎么样").
- Optimize a SKILL.md that has grown bloated or inconsistent ("把提示词里重复的地方合并一下").
- Run a TRACE scorecard for a skill library / marketplace submission.
- Test a skill's robustness ("这个 Skill 在空输入 / 超大输入下会怎样").
- Produce a diffable before/after report of skill edits ("对比优化前后改了什么").
- 对自己的 Skill 做质量自检（用 skill-auditor 审 skill-auditor 自身）。

## 能力边界与异常处理

### 能力边界（三栏表）

| 类别 | 范围 | 处理原则 |
|------|------|----------|
| 能做 | 审查 / 评测 / 测试 / 安全优化任何基于 `SKILL.md` 的 Skill（WorkBuddy、OpenClaw 等框架通用） | 直接执行 Phase 0–5 标准流程 |
| 不做 | ①改写目标 Skill 的领域业务逻辑 ②处理二进制/非文本资源 ③保证某个评分或"一定通过" ④访问私有仓库或外发内容 | 明确告知不适用，不强行执行 |
| 降级做 | ①布局非标准（无 scripts/ 等约定目录）→ 仅审 SKILL.md 正文并标注缺失 ②脚本缺失 → 跳过对应检查并提示 ③未知框架 → 仍解析 `SKILL.md` 本体，按通用规则评测 | 优雅降级，不拒答但标注假设与边界 |

### 异常处理（诊断 → 修复 话术库）

| 异常现象 | 诊断 | 标准修复动作 |
|----------|------|--------------|
| 找不到目标 Skill | 路径/目录不对 | 用父目录解析；仍无 `SKILL.md` 则请用户给出正确路径 |
| `SKILL.md` 无法解析 | frontmatter 语法错误 | 报告具体行号，建议手动修正后再审 |
| 引用资源不存在 | 死链/路径漂移 | `audit_skill.py` 标记 STRUCT-007/008，`optimize_apply.py` 可安全修复或仅建议 |
| 发现有冲突 | 同概念多写法/冲突指令 | 输出 SEM-003/SEM-004，默认只建议；确需统一走 `OPT-TERM-UNIFY`（三重保护不降级） |
| 用户只要建议不要改 | 意图是"审查"非"优化" | 停在 dry-run，直接呈现发现 + TRACE，不写盘 |
| 高风险改写被拒 | `--aggressive` 超界 | 写入报告"仅建议(人工)"，由用户决策 |

### 澄清问卷（输入模糊时主动使用）

当用户未明确以下任一项时，动手前先问（合并提问，不超过 2 轮）：
1. 要审/测/优化**哪个 Skill** 的路径？
2. 作用域是 user 还是 project？
3. 只要报告，还是要**自动优化落盘**？
4. 是否允许 `--aggressive` 高风险改写？

> **接下来读什么**：想了解标准执行流程 → `## Workflow`；想直接看输入输出样例 → `## 示例（Few-shot）`。

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
# 静态完整性检查（引用是否存在 / frontmatter / 代码围栏 / 锚点）
python3 <skill_dir>/scripts/skill_tester.py <target> --run > <target>/.skill-audit/testplan.json
# 或仅生成边界/准确性用例（不跑静态检查）
python3 <skill_dir>/scripts/skill_tester.py <target> --plan-only > <target>/.skill-audit/testplan.json
```

`skill_tester.py` runs two layers:

1. **Static integrity tests (fully automated, high value):** every `scripts/`, `references/`,
   `assets/` path referenced in SKILL.md actually exists; examples are internally consistent;
   no broken internal anchors; frontmatter parses. These run by default and with `--run`.
2. **Test-plan generation:** derives boundary cases (empty input, oversized skill, missing
   optional args, ambiguous intent) and accuracy cases (does the skill do what its description
   claims?) from the skill's own description and examples. Always generated.

> **`--run` vs `--plan-only`**：`--run`（或默认无 flag）**执行**静态完整性检查并输出结果；
> `--plan-only` **只生成**边界/准确性用例，跳过静态检查。两者行为不同，请按需选用。

To actually execute the boundary/accuracy plan against a model, pass `--model-config config.json`
along with `--run` (or default); otherwise the plan is emitted with `manual` status for an agent
to execute (see Phase 3 execution note below). Boundary/accuracy results are recorded in
`testplan.json` as `pass | fail | manual`.

> **Phase 3 execution note:** True output testing requires loading the target skill into a
> model session and running each case. When a case is `manual`, the agent should: read
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

Assemble the final deliverable from `assets/report_template.md` (a small `{{placeholder}}`
/ `{% for %}` template) using the artifacts collected in Phases 1–4:

```bash
python3 <skill_dir>/scripts/build_report.py <target> --out <target>/.skill-audit/REPORT.md
```

`build_report.py` reads `audit.json` / `semantic.json` / `trace.json` / `testplan.json` plus the
optional `optimization-report.md`, renders the template, and writes `REPORT.md`. The report contains:

- Skill identity (name, path, scope).
- TRACE scorecard table (5 dimensions + overall, with prior-vs-after if available).
- Top findings by severity, each with rule_id, location, evidence, recommendation.
- Testing summary (static pass rate + manual-case outcomes).
- Before/after diff excerpt for applied optimizations.
- Configurable next-step suggestions.

Write the report to `<target>/.skill-audit/REPORT.md` and present it.

> **接下来读什么**：想照着实例跑一遍 → `## 示例（Few-shot）`；想自己配置规则/权重 → `## Configuration`。

## 示例（Few-shot）

为降低使用差异、提升稳定性，以下给出三类核心流程的输入/输出骨架。

### 示例 1 · 审查（Audit）

- **用户输入**："审查一下 ~/.workbuddy/skills/foo"
- **技能动作**：Phase 0–1 → `audit.json` + `semantic.json` 合并；输出结构/提示词/效率 + 语义发现清单（按严重度）。
- **关键产出**：如 `STRUCT-013 文档/脚本参数不一致`、`SEM-003 术语混用`、`EFF-001 重复块`。

### 示例 2 · TRACE 评测

- **用户输入**："给这个 Skill 做个 TRACE 评测"
- **技能动作**：Phase 2 → `trace.json`；五维加权 0–100，最弱维度优先。
- **关键产出**：`总分 92.0 / A`，维度表 + 每条证据。

### 示例 3 · 优化（Optimize）

- **用户输入**："把这个 Skill 的提示词冗余合并一下，先给我看看"
- **技能动作**：Phase 4 → `--dry-run` 预览 diff；用户确认后再 `--out` 落盘 + `.bak` 备份。
- **关键产出**：修改前/后对比 + 统一 diff，全部可回退。

## Configuration

All extensibility lives in a JSON config (copy `assets/config.example.json` to
`<target>/.skill-audit/config.json` and edit):

- `rules`: enable/disable audit rules by `rule_id`, set per-rule severity thresholds.
- `weights`: override TRACE dimension weights (must sum to 1.0).
- `strategies`: toggle which optimization strategies run, and whether `--aggressive` is allowed.
- `thresholds`: length/duplication/consistency numeric cutoffs.

Pass `--config <path>` to any script that supports it (`audit_skill.py`, `trace_eval.py`,
`optimize_apply.py`).

> **接下来读什么**：想扩展自定义规则 → `## Extensibility`；遇到具体问题 → `## 常见问题 FAQ` 或独立 `FAQ.md`。

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
| `audit_skill.py` | Structure / prompt-quality / efficiency audit | `--json`, `--config` |
| `semantic_analyzer.py` | Redundancy, terminology, conflict detection | `--json`, `--min-sentence-len` |
| `trace_eval.py` | TRACE 5-dimension scoring | `--json`, `--config`, `--prior trace.json` |
| `skill_tester.py` | Static integrity + test-plan generation | `--plan-only`, `--run`, `--model-config`, `--merge-results` |
| `optimize_apply.py` | Apply safe optimizations + diff + report | `--dry-run`, `--aggressive`, `--out`, `--config` |
| `build_report.py` | Assemble Phase 5 REPORT.md from artifacts | `--out`, `--config` |

All scripts are Python 3.9+ stdlib-only. No network or external packages required for
audit / semantic / TRACE / static-test phases.

## References / Assets 引用

| 任务 | 需要加载的 references | 需要使用的 assets |
|------|---------------------|------------------|
| 结构/提示词/效率审查 | audit-rules.md | config.example.json |
| 提示词语义分析 | prompt-semantic-analysis.md | — |
| TRACE 五维评测 | trace-framework.md | — |
| 安全自动优化 | optimization-strategies.md | report_template.md |
| 自定义规则/策略/权重/术语簇 | （任意自定义模块） | config.example.json, model-config.example.json |
| 查常见问题/反模式 | FAQ.md | — |
| 照案例执行 | COOKBOOK.md | — |

加载策略：默认随脚本自动读取所需 reference；自定义扩展走 `config.custom_rules_module` / `config.custom_strategies_module`。

> **接下来读什么**：还在入门 → `FAQ.md`；想照着做 → `COOKBOOK.md`。

## 常见问题 FAQ

**Q1：它会直接改我的 Skill 吗？**
A：默认只出报告 + dry-run 预览；真正落盘需你显式确认，且每次改动保留可逆 diff 与 `.bak` 备份，绝不静默覆盖。

**Q2：支持哪些框架的 Skill？**
A：任何基于 `SKILL.md` 的 Skill（WorkBuddy、OpenClaw 等通用规范）。非标准布局会自动降级处理（见能力边界）。

**Q3：TRACE 分数怎么看？**
A：五个维度加权 0–100，附证据。最弱维度 = 最高杠杆的改进点；等级参考 A(≥90) / B(75–89) / C(60–74) / D(<60)。

**Q4：自动优化会不会改坏？**
A：不会。`OPT-TERM-UNIFY` 有三重保护（标题行 / 英文句首 / 列表·引用·序号行首不降级），原则是"宁可少改不可改坏"；高风险改写默认仅建议。

**Q5：我的 Skill 内容会泄露吗？**
A：不会。审计/语义/TRACE/静态测试全部本地运行，无网络、无外部依赖；仅"模型测试"阶段需你显式提供 `--model-config`，且该步可完全跳过。

**Q6：想自定义规则 / 权重 / 术语簇？**
A：复制 `assets/config.example.json` 到 `<target>/.skill-audit/config.json` 即可，无需改代码；术语簇见 `config.term_clusters`。

**Q7：能用来给 Skill 自己做质量自检吗？**
A：能。对 skill-auditor 自身跑一遍 Phase 0–5 即是一次完整自检（本仓库 `.skill-audit/REPORT.md` 即实例）。

**Q8：报错信息里出现了错误码（如 E_TOO_LARGE），该怎么办？**
A：每个错误码都附带"下一步"建议。例如 `E_TOO_LARGE` 表示 SKILL.md 超过 512 KB，建议把细节移到 `references/`；`E_NO_SKILL_MD` 表示路径不对。按提示操作即可，无需翻源码。

**Q9：我的 SKILL.md 很大（几千行），会不会卡住？**
A：不会。正文超过 5 万词或 SKILL.md 超过 512 KB 时，语义分析会自动进入"采样模式"：只分析前 2000 句，跳过全量 O(n²) 检查，并产出提示告诉你降级了。

**Q10：完整测试一定要配 `--model-config` 吗？**
A：不是必须的。静态完整性测试（引用是否存在、frontmatter 是否合法、代码围栏是否配对等）零配置即可跑；只有"把测试用例交给真实模型执行"这一步才需要 `--model-config`，且可以跳过。

**Q11：语义分析报"疑似冲突指令"，但其实是正常说明，怎么办？**
A：skill-auditor 对冲突指令加了"请人工复核"提示，不会直接改写。你可以在 `config.json` 里把 `SEM-004` 的 severity 调低或关闭，也可忽略该建议。

**Q12：想快速提升 TRACE 分数，应该先看哪个维度？**
A：看总分最低的那个维度。通常优先级：R（可靠性，边界处理/错误说明）> T（安全可信）> E（有效性，描述与能力一致）> A（适用性，配置/扩展）> C（规范性，结构/示例）。具体修复清单见审计报告。

**Q13：加载时提示「不支持的文件类型：.gitignore / LICENSE」怎么办？**
A：这是 Skill 宿主跳过仓库元数据文件的正常提示，不影响 Skill 运行。`.gitignore` 建议保留；`LICENSE` 可改名为 `LICENSE.md` 以避免提示。skill-auditor 会标记为 `STRUCT-014`（low），不强制修复。详见 `FAQ.md` Q13。
