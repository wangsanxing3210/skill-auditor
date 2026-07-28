# 审查规则目录（Audit Rule Registry）

本文件是 `audit_skill.py` 与 `semantic_analyzer.py` 的规则清单。规则分三类：
**structure（结构）**、**prompt（提示词质量）**、**efficiency（执行效率）**，另由
`semantic_analyzer.py` 负责 **semantic（语义）** 类。每条规则有稳定 `rule_id`、默认
`severity`、所属 `category` 与 `check` 来源。

规则可在 `config.json` 的 `rules` 段按 `rule_id` 启停或调级：

```json
{
  "rules": {
    "STRUCT-001": {"enabled": true, "severity": "high"},
    "PROMPT-007": {"enabled": false},
    "EFF-003": {"enabled": true, "severity": "medium"}
  }
}
```

## structure（结构）

| rule_id | 名称 | severity | 检查 |
|---------|------|----------|------|
| STRUCT-001 | frontmatter 存在且可解析 | high | YAML 头存在、能被解析 |
| STRUCT-002 | 必填字段 name 存在 | high | frontmatter 含 name |
| STRUCT-003 | 必填字段 description 存在且非空 | high | frontmatter 含 description |
| STRUCT-004 | agent_created 标记（可修改性） | low | frontmatter 含 agent_created:true |
| STRUCT-005 | description 含触发场景（WHEN） | medium | description 含"当…/用于…/触发"类表述 |
| STRUCT-006 | description 用第三人称 | medium | 非"You should/你应该"开头 |
| STRUCT-007 | 引用脚本真实存在 | high | SKILL.md 提到的 scripts/*.py 文件存在 |
| STRUCT-008 | 引用参考真实存在 | high | SKILL.md 提到的 references/*.md 存在 |
| STRUCT-009 | 引用资产真实存在 | medium | SKILL.md 提到的 assets/* 存在 |
| STRUCT-010 | 目录结构合规 | low | 含 scripts/references/assets（按需） |
| STRUCT-011 | 无中文/空格路径问题 | low | 路径 ASCII 安全 |
| STRUCT-012 | 指令用祈使/不定式 | medium | 正文以动词开头，非第二人称 |
| STRUCT-013 | 文档/脚本参数一致 | high | SKILL.md 演示的 `--flag` 在对应 `scripts/*.py` 中确有 `add_argument` 声明 |

## prompt（提示词质量）

| rule_id | 名称 | severity | 检查 |
|---------|------|----------|------|
| PROMPT-001 | 触发词清晰 | medium | 列出可触发该技能的用户表述 |
| PROMPT-002 | 角色/目标明确 | medium | 开头说明"这个技能做什么" |
| PROMPT-003 | 示例覆盖关键场景 | medium | 至少 1 个可执行示例 |
| PROMPT-004 | 长度卫生 | low | SKILL.md ≤ 5k 词（超则建议外置） |
| PROMPT-005 | 无空 TODO 占位 | high | 不含 [TODO] 等未填占位 |
| PROMPT-006 | 无能力夸大 | medium | 无"100%/永远/绝对"等绝对化表述 |
| PROMPT-007 | 输出交付物明确 | medium | 说明产出物/成功判据 |
| PROMPT-008 | 无过时工具名/错误命令 | high | 引用的工具/命令真实存在 |
| PROMPT-009 | 指令无歧义 | medium | 同一动作无多种矛盾说法 |

## efficiency（执行效率）

| rule_id | 名称 | severity | 检查 |
|---------|------|----------|------|
| EFF-001 | 无大段重复文本块 | medium | 连续≥3 行重复出现≥2 次 |
| EFF-002 | 细节应外置未外置 | medium | 大段参考内容堆在 SKILL.md 内 |
| EFF-003 | 无死引用 | low | 提到的文件/章节锚点都存在 |
| EFF-004 | 步骤无冗余回路 | low | 无明显的重复步骤循环 |
| EFF-005 | 渐进式披露达标 | low | references 被按需引用而非全量 |

## semantic（语义，由 semantic_analyzer.py 负责）

| rule_id | 名称 | severity | 检查 |
|---------|------|----------|------|
| SEM-001 | 近义重复句 | medium | 两句话语义高度重叠（编辑距离/词袋重叠） |
| SEM-002 | 高频重复短语 | low | 同一短语出现≥N 次且可合并 |
| SEM-003 | 术语不一致 | medium | 同一概念用不同词（如 Skill/skill/技能混用） |
| SEM-004 | 冲突指令 | high | 前后给出相反的操作要求 |
| SEM-005 | 意图漂移 | low | 段落主题偏离技能声明的能力 |

## 严重度约定

- **high**：阻断发布，必须修复（如缺失 frontmatter、错误命令、冲突指令）。
- **medium**：显著影响质量，建议修复（如缺示例、术语不一致）。
- **low**：锦上添花，可后续处理（如目录结构、长度卫生）。

## 自定义规则

在 `config.json` 设置：

```json
{
  "custom_rules_module": "/abs/path/custom_rules.py"
}
```

`custom_rules.py` 需导出：

```python
def check(skill, ctx) -> list:
    # skill: dict{path, frontmatter, body, files}
    # ctx:   dict{config, thresholds}
    # 返回 [{"rule_id":"CUSTOM-001","severity":"medium","category":"structure",
    #        "location":"SKILL.md:42","evidence":"...","recommendation":"..."}]
    return []
```

`audit_skill.py` 在跑完内置规则后自动 import 并运行该模块。
