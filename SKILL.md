---
name: skill-auditor
version: 1.8.0
description: '用于审查、评测、测试、优化其他任何 Skill 的元技能（meta-skill），不限定具体工具框架，适用于 WorkBuddy、OpenClaw 等所有基于 SKILL.md 的 Skill。当用户需要审查/评测/优化某个 SKILL.md、评估技能质量、查找冗余或不一致的提示词、测试技能的边界情况、运行 TRACE 五维评测，或生成技能改动的前后对比报告时使用。触发方式包括：「审查这个 Skill」「优化 SKILL.md」「给这个 Skill 做个 TRACE 评测」「测一下这个技能的边界情况」「Skill 提示词冗余检测」「对比优化前后」「帮我看看这个 skill 写得怎么样」等。'
agent_created: true
---

# Skill Auditor（元 Skill：审查 · 评测 · 优化）

> **纯本地 · 零网络依赖 · 零配置 · 全中文界面 · 下载即用**
> 审计 / 评测 / 测试 / 优化全部在本机完成，不上传你的 Skill 内容，不访问外网；审查、语义分析、TRACE 评分、静态测试无需任何模型或网络配置；只有"模型输出测试"是可选且完全可跳过的高级配置。
> 一条命令拿到完整报告：`python3 scripts/run_all.py <skill_dir>` 自动跑完 审计 → 语义 → TRACE → 测试 → 报告，生成 `.skill-audit/REPORT.md`。
> 本 Skill 引用的 `references/`、`assets/` 均为自带文件，离线可读，不依赖任何外部链接。

## Overview

这是一个**把其他 Skill 当作分析对象**的元技能——框架无关，适用于任何基于 `SKILL.md` 的 Skill（WorkBuddy、OpenClaw 及类似工具）。它会审查目标 Skill 的**逻辑结构、提示词质量、执行效率**，运行自动化**测试**（输出准确性与边界用例），并基于审计与测试结果给出具体的**改进建议**，还能**自动应用**安全的优化。所有结果最终渲染为一份**优化前后对比报告**。

质量基准是 **SkillHub TRACE 评测体系**，共五个维度——**T**rust（可信任度）、**R**eliability（可靠性）、**A**daptability（适用性）、**C**onvention（规范性）、**E**ffectiveness（有效性）。详见 `references/trace-framework.md`。

本技能自带**可扩展的审计规则库**和**可配置的优化策略**（见 `references/audit-rules.md` 与 `references/optimization-strategies.md`），因此规则集与自动优化行为可以在不改代码的前提下调整。

> **安全与伦理声明**：全部分析在本地完成，不联网、不上传你的 Skill 内容；自动优化始终保留可逆 diff 与 `.bak` 备份，绝不静默覆盖。仅"模型测试"阶段需你显式提供 `--model-config`，且该步可完全跳过。

## 触发词速查卡（场景 → 说法 → 执行阶段）

| 场景 | 你可以直接这样说 | 适用人群 / 行业例子 | 它会执行的阶段 |
|------|----------------|---------------------|---------------|
| 审查 | "审查一下 ~/.workbuddy/skills/foo" / "帮我看看这个 Skill 写得怎么样" | 工具型、教学型 Skill 作者（发布前自查） | Phase 0–1 |
| 评测 | "给这个 Skill 做个 TRACE 评测" / "评一下质量" / "看看能得几分" | 要上架应用市场的作者（品牌/文案/知识型 Skill 也适用） | Phase 2 |
| 测试 | "测一下这个技能的边界情况" / "空输入/大文件会怎样" / "会不会崩" | 面向真实用户的工具型 Skill（可靠性优先） | Phase 3 |
| 优化（预览） | "把提示词里重复的地方合并一下，先给我看看" / "我想优化但别直接改" | 任何想改但怕改坏的作者 | Phase 4 dry-run |
| 优化（落盘） | "确认优化" / "就按这个改" / "apply" | 看过预览、确认无误后 | Phase 4 apply |
| 报告 | "对比优化前后改了什么" / "给我一份 REPORT.md" | 需要给团队/客户交付审查结论的人 | Phase 5 |
| 自动化 / 批量 | "把所有 skills 都审一遍" / CI 里想直接调用 | 维护多个 Skill 的团队负责人、流水线脚本 | 全流程（`run_all.py <skill>` 一条命令） |

