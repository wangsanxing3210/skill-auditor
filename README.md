# skill-inspector

> 一个用于**审查、评测、测试、优化**其他 Skill 的元 Skill（meta-skill）——不限定于某家工具，适用于 WorkBuddy / OpenClaw 等任何基于 SKILL.md 的 Skill。

skill-inspector 把自己当成一把"刀"，专门削其他 Skill——在不破坏原有能力的前提下，发现结构 / 提示词 / 效率层面的问题，并按发现安全地自动优化。

> **版本 v1.10.1** · 框架无关：适用于任何基于 `SKILL.md` 的 Skill（WorkBuddy / OpenClaw 等）。
> **跨平台**：macOS / Linux / Windows 同一套脚本、同一套用例，CI 三平台矩阵验证（Windows 的代码页、路径分隔符差异已处理）。
> 注册名 `skill-inspector`（原 `skill-auditor`，因平台名称唯一性被占用而改名），仓库名沿用旧名。
> 完整用法见 `SKILL.md`：含 **触发词速查卡**、**30 秒快速开始**、**能力边界与异常处理**、**示例（Few-shot）**。
> 遇到卡点查 **`FAQ.md`**；想照着做看 **`COOKBOOK.md`**。
> 本 Skill 引用的 `references/`、`assets/` 均为自带文件，离线可读，不依赖任何外部链接。

## 核心能力

0. **一键全流程**（`scripts/run_all.py`）——`python3 run_all.py <skill>` 一条命令跑完 审计 → 语义 → 安全 → TRACE → 测试 → 报告，生成 `REPORT.md`，零配置；带 `--fail-on` / `--fail-under` 可直接当 CI 门禁。
1. **结构 / 提示词 / 效率审查**（`scripts/audit_skill.py`）——基于 `references/audit-rules.md` 的规则集（STRUCT / PROMPT / SEM / EFF 多类），扫描 SKILL.md 与脚本的完整性、一致性、冗余。
2. **提示词语义分析**（`scripts/semantic_analyzer.py`）——近义重复、术语不一致、冲突指令、意图漂移检测。
3. **SkillHub TRACE 五维评测**（`scripts/trace_eval.py`）——Trust / Reliability / Adaptability / Convention / Effectiveness 加权评分，输出总分与等级。
4. **自动化测试**（`scripts/skill_tester.py`）——静态完整性校验 + 边界 / 准确性用例生成与执行（默认启发式判定，支持 `--model-config` 接入模型）。
5. **安全自动优化**（`scripts/optimize_apply.py`）——基于发现应用优化策略，产出前后 diff 报告；所有改动可回退，破坏性操作默认 dry-run。
6. **报告汇编**（`scripts/build_report.py`）——读取各阶段 JSON 产物，渲染 `assets/report_template.md`，自动生成 Phase 5 的 `REPORT.md`。
7. **一键环境诊断**（`scripts/diagnose.py`）——Python 环境 / SKILL.md 可读性 / frontmatter / 超限 / dotfile / 配置 7 项检查，输出"环境健康报告"。
8. **安全扫描**（`scripts/security_analyzer.py`）——按 **OWASP Agentic Skills Top 10** 切分的 8 类模式（SEC-001~008，含跨文件读+发组合）：危险命令、敏感读取+外发、越权/隐蔽指令、过度授权、硬编码凭据（脱敏）、写身份/记忆文件、隐藏 Unicode；**代码层与正文指令层都读**，支持行级/文件级抑制与 `config.json` 逐条关规则。
9. **批量并行 + 汇总看板**（`scripts/batch_audit.py`）——`--root <技能父目录>` 一条命令并行审完一批技能，出 `BATCH-AUDIT.md`：总览表（按 TRACE 排序）、共性问题（同一条规则命中几个技能）、待修清单（带文件行号）。**只读**，不在目标目录留产物；`--fail-on/--fail-under` 可当 CI 门禁。
10. **自带测试与 SARIF**——`scripts/selftest.py` 一条命令跑 68 项单元 / 端到端测试（stdlib `unittest`，无第三方依赖）；`audit_skill.py --format sarif` 输出 SARIF 2.1.0，可接 GitHub Security 面板。

## 目录结构

