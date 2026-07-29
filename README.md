# skill-auditor

> 一个用于**审查、评测、测试、优化**其他 Skill 的元 Skill（meta-skill）——不限定于某家工具，适用于 WorkBuddy / OpenClaw 等任何基于 SKILL.md 的 Skill。

skill-auditor 把自己当成一把"刀"，专门削其他 Skill——在不破坏原有能力的前提下，发现结构 / 提示词 / 效率层面的问题，并按发现安全地自动优化。

> **版本 v1.4.0** · 框架无关：适用于任何基于 `SKILL.md` 的 Skill（WorkBuddy / OpenClaw 等）。
> 完整用法见 `SKILL.md`：含 **触发词速查卡**、**30 秒快速开始**、**能力边界与异常处理**、**示例（Few-shot）**。
> 遇到卡点查 **`FAQ.md`**；想照着做看 **`COOKBOOK.md`**。

## 核心能力

1. **结构 / 提示词 / 效率审查**（`scripts/audit_skill.py`）——基于 `references/audit-rules.md` 的规则集（STRUCT / PROMPT / SEM / EFF 多类），扫描 SKILL.md 与脚本的完整性、一致性、冗余。
2. **提示词语义分析**（`scripts/semantic_analyzer.py`）——近义重复、术语不一致、冲突指令、意图漂移检测。
3. **SkillHub TRACE 五维评测**（`scripts/trace_eval.py`）——Trust / Reliability / Adaptability / Convention / Effectiveness 加权评分，输出总分与等级。
4. **自动化测试**（`scripts/skill_tester.py`）——静态完整性校验 + 边界 / 准确性用例生成与执行（支持 `--model-config` 接入模型）。
5. **安全自动优化**（`scripts/optimize_apply.py`）——基于发现应用优化策略，产出前后 diff 报告；所有改动可回退，破坏性操作默认 dry-run。
6. **报告汇编**（`scripts/build_report.py`）——读取各阶段 JSON 产物，渲染 `assets/report_template.md`，自动生成 Phase 5 的 `REPORT.md`。

## 目录结构

```
skill-auditor/
├── SKILL.md                        # 元 Skill 入口与触发词
├── FAQ.md                          # 常见问题汇总页
├── COOKBOOK.md                     # 可照着做的完整场景案例
├── scripts/                        # 7 个 stdlib-only Python 脚本
│   ├── _common.py
│   ├── audit_skill.py
│   ├── semantic_analyzer.py
│   ├── trace_eval.py
│   ├── skill_tester.py
│   ├── optimize_apply.py
│   └── build_report.py
├── references/                     # 规则库与框架文档
│   ├── audit-rules.md              # STRUCT/PROMPT/SEM/EFF 规则
│   ├── optimization-strategies.md  # 优化策略 + 安全约束
│   ├── prompt-semantic-analysis.md
│   └── trace-framework.md
├── assets/                         # 配置样例与报告模板
│   ├── config.example.json
│   ├── model-config.example.json
│   └── report_template.md
├── LICENSE.md                      # 开源许可（宿主会跳过，不影响 Skill 运行）
└── .gitignore                      # Git 忽略规则（宿主会跳过，不影响 Skill 运行）
```

## 用法

- **作为 Skill 使用**：将本仓库放到 `~/.workbuddy/skills/skill-auditor/`（user scope）或 `<workspace>/.workbuddy/skills/`（project scope），WorkBuddy 会自动加载。对某个 Skill 说"审查这个 Skill""给这个 Skill 做个 TRACE 评测"即可触发。
- **单独跑脚本**：所有脚本为 Python3 stdlib-only，无外部依赖，参数与 `SKILL.md` 的 Workflow 一致。例如：
  ```bash
  python3 scripts/audit_skill.py <目标Skill路径> --json > audit.json
  python3 scripts/trace_eval.py  <目标Skill路径> --json > trace.json
  python3 scripts/optimize_apply.py <目标Skill路径> --findings audit.json --dry-run
  ```

## 设计原则

- 自动优化**宁可少改，不可改坏**：专有名词 / 标题 / 列表行首等一律跳过重写。
- 破坏性操作需 `--dry-run` 预览 + 确认，且保留可逆 diff。
- 规则 / 权重 / 策略 / 阈值均可在 `config.json` 覆盖，并支持 `custom_rules_module` / `custom_strategies_module` 扩展。
- **零配置开箱可用**：审查、语义分析、TRACE、静态测试无需模型或网络；仅可选的模型测试需 `--model-config`。
- **大文件与错误兜底**：SKILL.md 超过 512 KB 或正文超过 5 万词时自动降级；所有错误给出明确错误码 + 下一步操作建议。

## License

见仓库根目录 `LICENSE.md`。
