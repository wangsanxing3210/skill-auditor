# Changelog

## v1.7.0 — 2026-08-04

**按 SkillHub 评测报告（4.7/5）落地 P0–P3 全量优化 + 全文中文化**

- **描述中文化（用户要求）**：`SKILL.md` 的 description、Overview、Design Principles、Workflow、Phase 0–5、Configuration、Extensibility 等全部改为中文为主（保留必要技术名词）；触发词速查卡加"适用人群/行业"列与"审/修/比"傻瓜入口。
- **P0-1 零依赖启发式测试**（`scripts/skill_tester.py`）：新增 `--no-model` 模式（无 `--model-config` 时自动启用），用确定性规则对边界/准确性用例输出 pass/fail + 证据，不再全是 manual；17 条用例全部自动判定。
- **P0-2 全量浅扫兜底**（`scripts/semantic_analyzer.py`）：heavy 模式下术语一致性、冲突指令、高频短语、意图漂移对**全文**执行（O(n)），仅 O(n²) 近义句重复做重点段采样；SEM-INFO 话术改为"分段采样 + 全量浅扫兜底"，消除"跳过"负面感知。
- **P0-3 报告覆盖度栏**（`scripts/build_report.py`、`assets/report_template.md`）：第 4 节新增"扫描覆盖度"与启发式判定统计，默认输出带结论而非"待人工"。
- **P1-1 错误提示命令化**（`scripts/_common.py`）：humanize_error / GuardError 的下一步升级为"一键可复制命令"（ls、wc -c、json.load 校验等）。
- **P1-2 一键环境诊断**（`scripts/diagnose.py` 新增）：Python 版本 / 脚本可导入 / SKILL.md 可读性 / frontmatter / 超限 / dotfile / config JSON 七项检查，输出"环境健康报告"。
- **P2 反模式五列化 + FAQ Q17**（`SKILL.md`、`FAQ.md`）：反模式表扩为五列（含典型错误示例与真实修复案例）；新增 Q17 评测结果解读指南。
- **修复两个新 bug**：① 中文化后 TOC 锚点失效（ST-04 死锚点）——重建 TOC 为精确 slug；② T3 把"绝对路径"误判为夸大——加技术语境豁免。
- **自检**：py_compile 全过；自身 audit 仅 STRUCT-014；TRACE 100.0/A；静态 5/5；17 用例全启发式执行；diagnose.py 三场景验证通过；build_report 端到端含覆盖度栏。

## v1.6.0 — 2026-07-30

**第二轮查漏补缺：补齐 T/A/E 显式声明 + C 目录与反模式**

- **国内适配性加固**（`SKILL.md`）：顶部加「纯本地 · 零网络依赖 · 零配置 · 全中文界面 · 下载即用」Banner，并把 `30 秒快速开始` 改为完整端到端 4 步命令（`build_report.py` 一行出报告）。
- **触发场景结构化**（`SKILL.md`）：触发词速查卡扩为 7 大场景（审查 / 评测 / 测试 / 优化预览 / 优化落盘 / 报告 / 自审批量）的"场景 → 说法 → 执行阶段"映射表。
- **Few-shot 补多轮澄清与自审**（`SKILL.md`）：新增示例 4（用户模糊→追问→执行的多轮澄清）与示例 5（skill-auditor 审计自身的自检）。
- **文档导航与反模式**（`SKILL.md`）：新增目录（TOC）；内嵌 FAQ 扩到 Q16（Q14 反模式索引、Q15 批量审查脚本、Q16 版本变更追踪）；新增独立「反模式」表（10 条 + 修复方向）。
- **自检结果**：py_compile 全过；自身 audit 仅 STRUCT-014；TRACE 100.0/A；静态 5/5；build_report.py 端到端跑通。

## v1.5.0 — 2026-07-30

**针对评测报告短板定向优化：提升可靠性、规范性与文档友好度**

- **错误提示人话化**（`scripts/_common.py`）：所有 GuardError 与 humanize_error 输出改为非技术用户能懂的三段式（简单说明 + 原因 + 下一步），避免"E_TOO_LARGE"这类纯代码式提示。
- **实现 OPT-TRIGGER 自动补全触发词**（`scripts/optimize_apply.py`）：当 `PROMPT-001` 触发（缺少触发词）时，自动从 description + 能力描述抽取关键词，在 frontmatter 后插入「触发词速查卡」草案（dry-run 可预览）。
- **大文件语义分析提速 + 精确化**（`scripts/_common.py`、`scripts/semantic_analyzer.py`）：
  - 采样阈值从 5 万词/前 2000 句收紧为 3 万词 或 3000 句 / 共 1500 句；
  - 从"只采开头"改为"开头、中间、结尾三段均匀采样"，并在 SEM-INFO 中明确标注覆盖区间；
  - 实测 4.4 万词/1.1 万句文件从数分钟挂起降到 5 秒内完成。
- **文档补齐自然语言示例与错误对比**（`FAQ.md`、`COOKBOOK.md`）：新增 COOKBOOK「自然语言使用速查」、FAQ Q14「错误写法 → 修复后」对照表、更新 Q9 采样说明，降低文档的命令行倾向。
- **自检结果**：py_compile 全过；自身 audit 仅 STRUCT-014；TRACE 100.0/A；静态 5/5；OPT-TRIGGER、人话错误、大文件采样均单独验证通过。

## v1.4.0 — 2026-07-29

**收紧 TRACE 评测判定，消除"关键词命中即满分"的自嗨空间**

- `scripts/trace_eval.py` 重写 8 个宽松指标，要求**结构证据**而非关键词命中：
  - T5：需真实 `http(s)` 链接或 `references/<file>` 文件引用（仅"参考"二字不计分）
  - R3：需真实错误处理指令（try/except、fallback、回退、捕获异常等）
  - R5：需具名边界场景（空/超大/缺失）或 `skill_tester` 真有 boundary 用例
  - R7：需显式大小限制/guard/降级策略
  - A1：需 `--config` 或 `config.json` 引用（仅"配置"二字不计分）
  - A2：需 `custom_rules_module`/`custom_strategies_module` 钩子（仅"扩展"二字不计分）
  - E2：需含命令的代码围栏 + 动作动词（可操作）
  - E4：需交付物专节或 verbatim 交付物清单（仅"报告"二字不计满分）
- 新增 `m_near()`：有主题提及但无结构证据的指标给 partial，缺失给 fail
- `references/trace-framework.md` 同步更新指标判据说明
- 自测：skill-auditor 自身仍 100.0/A（无误伤）；关键词堆砌的弱 Skill 实测掉到 67.5/C

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
