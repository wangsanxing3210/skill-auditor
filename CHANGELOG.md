# Changelog

## v1.3.0 — 2026-07-29

**以"评审第三方"视角自测，修复文档/代码 drift 与两个真 bug，并补全 Phase 5 自动化**

- **修复 C5 文件名检查 bug**：`trace_eval.py` 原先只检查文件名的首字符（`f.split("/")[-1][:1]`），中文/空格落在文件名后段会漏检；改为完整遍历文件名，与 `STRUCT-011` 一致。
- **修复 `--run` 死 flag**：`skill_tester.py` 声明了 `--run` 但逻辑从未使用，静态检查默认就跑，导致 `--run` 与默认行为无差别。现明确：`--run`（或默认）执行静态检查；`--plan-only` 仅生成用例。同步修正 SKILL.md 中关于 `--run` 的两处矛盾描述。
- **实现 3 条之前只列在文档、代码未落地的规则**：`PROMPT-001`（触发词明确）、`PROMPT-002`（角色/目标明确）、`EFF-002`（超长内联块应外置）。
- **修正策略映射**：`optimize_apply.py` 的 `STRATEGY_TABLE` 移除无效的 `PROMPT-009` 映射，补入 `OPT-SEM-DEDUP`（折叠重复行，覆盖 SEM-001/002）与 `OPT-REF-EXTERNALIZE`（仅建议）。
- **标注文档中未实现的规则/策略为「预留」**：`audit-rules.md`（EFF-004、PROMPT-008/009）、`optimization-strategies.md`（OPT-TRIGGER、OPT-EXAMPLE-ADD）明确标注，避免用户在 config 中启用后无效。
- **新增 `build_report.py` 打通 Phase 5**：读取各阶段 JSON 产物 + `optimization-report.md`，渲染 `assets/report_template.md`（`{{}}` / `{% for %}` 模板），自动生成 `REPORT.md`。修复模板里的 `eevidence` 笔误（→ `evidence`）。SKILL.md Phase 5 增加调用步骤。
- **README 同步**：脚本数 6→7，核心能力补充"报告汇编"。

## v1.2.1 — 2026-07-29

**处理 Skill 宿主跳过 `.gitignore` / `LICENSE` 的提示**

- 新增审计规则 `STRUCT-014`：检测 `.gitignore` 和无扩展名 `LICENSE`，标记为 low 级别提示，说明这是宿主跳过仓库元数据文件的正常行为。
- `LICENSE` 重命名为 `LICENSE.md`；README 同步引用，减少 WorkBuddy 等宿主加载时的「不支持的文件类型」警告。
- 文档补全：`references/audit-rules.md` 加入 STRUCT-014；`FAQ.md` 新增 Q13；`SKILL.md` 内嵌 FAQ 同步 Q13。

## v1.2.0 — 2026-07-29

**针对 TRACE 4.5/5 评测反馈做冲刺优化，补齐可靠性、规范性、有效性短板**

- **统一友好错误处理**：`_common.py` 新增 `GuardError` + `humanize_error()`，6 个脚本 `main()` 全部包 try/except；错误输出含明确错误码 + 下一步操作建议，不再抛出 raw traceback。
- **大文件与资源兜底**：
  - `MAX_SKILL_BYTES=512KB`、`MAX_SENTENCES=2000`、`MAX_BODY_WORDS_FOR_HEAVY=50000`；
  - 超大 SKILL.md 直接给 `E_TOO_LARGE` 提示；语义分析在大文件下自动采样，跳过全量 O(n²) 检查并提示。
- **语义分析更保守**：冲突指令阈值从 0.3 提高到 0.4，并加"请人工复核"提示；术语不一致输出规范写法置信度；避免偶发小瑕疵被误判。
- **触发词速查卡**：SKILL.md 顶部新增"触发词 → 动作 → 示例"一表，降低使用记忆成本。
- **独立 FAQ 页 + Cookbook**：新增 `FAQ.md`（12 条高频问答 + 反模式表）和 `COOKBOOK.md`（3 个可照做的完整场景），解决"缺常见问题汇总页"和"缺菜谱式案例"的扣分项。
- **渐进式披露导航**：SKILL.md 各主要章节末尾加「接下来读什么」，减少用户在多文件间迷失。
- **零配置声明强化**：明确审查/语义/TRACE/静态测试无需 `--model-config`，仅模型输出测试可选。
- **TRACE R 维度增强**：新增 R7 指标检查大文件/降级处理声明。

## v1.1.0 — 2026-07-28

**按 medinfo-solution-expert 冲分 4.9 的结构范式升级可用性 / 健壮性**

- **框架无关化**：SKILL.md `description`、Overview、README、trace-framework 去除"WorkBuddy 专用"措辞，明确适用于任何基于 `SKILL.md` 的 Skill。
- **OPT-TERM-UNIFY 默认中立**：移除硬编码的 WorkBuddy 产品术语簇，默认仅含跨框架通用写法；新增 `config.term_clusters` 支持按需自定义产品簇（`semantic_analyzer.py` / `optimize_apply.py` 同步支持）。
- **新增「30 秒快速开始」+ 安全与伦理声明**：讲清启动方式 / 产出 / 改动确认机制；声明本地运行、不联网、不改坏。
- **新增「能力边界与异常处理」**：能做 / 不做 / 降级做 三栏表 + 诊断→修复话术库 + 澄清问卷。
- **新增「示例（Few-shot）」**：审查 / TRACE / 优化三类输入-输出骨架，降低使用差异。
- **新增「References / Assets 引用表」+「常见问题 FAQ」**：任务→文档映射、7 条高频问答（是否改坏 / 框架支持 / 分数解读 / 泄露 / 自定义等）。
- **文档一致性修复**：SKILL.md Scripts 表格移除 `audit_skill.py` 不存在的 `--rules-only`；README 用法示例修正为真实参数（`target` 位置参数 + `--json`）。

## v1.0.0 — 2026-07-28

- 初始发布：审查 / 语义分析 / TRACE 五维评测 / 自动化测试 / 安全自动优化五大能力，6 个 stdlib-only 脚本 + 4 个 references + 3 个 assets。
- 自审自身：audit 0 发现，TRACE 100.0/A；第二轮加固新增 STRUCT-013 与 OPT-TERM-UNIFY 三重保护。
