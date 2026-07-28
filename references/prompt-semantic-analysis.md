# 提示词语义分析方法论（Prompt Semantic Analysis）

`semantic_analyzer.py` 在 SKILL.md 正文上做语言学层面的检查，补充结构审查看不到的"软问题"：
重复、不一致、冲突、漂移。所有检查均为确定性启发式（无模型调用），结果可复现。

## 1. 近义重复句检测（SEM-001）

**目标**：找出语义高度重叠的两句话，避免啰嗦与前后重复强调。

**方法**：
1. 按句子切分（以 `。！？.!?` 及换行分隔），过滤掉标题行（以 `#` 开头）与代码块。
2. 对每句做词袋（去停用词、ASCII 小写），计算 Jaccard 相似度与编辑距离占比。
3. 相似度 ≥ `thresholds.dup_sentence_jaccard`（默认 0.6）且非引号/列表项，标记为候选。
4. 输出重复对：`(sent_a, sent_b, score, line_a, line_b)`。

**注意**：允许"先总后分"的刻意重复（如概述段 + 详情段），故仅当两句话**词袋重叠高且都非标题/列表**时判定为冗余，避免误伤。

## 2. 高频重复短语检测（SEM-002）

**目标**：发现同一短语被不必要地反复使用，可合并或代词化。

**方法**：
1. n-gram（2–4 词）滑动窗口统计出现频次。
2. 频次 ≥ `thresholds.repeat_phrase_min_count`（默认 4）且非必要术语（如"Skill"）的短语标记。
3. 给示例合并建议（如连续出现 4 次"这个技能"→ 部分可删）。

## 3. 术语一致性检测（SEM-003）

**目标**：同一概念用不同词表述会造成阅读混乱与检索困难。

**方法**：
1. 维护"同义术语簇"映射（可在 config 覆盖），默认簇如：
   - `{Skill, skill, 技能, 这个技能}` → 建议统一为技能内最高频写法
   - `{WorkBuddy, workbuddy, 助手}` → 统一为 WorkBuddy
   - `{frontmatter, 前置元数据, YAML头}` → 统一为 frontmatter
2. 统计每簇内各写法出现次数，取最高频者为"规范写法"。
3. 标记所有偏离规范写法的位置，建议批量替换。

## 4. 冲突指令检测（SEM-004，高危）

**目标**：前后给出相反/互斥的操作要求（如"必须 X"与"不要 X"）。

**方法**：
1. 抽取含强约束词的句子：必须/禁止/不要/始终/绝不/应该/不可/只能。
2. 对同一动作对象（动词+宾语），若同时出现正向与负向约束，标记冲突。
3. 例："始终使用中文回答" vs "回复可用英文" → 冲突。
4. 输出冲突对与建议保留版本（默认保留更安全/更具体的那条，或交由人工）。

## 5. 意图漂移检测（SEM-005）

**目标**：某段落主题明显偏离技能声明的能力范围。

**方法**：
1. 取 SKILL.md 开头声明的"能力关键词"（来自 Overview/When To Use）。
2. 对正文每个二级标题段落做关键词覆盖度打分。
3. 覆盖度 < `thresholds.drift_threshold`（默认 0.2）且段落较长的，标记"疑似漂移"，供人工判断。

## 阈值（config.thresholds 默认）

```json
{
  "dup_sentence_jaccard": 0.6,
  "repeat_phrase_min_count": 4,
  "drift_threshold": 0.2,
  "min_sentence_len": 8
}
```

## 输出 JSON 结构

```json
{
  "semantic_findings": [
    {"rule_id":"SEM-001","severity":"medium","location":"SKILL.md:120",
     "evidence":"句A 与 句B 相似度 0.72","recommendation":"合并为一条"},
    {"rule_id":"SEM-003","severity":"medium","location":"SKILL.md:55,89",
     "evidence":"'Skill' 与 '技能' 混用","recommendation":"统一为'技能'"}
  ],
  "term_unify_suggestions": {"Skill":"技能","workbuddy":"WorkBuddy"}
}
```

## 与优化策略的衔接

- SEM-001/002 → `OPT-SEM-DEDUP`（safe，合并/删除重复）
- SEM-003 → `OPT-TERM-UNIFY`（safe，术语归一）
- SEM-004 → `OPT-REWRITE-CONFLICT`（aggressive，重写冲突）
- SEM-005 → 仅报告，不自动改写（避免误删有意为之的内容）
