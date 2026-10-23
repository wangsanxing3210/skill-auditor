# SkillHub TRACE 评测体系

TRACE 是评估一个 Skill 质量的五维框架（适用于任何基于 SKILL.md 的 Skill）。每个维度独立打分（0–100），再按权重合成
总分。分数背后必须有**可复核的证据**（来自 `audit_skill.py` / `semantic_analyzer.py` /
`skill_tester.py` 的输出），避免主观打分。

## 维度定义

| 维度 | 英文 | 含义 | 关注问题 |
|------|------|------|----------|
| T | Trust（可信任度） | 技能是否安全、可信、无隐患 | 会不会泄露密钥？会不会执行危险操作？有没有误导性声明？ |
| R | Reliability（可靠性） | 技能在各类输入下是否稳定可预期 | 边界输入会不会崩？错误处理是否到位？示例是否可执行？ |
| A | Adaptability（适用性） | 技能对场景/参数/扩展的适配能力 | 能否配置？能否扩展规则？能否覆盖变体场景？ |
| C | Convention（规范性） | 是否符合 Skill 编写规范 | frontmatter 合规吗？命名规范吗？指令用祈使句吗？ |
| E | Effectiveness（有效性） | 技能是否真的能达成目标 | 描述与能力一致吗？指令是否可操作？有无可衡量产出？ |

## 权重（默认）

```
T: 0.22
R: 0.24
A: 0.18
C: 0.18
E: 0.18
```
合计 1.00。可通过 `config.weights` 覆盖（必须归一化到 1.0）。

> 设计理由：Reliability 权重最高——一个在边界情况下崩溃的技能危害最大；
> Trust 次之——安全是底线。Adaptability / Convention / Effectiveness 各 0.18，
> 属于"好技能应有的素质"，但不及稳定与安全关键。

## 评分方法（每维度 0–100）

每个维度由若干**指标（metric）**组成，指标分三档：

- `pass`（满分）：明确满足
- `partial`（半分）：部分满足 / 有保留
- `fail`（0 分）：缺失或反向

维度得分 = Σ(metric_weight × metric_score) / Σ(metric_weight)，metric_score ∈ {0, 0.5, 1}。

### T — Trust 指标

| metric_id | 指标 | 检查来源 |
|-----------|------|----------|
| T1 | 无硬编码密钥 / token / 明文凭证 | semantic + grep 扫描 |
| T2 | 外部副作用有确认/风险提示（删除/外发/付费前警示） | SKILL.md 文本 |
| T3 | 无夸大或虚假声明（"100% 准确"等） | SKILL.md 文本；**三类豁免**：代码块/行内代码、引号内引用（「」“”""）、教材或禁止语境行（反模式/示例/不要/禁止/avoid），外加技术术语豁免（绝对路径、绝对化承诺）。豁免是为区分"自己的承诺"与"引用别人的说法" |
| T4 | 隐私/数据安全说明到位（涉及个人文件时） | SKILL.md 文本 |
| T5 | 引用来源可溯（真实 `http(s)` 链接，或 `references/<file>` 文件引用；仅出现"参考"二字不计分） | SKILL.md 文本 |

### R — Reliability 指标

| metric_id | 指标 | 检查来源 |
|-----------|------|----------|
| R1 | frontmatter 可解析、必填字段齐全 | audit_skill |
| R2 | 引用的脚本/参考/资产文件真实存在 | skill_tester 静态 |
| R3 | 有真实错误处理指令（try/except、if 失败、fallback、回退到 X、捕获异常等；仅出现"错误"二字不计满分） | SKILL.md 文本 |
| R4 | 示例自洽、可被直接执行 | skill_tester |
| R5 | 边界输入有应对：**具名边界场景**（空/超大/缺失参数等）**或** `skill_tester` 实际生成了 boundary 用例 | skill_tester 边界用例 |
| R6 | 指令无歧义、无内部冲突 | semantic_analyzer |

### A — Adaptability 指标

| metric_id | 指标 | 检查来源 |
|-----------|------|----------|
| A1 | 支持配置（显式 `--config` 或 `config.json` 引用；仅出现"配置"二字不计分） | SKILL.md + config |
| A2 | 规则/策略可扩展（真实钩子 `custom_rules_module` / `custom_strategies_module`；仅出现"扩展"二字不计分） | SKILL.md 文本 |
| A3 | 覆盖变体场景（多触发词/多任务分支） | SKILL.md 文本 |
| A4 | 资源用 references/assets 外置，不堆砌正文 | audit_skill 效率 |

### C — Convention 指标

| metric_id | 指标 | 检查来源 |
|-----------|------|----------|
| C1 | frontmatter 含 name/description/agent_created | audit_skill |
| C2 | description 含 WHEN 触发场景、第三人称 | audit_skill |
| C3 | 指令用祈使/不定式（非第二人称） | audit_skill |
| C4 | 目录结构符合 scripts/references/assets | audit_skill |
| C5 | 文件命名/无中文路径问题 | audit_skill |
| C6 | 渐进式披露（SKILL.md 精简，细节外置） | audit_skill 长度 |

### E — Effectiveness 指标

| metric_id | 指标 | 检查来源 |
|-----------|------|----------|
| E1 | description 与实际能力一致（无能力漂移） | skill_tester 准确性用例 |
| E2 | 指令可操作（含带命令的代码围栏 + 动作动词"运行/执行"等；仅出现动词不计满分） | SKILL.md 文本 |
| E3 | 有关键场景示例 / 工作流 | SKILL.md 文本 |
| E4 | 可衡量交付物（专属 Output/Deliverables 标题，或 verbatim 交付物清单如 `*.json`/`.skill-audit/`；仅出现"报告"二字不计满分） | SKILL.md 文本 |

## 等级映射

| 总分 | 等级 | 含义 |
|------|------|------|
| 90–100 | A | 可直接发布/上架 |
| 75–89 | B | 良好，建议小幅优化 |
| 60–74 | C | 可用，但有明显短板，需优化 |
| < 60 | D | 不达标，须大修 |

任一维度 < 50 即视为"关键短板"，无论总分多少都应在报告中置顶提示。

## 证据链

`trace_eval.py` 的输出 JSON 结构：

```json
{
  "overall": 78.4,
  "grade": "B",
  "dimensions": {
    "T": {"score": 90, "metrics": {"T1": 1, "T2": 0.5, "T3": 1, "T4": 1, "T5": 0.5}},
    "R": {"score": 72, "metrics": {"R1": 1, "R2": 1, "R3": 0.5, "R4": 1, "R5": 0, "R6": 1}},
    "A": {"score": 70, "metrics": {...}},
    "C": {"score": 85, "metrics": {...}},
    "E": {"score": 75, "metrics": {...}}
  },
  "weakest_dimension": "R",
  "critical_gaps": ["R5"],
  "evidence": { "R5": "skill_tester: 未声明超大 SKILL.md(>5k 词) 的处理策略" }
}
```

把 `--prior trace.json` 传入时，`trace_eval.py` 会同时输出 `delta`（本次相对上次的提升），
供优化前后对比报告使用。
