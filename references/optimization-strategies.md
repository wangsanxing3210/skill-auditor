# 优化策略体系（Optimization Strategies）

优化策略把**审查发现（finding）**映射到**可执行的改写动作（transform）**。每个策略有
`strategy_id`、绑定的 `rule_ids`、风险等级（safe / aggressive）、以及动作描述。
`optimize_apply.py` 据此决定是否自动应用。

默认只应用 **safe** 策略；传入 `--aggressive` 才应用 aggressive 策略，且每次应用都写
unified diff 供人工复核。

## 策略清单

| strategy_id | 绑定规则 | 风险 | 动作 |
|-------------|----------|------|------|
| OPT-FRONTMATTER | STRUCT-001/002/003/004 | safe | 补全/修复 frontmatter（加 name/description/agent_created） |
| OPT-TRIGGER | PROMPT-001/005 | safe | 把 [TODO]、缺失的触发词补全为占位模板 |
| OPT-DEDUP-BLOCK | EFF-001 | safe | 删除连续重复文本块，保留一份 |
| OPT-SEM-DEDUP | SEM-001/002 | safe | 合并近义重复句 / 高频短语 |
| OPT-TERM-UNIFY | SEM-003 | safe | 统一术语（按 skill 内最高频写法归一） |
| OPT-REF-EXTERNALIZE | EFF-002 | safe | 将大段参考内容建议外置（写注释提示，不强制移动） |
| OPT-DEADREF-FIX | STRUCT-007/008/009, EFF-003 | safe | 修正/移除死引用路径 |
| OPT-PHRASE-NORMALIZE | PROMPT-006/009 | safe | 弱化绝对化表述、消除歧义措辞 |
| OPT-REWRITE-CONFLICT | SEM-004 | aggressive | 重写冲突指令，保留更安全/更合理的版本 |
| OPT-RESTRUCTURE | PROMPT-004, EFF-005 | aggressive | 将超长 SKILL.md 拆段外置到 references/ |
| OPT-EXAMPLE-ADD | PROMPT-003/007 | aggressive | 为缺失示例/交付物补写示例段落 |

## 安全约束（OPT-TERM-UNIFY 必读）

术语归一 `OPT-TERM-UNIFY` 看似无害，但**错误实现会降级文本**。在 round-2 自审中曾出现
把 `# Skill Auditor` 标题改写成 `# skill Auditor`、`- Skill identity` 列表项小写的误伤。
`optimize_apply.py` 的 `safe_replace` 因此内置三重保护，**任何归一动作都不能突破**：

1. **标题保护**：匹配所在行以 `#` 开头的，整行跳过（标题大小写属于规范写法）。
2. **句首保护**：英文句首大写的词（前为句末标点/换行/行首）跳过，不强制小写。
3. **列表/引用/序号行首保护**：去掉 `- ` / `* ` / `> ` / `N. ` 前缀后若为空，说明该词是
   行首项，跳过。

> 经验法则：**自动优化宁可少改，不可改坏。** 任何 safe 策略落盘前必须 `--dry-run` 人工复核
> diff；出现标题/专有名词被降级时，应判定为策略缺陷而非照单全收。

## 风险分级

- **safe**：可逆、低误伤。去重、补 frontmatter、统一术语、修路径——即便判断不完美，人工
  复核 diff 即可还原。默认自动应用。
- **aggressive**：会改写语义或结构，误伤成本更高。需显式 `--aggressive` 才执行，且必须
  在报告中展示前后对比，由用户确认。

## 配置开关

`config.json` 的 `strategies` 段控制每个策略：

```json
{
  "strategies": {
    "OPT-DEDUP-BLOCK": {"enabled": true, "risk": "safe"},
    "OPT-SEM-DEDUP":   {"enabled": true, "risk": "safe"},
    "OPT-REWRITE-CONFLICT": {"enabled": true, "risk": "aggressive"},
    "OPT-RESTRUCTURE": {"enabled": false, "risk": "aggressive"},
    "allow_aggressive": false
  }
}
```

`allow_aggressive=false` 时，即便命令行传 `--aggressive` 也会被策略层拦下（双保险）。

## 自定义策略

```json
{
  "custom_strategies_module": "/abs/path/custom_strategies.py"
}
```

`custom_strategies.py` 导出：

```python
def transform(skill, finding, ctx):
    # 返回 (new_text: str, change_note: str)
    # new_text 为整份 SKILL.md（或对应文件）改写后的完整文本
    return skill["body"], "no-op"
```

`optimize_apply.py` 对每条绑定到该策略的 finding 调用 `transform`，并在应用前生成 diff。

## 应用流程（optimize_apply.py 内部）

1. 读 `findings.json`，按 `rule_id` → `strategy_id` 分组。
2. 对每个 finding：查策略，若 `enabled` 且（risk=safe 或 allow_aggressive）则执行 transform。
3. 执行前对原文件生成快照；执行后 `difflib.unified_diff` 生成补丁。
4. 写入 `optimization-report.md`（含前后对照 + 每条 change_note）。
5. 默认 `--dry-run` 只输出将要发生的改动，不落盘。