> **不知道怎么开口？** 从这三个字开始：**「审」**（审查这个 skill）、**「修」**（帮我优化）、**「比」**（对比优化前后）。说完 skill-auditor 会追问路径和细节，你只需要回答。
> 提示：不需要记特殊命令，用自然语言描述意图即可；skill-auditor 会先澄清模糊点再动手（参见「能力边界与异常处理 → 澄清问卷」）。

## 目录

- [Overview](#overview)
- [触发词速查卡（场景 → 说法 → 执行阶段）](#触发词速查卡场景-说法-执行阶段)
- [30 秒快速开始（端到端 3 步：一条命令拿到 REPORT.md）](#30-秒快速开始端到端-3-步一条命令拿到-reportmd)
- [什么时候用（When To Use）](#什么时候用when-to-use)
- [能力边界与异常处理](#能力边界与异常处理)
- [设计原则（Design Principles）](#设计原则design-principles)
- [工作流程（Workflow）](#工作流程workflow)
- [示例（Few-shot）](#示例few-shot)
- [配置（Configuration）](#配置configuration)
- [扩展（Extensibility）](#扩展extensibility)
- [输出产物（Output Artifacts）](#输出产物output-artifacts)
- [脚本速查（Scripts Reference）](#脚本速查scripts-reference)
- [References / Assets 引用](#references-assets-引用)
- [常见问题 FAQ](#常见问题-faq)
- [反模式](#反模式)

配套文档：`FAQ.md`（12 条问答 + 反模式表）、`COOKBOOK.md`（3 个完整场景 + 自然语言使用速查）。

## 30 秒快速开始（端到端 3 步：一条命令拿到 REPORT.md）

```bash
# 1. 进入待审 Skill（示例：~/.workbuddy/skills/foo）
cd ~/.workbuddy/skills/foo

# 2. 一条命令跑完 审计 → 语义 → TRACE → 测试 → 报告（无需任何配置）
python3 ~/.workbuddy/skills/skill-auditor/scripts/run_all.py .

# 3. 查看报告（按严重度排序的发现 + TRACE 五维评分 + 测试结论 + 覆盖度）
cat .skill-audit/REPORT.md
```

第一次用，记住三件事：

1. **怎么启动**：直接对某个 Skill 说"审查这个 Skill""给这个 Skill 做个 TRACE 评测""测一下这个技能的边界情况"，或"对比优化前后"；等价说法都能触发（见上方触发词速查卡）。
2. **你会得到什么**：一份结构化报告——审计发现（结构/提示词/效率）+ TRACE 五维评分 + 测试结论；需要时才出前后 diff。
3. **想改就改，但先看清**：优化默认只给建议与 dry-run 预览；真正落盘需你确认，且每次改动都可回退。

**零配置开箱可用**：`run_all.py .` 一条命令跑完所有阶段，审查、语义分析、TRACE 评测、静态测试、报告生成都不需要任何外部模型或网络，下载即用；只有"模型输出测试"才需要可选的 `--model-config`。

**离线自带，无需联网**：本 Skill 引用的所有 `references/`、`assets/` 均为自带文件，离线可读，不依赖任何外部链接。

**稳定性与资源保护**：SKILL.md 超过 512 KB 或正文超过 3 万词 / 3000 句时，语义分析自动采用"重点段深扫 + 全文浅扫兜底"（术语、冲突、短语、意图漂移对全文执行，近义句重复在开头/中间/结尾重点段深扫），覆盖区间会写入报告；所有错误都会给出明确的"原因 + 下一步操作建议"，不会直接崩溃。

> **新手推荐阅读路径**：`## 能力边界与异常处理` → `## 示例（Few-shot）` → 需要完整场景案例看 `COOKBOOK.md` → 遇到卡点查 `FAQ.md` → 自定义看 `## 配置`。

## 什么时候用（When To Use）

- 发布前或收到反馈后，审查一个 Skill（"帮我看看这个 Skill 写得怎么样"）。
- 优化一个已经臃肿或不一致的 SKILL.md（"把提示词里重复的地方合并一下"）。
- 为 Skill 库 / 应用市场提交跑一次 TRACE 评分卡。
- 测试一个 Skill 的健壮性（"这个 Skill 在空输入 / 超大输入下会怎样"）。
- 生成 Skill 改动的可对比前后报告（"对比优化前后改了什么"）。
- 对自己的 Skill 做质量自检（用 skill-auditor 审 skill-auditor 自身）。

## 能力边界与异常处理

### 能力边界（三栏表）

| 类别 | 范围 | 处理原则 |
|------|------|----------|
| 能做 | 审查 / 评测 / 测试 / 安全优化任何基于 `SKILL.md` 的 Skill（WorkBuddy、OpenClaw 等框架通用） | 直接执行 Phase 0–5 标准流程 |
| 不做 | ①改写目标 Skill 的领域业务逻辑 ②处理二进制/非文本资源 ③保证某个评分或"一定通过" ④访问私有仓库或外发内容 | 明确告知不适用，不强行执行 |
| 降级做 | ①布局非标准（无 scripts/ 等约定目录）→ 仅审 SKILL.md 正文并标注缺失 ②脚本缺失 → 跳过对应检查并提示 ③未知框架 → 仍解析 `SKILL.md` 本体，按通用规则评测 ④超大文件（>3 万词 / 3000 句）→ 全文浅扫兜底 + 重点段深扫，不丢失检查项，覆盖区间写入报告 | 优雅降级，不拒答但标注假设与边界 |

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

> **接下来读什么**：想了解标准执行流程 → `## 工作流程`；想直接看输入输出样例 → `## 示例（Few-shot）`。

## 设计原则（Design Principles）

1. **先审计，再改动。** 任何修改都必须在产出发现之后进行；优化源自证据，而非主观偏好。
2. **默认安全。** `optimize_apply.py` 默认只应用*可逆、低风险*的改写（去重、frontmatter 补全、章节补全、措辞归一），除非显式传入 `--aggressive`。高风险改写只报告、不落盘。
3. **尽可能确定性。** 结构、语义、TRACE 检查都以脚本运行（仅用标准库，无外部依赖），结果可复现、可对比。
4. **可扩展。** 新规则 = 配置文件里加一条；新策略 = 加一个策略块。常规扩展无需改代码。
5. **破坏性操作先确认、留后路。** 任何有副作用的操作（如 `--aggressive` 改写、`--out` 落盘、或发布/外发步骤）都必须先用 `--dry-run` 预览并显式确认。安全改写始终保留可逆 diff，失败可回退；绝不静默覆盖用户的 Skill。

## 工作流程（Workflow）

```
Phase 0  定位与解析   → 确定目标 Skill 目录，读取 SKILL.md 与附带资源
Phase 1  审计         → 结构 + 提示词质量 + 效率（audit_skill.py、semantic_analyzer.py）
Phase 2  TRACE 评测   → 五维评分卡（trace_eval.py）
Phase 3  自动化测试   → 静态完整性 + 边界/准确性用例（skill_tester.py）
Phase 4  建议与优化   → 汇总发现、应用安全修复、输出 diff（optimize_apply.py）
Phase 5  报告         → 优化前后对比（assets/report_template.md）
```

按顺序执行各阶段。每个阶段把 JSON 产物写入 `<target>/.skill-audit/`，供后续阶段和最终报告消费。

### Phase 0 — 定位与解析

解析出目标 Skill 目录（包含 `SKILL.md` 的那个文件夹）。如果用户指向的是单个文件，则取其父目录。记录完整路径，后续所有命令都基于它。

### Phase 1 — 审计

运行两个分析器并合并它们的发现：

```bash
python3 <skill_dir>/scripts/audit_skill.py <target> --json > <target>/.skill-audit/audit.json
python3 <skill_dir>/scripts/semantic_analyzer.py <target>/SKILL.md --json > <target>/.skill-audit/semantic.json
```

- `audit_skill.py` 覆盖**结构**（frontmatter 合法性、必填字段、资源引用能否解析、命名规范）、**提示词质量**（触发词清晰度、指令形式、示例覆盖、长度卫生）、**效率**（重复块、应外置的超长内联内容、死引用）。
- `semantic_analyzer.py` 覆盖**提示词语义**：近义重复句、高频重复短语、术语不一致（同一概念不同写法）、冲突指令。详见 `references/prompt-semantic-analysis.md`。

合并规则：并集合并；按 `(rule_id, location)` 去重。

### Phase 2 — TRACE 评测

```bash
python3 <skill_dir>/scripts/trace_eval.py <target> --json > <target>/.skill-audit/trace.json
```

每个维度产出 0–100 分加一个加权总分，每项分数都附证据。方法与权重在 `references/trace-framework.md`。用分数决定先修哪些发现（最低维度 = 最高杠杆）。

### Phase 3 — 自动化测试

```bash
# 静态完整性检查（引用是否存在 / frontmatter / 代码围栏 / 锚点）
python3 <skill_dir>/scripts/skill_tester.py <target> --run > <target>/.skill-audit/testplan.json
# 或仅生成边界/准确性用例（不跑静态检查）
python3 <skill_dir>/scripts/skill_tester.py <target> --plan-only > <target>/.skill-audit/testplan.json
```

`skill_tester.py` 分两层：

1. **静态完整性测试（全自动、高价值）**：SKILL.md 中引用的每个 `scripts/`、`references/`、`assets/` 路径真实存在；示例内部一致；内部锚点无死链；frontmatter 可解析。默认与 `--run` 都会执行。
2. **测试用例生成**：从技能自身的描述与示例推导边界用例（空输入、超大 Skill、缺失可选参数、歧义意图）和准确性用例（技能是否真的做了 description 声称的事）。始终生成。

> **`--run` vs `--plan-only`**：`--run`（或默认无 flag）**执行**静态完整性检查并输出结果；
> `--plan-only` **只生成**边界/准确性用例，跳过静态检查。两者行为不同，请按需选用。

把边界/准确性用例交给真实模型执行时，传入 `--model-config config.json` 配合 `--run`（或默认）；
否则用例以 `manual`（待人工执行）状态输出，供 agent 按下面的"Phase 3 执行说明"处理。
边界/准确性结果在 `testplan.json` 中记录为 `pass | fail | manual`。

> **Phase 3 执行说明**：真正的输出测试需要把目标 Skill 载入一个模型会话并逐个跑用例。
> 当某个用例状态是 `manual` 时，agent 应该：读取 `testplan.json`，在沙箱中调用目标 Skill
> 执行 `manual` 用例（或对其指令进行推理），把 `pass/fail` 和证据写回，然后重跑
> `skill_tester.py --merge-results` 把结果并入报告。

### Phase 4 — 建议与自动优化

把 Phase 1–3 的发现汇总成单个 `findings.json`，再做优化：

```bash
# 先 dry-run 预览（显示会改什么，不写盘）
python3 <skill_dir>/scripts/optimize_apply.py <target> \
    --findings <target>/.skill-audit/findings.json --dry-run

# 应用安全优化 + 写 diff + 前后对比报告
python3 <skill_dir>/scripts/optimize_apply.py <target> \
    --findings <target>/.skill-audit/findings.json \
    --out <target>/.skill-audit/optimization-report.md
```

`optimize_apply.py` 把每条发现映射到一个策略（见 `references/optimization-strategies.md`），
默认只应用**可逆**改写。它写出一份统一 diff 和一份可读的前后对比报告。要应用更高风险的改写，
请传 `--aggressive`（提交前务必先看 diff）。

如果用户只想要建议（不改动），在 dry-run 后停下，直接呈现发现 + TRACE 分数即可。

### Phase 5 — 报告

用 Phase 1–4 收集的产物，通过 `assets/report_template.md`（一个小的 `{{placeholder}}` / `{% for %}` 模板）组装最终交付物：

```bash
python3 <skill_dir>/scripts/build_report.py <target> --out <target>/.skill-audit/REPORT.md
```

`build_report.py` 读取 `audit.json` / `semantic.json` / `trace.json` / `testplan.json` 以及
可选的 `optimization-report.md`，渲染模板，写出 `REPORT.md`。报告包含：

- Skill 身份（名称、路径、作用域）。
- TRACE 评分卡表格（5 个维度 + 总分，有历史分数时带前后对比）。
- 按严重度排序的 Top 发现，每条含 rule_id、位置、证据、建议。
- 测试小结（静态通过率 + manual 用例结论）。
- 已应用优化的前后 diff 摘录。
- 可配置的下一步建议。

把报告写到 `<target>/.skill-audit/REPORT.md` 并呈现给用户。

> **接下来读什么**：想照着实例跑一遍 → `## 示例（Few-shot）`；想自己配置规则/权重 → `## 配置`。

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

### 示例 4 · 多轮澄清（用户模糊 → 追问 → 执行）

当你的需求信息不完整时，skill-auditor 会先问、再动手，而不是默认猜：

- **用户**："帮我看看这个 skill"（没说哪个 skill）
- **技能**："可以。请告诉我 Skill 的目录路径（带 SKILL.md 的那个）——也可以直接说 ~/.workbuddy/skills/xxx 这样的相对路径。"
- **用户**："那你看下 foo 吧，顺便优化一下"
- **技能**："好的。是要先 dry-run 预览差异再让你确认，还是我直接落盘？另外 foo 是 user scope 还是 project scope？"
- **用户**："先预览，user scope"
- **技能动作**：Phase 1 + Phase 4 dry-run；输出 diff 摘要等用户确认。

### 示例 5 · 自审自优（skill-auditor 审计自身）

- **用户输入**："skill-auditor 自己有没有隐藏 bug？"
- **技能动作**：对自身跑 Phase 0–5（标准自检流程）。
- **关键产出**：本仓库 `.skill-audit/REPORT.md` 是一次自检实例，audit 仅报预期的 `STRUCT-014`（`.gitignore` 被宿主跳过），TRACE 仍 100.0 / A。
- **如何复现**：

  ```bash
  cd ~/.workbuddy/skills/skill-auditor
  python3 scripts/run_all.py .   # 一条命令拿到自审报告
  ```

## 配置（Configuration）

所有可扩展配置都在一个 JSON 文件里（把 `assets/config.example.json` 复制到
`<target>/.skill-audit/config.json` 再编辑）：

- `rules`：按 `rule_id` 启用/禁用审计规则，设置每条规则的严重度阈值。
- `weights`：覆盖 TRACE 各维度权重（必须归一化到 1.0）。
- `strategies`：开关优化策略，以及是否允许 `--aggressive`。
- `thresholds`：长度 / 重复 / 一致性的数值阈值。

对支持配置的脚本传 `--config <path>`（`audit_skill.py`、`trace_eval.py`、`optimize_apply.py`）。

> **接下来读什么**：想扩展自定义规则 → `## 扩展`；遇到具体问题 → `## 常见问题 FAQ` 或独立 `FAQ.md`。

## 扩展（Extensibility）

- **新增审计规则：** 在 `config.rules` 里加一个带新 `rule_id` 的条目，并通过 `config.custom_rules_module` 指向一个自定义检查模块（一个 Python 文件，导出 `def check(skill, ctx) -> list[Finding]`）。`audit_skill.py` 会导入并运行它。
- **新增优化策略：** 在 `config.strategies` 里加一个 `strategy_id` 块，并在 `config.custom_strategies_module` 引用的自定义模块中写对应 transform（导出 `def transform(skill, finding, ctx) -> (new_text, change_note)`）。
- **自定义 TRACE 权重 / 细则：** 编辑 `config.weights` 与 `config.trace_rubric`。

## 输出产物（Output Artifacts）

所有中间产物都落在 `<target>/.skill-audit/`：

```
.skill-audit/
  config.json          # 生效配置
  audit.json           # Phase 1 结构/提示词/效率发现
  semantic.json        # Phase 1 语义发现
  trace.json           # Phase 2 TRACE 评分卡
  testplan.json        # Phase 3 测试用例 + 结果
  findings.json        # 合并发现（Phase 4 输入）
  optimization-report.md  # Phase 4 前后对比 + diff
  REPORT.md            # Phase 5 最终交付物
```

## 脚本速查（Scripts Reference）

| 脚本 | 用途 | 关键参数 |
|------|------|----------|
| `run_all.py` | **一键全流程**：审计→语义→TRACE→测试→报告 | `<skill>`（推荐入口） |
| `audit_skill.py` | 结构 / 提示词质量 / 效率审计 | `--json`, `--config` |
| `semantic_analyzer.py` | 冗余、术语、冲突检测 | `--json`, `--min-sentence-len` |
| `trace_eval.py` | TRACE 五维评分 | `--json`, `--config`, `--prior trace.json` |
| `skill_tester.py` | 静态完整性 + 用例生成 + 启发式判定 | `--plan-only`, `--run`, `--no-model`, `--model-config`, `--merge-results` |
| `optimize_apply.py` | 安全优化 + diff + 报告 | `--dry-run`, `--aggressive`, `--out`, `--config` |
| `build_report.py` | 从产物汇编 Phase 5 的 REPORT.md | `--out`, `--config` |
| `diagnose.py` | 一键环境与 Skill 健康诊断 | （可带目标路径，`--json`） |

所有脚本都是 Python 3.9+ 标准库实现。审计 / 语义 / TRACE / 静态测试阶段无需网络或外部依赖。

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
A：不会。SKILL.md 超过 512 KB 时直接给出友好提示；正文超过 3 万词 或 3000 句时，语义分析自动采用"重点段深扫 + 全文浅扫兜底"——术语、冲突、短语、意图漂移对全文执行，近义句重复在开头/中间/结尾重点段深扫，覆盖区间会写入报告，不会丢失检查项。

**Q10：完整测试一定要配 `--model-config` 吗？**
A：不是必须的。静态完整性测试（引用是否存在、frontmatter 是否合法、代码围栏是否配对等）零配置即可跑；只有"把测试用例交给真实模型执行"这一步才需要 `--model-config`，且可以跳过。

**Q11：语义分析报"疑似冲突指令"，但其实是正常说明，怎么办？**
A：skill-auditor 对冲突指令加了"请人工复核"提示，不会直接改写。你可以在 `config.json` 里把 `SEM-004` 的 severity 调低或关闭，也可忽略该建议。

**Q12：想快速提升 TRACE 分数，应该先看哪个维度？**
A：看总分最低的那个维度。通常优先级：R（可靠性，边界处理/错误说明）> T（安全可信）> E（有效性，描述与能力一致）> A（适用性，配置/扩展）> C（规范性，结构/示例）。具体修复清单见审计报告。

**Q13：加载时提示「不支持的文件类型：.gitignore / LICENSE」怎么办？**
A：这是 Skill 宿主跳过仓库元数据文件的正常提示，不影响 Skill 运行。`.gitignore` 建议保留；`LICENSE` 可改名为 `LICENSE.md` 以避免提示。skill-auditor 会标记为 `STRUCT-014`（low），不强制修复。详见 `FAQ.md` Q13。

**Q14：常见的反模式有哪些？**
A：见下方「反模式」表（10 条 + 修复方向），以及 `FAQ.md` Q14 的"错误写法 vs 修复后"对照示例。

**Q15：能不能一次性审多个 Skill？**
A：可以。批量审查的最小脚本：

```bash
for d in ~/.workbuddy/skills/*/; do
  [ -f "$d/SKILL.md" ] && python3 ~/.workbuddy/skills/skill-auditor/scripts/run_all.py "$d"
done
```
每个 Skill 会在自己的 `.skill-audit/REPORT.md` 生成报告；汇总比较可用：

```bash
for d in ~/.workbuddy/skills/*/; do
  [ -f "$d/.skill-audit/trace.json" ] && \
    echo "$(basename $d): $(python3 -c "import json;print(json.load(open('$d/.skill-audit/trace.json'))['overall'])")"
done
```

**Q16：在哪能跟踪 skill-auditor 的版本变更？**
A：`CHANGELOG.md` 记录每次发布的功能改动、bug 修复与已知局限；当前版本见 `SKILL.md` frontmatter 的 `version` 字段；同步镜像在 GitHub `wangsanxing3210/skill-auditor`。

## 反模式

下表是评审中最常见的 10 类问题，每类给出**典型错误示例**、**为什么扣分**、**修复方向**与**真实修复案例**。详细对照见 `FAQ.md` Q14。

| # | 反模式 | 典型错误示例 | 为什么扣分 | 修复方向 | 真实修复案例 |
|---|--------|-------------|-----------|----------|-------------|
| 1 | description 没讲何时用 | "这是一个审查工具。" | C/E 低：评测者不知道什么时候该触发它 | 加 WHEN 触发场景 + 典型用户说法 | "当需要审查/评测/优化基于 SKILL.md 的 Skill 时使用" |
| 2 | 触发词只堆关键词 | "触发词：审查、评测、优化" | A 低：关键词堆叠不等于"一句话就能唤起" | 改成场景→说法→执行阶段映射表 | 本 Skill 的「触发词速查卡」（7 大场景 + 人话说法） |
| 3 | 边界处理只有口号 | "本技能能处理各种边界情况。" | R 低：无具体话术，等于没写 | 列空输入/超大/缺失的具体应对话术 | "能力边界与异常处理"三栏表 + 诊断→修复话术库 |
| 4 | 示例不可执行 | "运行脚本即可。" | R/C 低：示例无命令、无路径、无预期产出 | 用可复制的 ```bash 代码块 | 本 Skill 的 30 秒快速开始（run_all.py 一条命令 → cat REPORT.md） |
| 5 | 错误提示只有代码 | "E_TOO_LARGE" | R 低：非技术用户看不懂，也无下一步 | 用"原因 + 下一步"人话话术 | 本 Skill 的错误提示已升级为"原因 + 一键命令" |
| 6 | 文档全是命令行 | 全文只有 ```bash 代码块 | A/C 低：普通用户没有命令行习惯 | 加对话式使用场景速查 | COOKBOOK「自然语言使用速查」表 |
| 7 | 所有细节堆在正文 | SKILL.md 3000 行，references/ 为空 | C 低：渐进式披露失败，正文淹没读者 | 外置到 references/，正文只留流程 | 本 Skill 的 7 个脚本细节全部在 scripts/，正文只留用法 |
| 8 | 含"100% 准确""永远不会错" | "保证 100% 正确" | T 低：绝对化承诺不可验证 | 改成可验证表述 | "同类技能中重复率 < 1%"这种可测量说法 |
| 9 | 命令与脚本声明不一致 | 文档写 `--rules-only`，脚本没这参数 | R/C 低：照文档跑必报错 | 保持文档与代码一致（参考 STRUCT-013） | skill-auditor 曾自查出此类问题并修复 |
| 10 | 优化无备份无回退 | 直接覆盖原文件 | T/R 低：改坏了无法恢复 | 默认 dry-run + `.bak` 备份 + 统一 diff | 本 Skill 的优化流程：dry-run → 确认 → .bak + diff |