```
skill-inspector/
├── SKILL.md                        # 元 Skill 入口与触发词
├── FAQ.md                          # 常见问题汇总页
├── COOKBOOK.md                     # 可照着做的完整场景案例
├── scripts/                        # 12 个 stdlib-only Python 脚本
│   ├── _common.py
│   ├── run_all.py                  # 一键全流程入口（推荐，含 CI 门禁开关）
│   ├── batch_audit.py              # 批量并行 + 汇总看板（只读）
│   ├── audit_skill.py              # 结构/提示词/效率（+ SARIF 输出）
│   ├── semantic_analyzer.py
│   ├── security_analyzer.py        # 安全扫描（OWASP AST，含跨文件组合 SEC-008）
│   ├── trace_eval.py
│   ├── skill_tester.py
│   ├── optimize_apply.py
│   ├── build_report.py
│   ├── diagnose.py                 # 一键环境诊断
│   └── selftest.py                 # 跑自带测试套件
├── tests/                          # 68 项单元 / 端到端测试（stdlib unittest）
│   ├── test_common.py              # 解析层：frontmatter / slug / 引号剥离
│   ├── test_rules.py               # 规则层：T3 误报回归 + SEC + SPEC + SARIF
│   └── test_e2e.py                 # 端到端：真跑 run_all / batch_audit，验退出码与门禁
├── references/                     # 规则库与框架文档
│   ├── audit-rules.md              # STRUCT/PROMPT/SEM/EFF 规则
│   ├── security-rules.md           # SEC 规则 + OWASP AST 映射 + 抑制语法
│   ├── optimization-strategies.md  # 优化策略 + 安全约束
│   ├── prompt-semantic-analysis.md
│   └── trace-framework.md
├── assets/                         # 配置样例与报告模板
│   ├── config.example.json
│   ├── model-config.example.json
│   └── report_template.md
├── .github/workflows/ci.yml        # CI 范例：3 个 Python 版本 + 门禁 + SARIF 上传
├── LICENSE.md                      # 开源许可（宿主会跳过，不影响 Skill 运行）
└── .gitignore                      # Git 忽略规则（宿主会跳过，不影响 Skill 运行）
```

## 用法

- **作为 Skill 使用**：将本仓库放到 `~/.workbuddy/skills/skill-inspector/`（user scope）或 `<workspace>/.workbuddy/skills/`（project scope），WorkBuddy 会自动加载。对某个 Skill 说"审查这个 Skill""给这个 Skill 做个 TRACE 评测"即可触发。
- **一条命令跑完全流程**（推荐新手 / 自动化用户）：
  ```bash
  python3 scripts/run_all.py <目标Skill路径>   # 自动生成 .skill-audit/REPORT.md
  ```
- **当 CI 门禁用**（出现 high 级发现或 TRACE 低于阈值即失败，退出码 2）：
  ```bash
  python3 scripts/run_all.py . --fail-on high --fail-under 80
  python3 scripts/audit_skill.py . --format sarif > skill-audit.sarif   # SARIF 2.1.0
  ```
- **批量审一批技能**（并行 + 看板，只读）：
  ```bash
  python3 scripts/batch_audit.py --root ~/.workbuddy/skills --jobs 4
  python3 scripts/batch_audit.py --root ./skills --fail-on high --fail-under 80   # CI 门禁
  ```
- **验证本 Skill 自身**（改代码后先跑这个，68 项用例）：
  ```bash
  python3 scripts/selftest.py
  ```
- **单独跑脚本**：所有脚本为 Python3 stdlib-only，无外部依赖，参数与 `SKILL.md` 的 Workflow 一致。例如：
  ```bash
  python3 scripts/audit_skill.py <目标Skill路径> --json > audit.json
  python3 scripts/trace_eval.py  <目标Skill路径> --json > trace.json
  python3 scripts/optimize_apply.py <目标Skill路径> --findings audit.json --dry-run
  ```

### 两种发行包（上传口径不同，别混用）

| 用途 | 包内形态 | 说明 |
|------|----------|------|
| WorkBuddy 技能导入 | 解压后**根目录即 `SKILL.md`**，无顶层目录；含 8 个脚本 + references/assets + 全部 md | 依赖 frontmatter 的 `display_name` / `display_name_en` / `description_zh` / `description_en` 四项，缺一即报"缺少 Skill 中文展示名" |
| SkillHub 上架 | **只收 `.md`**，根目录平铺 | SkillHub 拒收二进制与 dotfile，故该包只含文档；需要在本机跑脚本时，从 Git 仓库克隆完整目录 |


## 设计原则

- 自动优化**宁可少改，不可改坏**：专有名词 / 标题 / 列表行首等一律跳过重写。
- 破坏性操作需 `--dry-run` 预览 + 确认，且保留可逆 diff。
- 规则 / 权重 / 策略 / 阈值均可在 `config.json` 覆盖，并支持 `custom_rules_module` / `custom_strategies_module` 扩展。
- **零配置开箱可用**：审查、语义分析、TRACE、静态测试无需模型或网络；`run_all.py` 一条命令跑完所有阶段；仅可选的模型测试需 `--model-config`。
- **大文件与错误兜底**：SKILL.md 超过 512 KB 或正文超过 3 万词 / 3000 句时，采用"重点段深扫 + 全文浅扫兜底"，不丢失检查项；所有错误给出明确的"原因 + 下一步命令"。

## License

见仓库根目录 `LICENSE.md`。
