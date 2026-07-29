# Skill 审查 · 评测 · 优化报告

> 由 `skill-auditor` 元 Skill 生成。报告整合 Phase 1–4 的产出，供发布前评审或迭代使用。

## 1. 基本信息

| 项 | 值 |
|----|----|
| 技能名称 | {{skill_name}} |
| 路径 | {{skill_path}} |
| 作用域 | {{scope}}（user / project） |
| 审查时间 | {{timestamp}} |
| 配置 | {{config_path}} |

## 2. SkillHub TRACE 评测

**总分：{{overall}} / 100　等级：{{grade}}**

| 维度 | 含义 | 得分 | 关键证据 |
|------|------|------|----------|
| T | 可信任度 Trust | {{score_T}} | {{evidence_T}} |
| R | 可靠性 Reliability | {{score_R}} | {{evidence_R}} |
| A | 适用性 Adaptability | {{score_A}} | {{evidence_A}} |
| C | 规范性 Convention | {{score_C}} | {{evidence_C}} |
| E | 有效性 Effectiveness | {{score_E}} | {{evidence_E}} |

- 最弱维度：{{weakest_dimension}}
- 关键短板（<50）：{{critical_gaps}}
- 优化前→后对比（如有）：{{prior_overall}} → {{overall}}（Δ {{delta}}）

## 3. 关键发现（按严重度）

{% for finding in findings %}
- **[{{finding.severity}}] {{finding.rule_id}}** @ `{{finding.location}}`
  - 证据：{{finding.evidence}}
  - 建议：{{finding.recommendation}}
{% endfor %}

## 4. 测试结论

- 静态完整性：{{static_pass}}/{{static_total}} 通过
- 用例：{{cases_total}} 项（已执行 {{cases_executed}}，待人工 {{cases_manual}}）
- 边界/准确性摘要：{{test_summary}}

## 5. 优化前后对照

- 自动应用策略：{{applied_strategies}}
- 仅建议（人工处理）：{{report_only_strategies}}
- 改动清单：
  {{change_notes}}
- Diff 摘要：
```diff
{{diff_excerpt}}
```

## 6. 后续建议

1. {{next_step_1}}
2. {{next_step_2}}
3. {{next_step_3}}

---
*报告由 skill-auditor 生成；所有自动改动均可通过 `.skill-audit/` 下的原始快照与 diff 还原。*
