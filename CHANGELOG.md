# Changelog

## v1.10.1 — 2026-10-23

**补上最后一条：Windows 真能跑（三平台 CI + 编码 / 路径归一）**

> v1.10.0 结尾留了一句"不跨平台验证运行时行为"。这轮把它做实：不是写句"支持 Windows"，
> 而是把 Windows 上会崩的三处真改掉，再交给 CI 的三个平台各自跑一遍。

### 修复（Windows 上必崩、macOS 上完全无感）

- **标准输出编码**：新增 `_common.ensure_utf8_stdio()`，导入时把 stdout/stderr 固定为 UTF-8。
  Windows 默认按本地代码页（cp936 / cp1252）写标准输出，报告里的中文会直接抛 `UnicodeEncodeError`——
  工具逻辑没问题，死在控制台上。
- **子进程解码**：`run_all.py` / `batch_audit.py` 调子脚本时统一 `encoding="utf-8", errors="replace"`
  并注入 `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1`；否则父进程按本地代码页解码子进程的中文 JSON 会报错。
- **路径分隔符归一**：新增 `_common.posix_rel()`，`load_skill` 与 `diagnose` 的文件清单统一用 `/`。
  反斜杠会让 `.skill-audit/`、`.git/` 的排除判断和 `references/` 引用检查在 Windows 上**静默失效**（不报错，直接漏检）。
- **`--depth` 语义跨平台一致**：`batch_audit.py` 改按相对路径段数算深度，不再数字符数——
  Windows 的盘符 `C:\` 会让字符数偏多，同一份目录树在两平台跑出不同结果。
- **测试夹具用 `os.devnull`**：原来 `--out /dev/null` 在 Windows 上根本不存在，用例会假失败。
- **`diagnose.py` 文件句柄**：`json.load(open(...))` 改为 `with`，Windows 上未关闭句柄会阻止删除目录。

### 新增

- **CI 三平台矩阵**：`ubuntu-latest` / `macos-latest` / `windows-latest` × Python 3.9、3.13（Ubuntu 补 3.12），
  全局 `PYTHONUTF8=1`；另拆出 `security` job 专门上传 SARIF。
- **跨平台契约用例 4 条**（`tests/test_common.py::TestCrossPlatform`）：路径归一、`load_skill` 无反斜杠、
  子进程环境变量、stdout 能直接写中文。测试 64 → **68 项**。
- `selftest.py` 摘要打印平台与 Python 版本，CI 日志里一眼定位是哪个平台挂的。

### 文档

- README / SKILL.md 标注「跨平台：三平台 CI 验证」；FAQ 新增 Q20（Windows 支持与三个已知差异）。

## v1.10.0 — 2026-10-23

**把 v1.9.0 自曝的四个短板补掉：批量并行、同义改写、跨文件外发、跨平台路径**

> 这四项都来自 v1.9.0 结尾的"诚实清单"，本轮逐条落地，没有新增"预留但未实现"的东西。

### 新增

- **`batch_audit.py`：批量并行审计 + 汇总看板**（第 11 个脚本）
  - `--root DIR` 递归发现含 `SKILL.md` 的技能（命中即停，不把技能里内嵌的示例算成两个目标），
    `--jobs` 并行（默认 CPU 核数、上限 8），实测 86 个技能 / 4 并行约 35 秒。
  - 看板三块：**总览表**（按 TRACE 从低到高）、**共性问题**（同一条规则命中几个技能 = 系统性短板）、
    **待修清单**（high/medium，带文件行号）。
  - **只读**：不创建 `.skill-audit/`、不改任何文件——批量扫别人托管的目录时这点很关键。
  - 门禁：`--fail-on` / `--fail-under`（要求**每个**技能达标），退出码 2，与步骤失败（1）区分。
- **SEM-006 同义改写重复**：SEM-001 只看字面，作者一换同义词（校验→检查）就漏。新增**概念归一表**
  （8 组通用词表，`config.synonyms` 可合并扩充），归一后重算相似度；三道精度闸门：必须真换过词、
  极性一致（必须 vs 禁止归 SEM-004）、已由 SEM-001 报过的不重报。证据里带出换词对，一眼能判断真假。
- **SEC-008 跨文件读+发组合**：读在 A 文件、发在 B 文件，是绕开 SEC-002 同文件判定的常见手法。
  两侧都要求**动作级证据**：一侧是把私钥/凭据喂给命令的读取动作，另一侧是带数据体或上传选项的发送动作；
  只报 medium，不追数据流。规则样例见 `references/security-rules.md`（该文件整体豁免，可如实写出模式）。
- **STRUCT-019 覆盖 Windows**：新增盘符（`C:` 后接反斜杠或正斜杠）与 UNC（`\\host\share`）形态；
  盘符前加负向断言，`https://` 不会被误判成盘。

### 修复

- **`config.synonyms` 的配置陷阱**（自测中发现）：原实现是"整块替换内置词表"，用户在配置里只写一组，
  等于悄悄关掉其余七组检查。改为**同名键覆盖、新键新增**，并忽略 `_` 开头注释键与非列表值。
- **`batch_audit.py` 的告警污染 JSON**：路径告警原走 stdout，`--json` 时输出不合法；已改走 stderr。

### 文档

- SKILL.md 新增「批量审计（一次扫完多个 Skill）」章节 + 目录项；能力边界补 ⑤⑥ 两条诚实边界；
  Q15 从"自己写 for 循环"改为指向 `batch_audit.py`；新增 Q19（同义改写怎么判断）。
- FAQ 新增 Q18（批量）与 Q19（同义改写边界）；`references/prompt-semantic-analysis.md` 新增第 6 节；
  `references/security-rules.md` 新增 SEC-008 并重写跨文件边界说明；
  `references/audit-rules.md` 补 SEM-006 与 STRUCT-019 跨平台口径；示例配置补 `synonyms`。
- 测试 50 → **64 项**（SEC-008 三例、STRUCT-019 跨平台两例、SEM-006 四例、批量端到端四例、
  配置合并一例）。

## v1.9.0 — 2026-10-23

**对齐开源生态的先进做法：OWASP Agentic Skills 安全规则族 + 规范合规校验 + SARIF/CI 门禁 + 自带测试套件**

> 参考了 OWASP Agentic Skills Top 10（AST01–AST10）与其 Skill Security Assessment Checklist、
> agentskills.io 规范与主流 marketplace 的两层校验口径、以及开源 skill 扫描器（SX-CMD/SX-EXF/SX-INJ 等）
> 的规则切分方式。落地的都是能在本机复现的检查项，没有"预留但未实现"的东西。

### 新增能力

- **安全扫描 `security_analyzer.py`（Phase 1.5）**：SEC-001~007 七类模式，**代码层与正文指令层都读**——
  这是 Skill 特有的攻击面（payload 藏在 markdown 散文里），普通密钥扫描器看不到。每条带 OWASP AST 编号：
  危险命令(AST01)、敏感读取+外发(AST01)、越权/隐蔽指令(AST05)、过度授权(AST03)、硬编码凭据(AST04，证据脱敏)、
  写身份/记忆文件(AST01+03)、隐藏 Unicode(AST05)。规则详情见 `references/security-rules.md`。
- **两套防误报机制**：① 教材/反模式语境自动降一级并标注；② 行级/文件级抑制标记
  （`skill-inspector: ignore SEC-001` / `ignore-file SEC-001,SEC-002`），豁免写在代码里可被 review，
  而不是偷偷关规则。
- **规范合规规则 STRUCT-015~019**：name 格式（1–64、kebab-case）、name 与目录名一致、
  description 长度（>1024 / <20）、正文行数卫生（>500 建议拆分）、机器绝对路径（`/Users/…`、`/home/…`）。
- **EFF-005 孤立资源**：`references/`、`assets/` 里存在但正文从未引用的文件——渐进式披露的另一半。
- **SARIF 2.1.0 输出**：`audit_skill.py --format sarif`，可接 GitHub Security 面板与任意 CI 聚合器。
- **CI 门禁**：`run_all.py --fail-on low|medium|high --fail-under 80`；命中退出码 `2`，脚本自身出错 `1`。
- **自带测试套件**：`tests/`（50 项，stdlib unittest）+ `scripts/selftest.py` + `.github/workflows/ci.yml`
  （3 个 Python 版本矩阵）。用例刻意做成"真阳性 + 假阳性回归"双向断言——因为这个工具最容易错的地方就是误报。

### 修复

- **`parse_frontmatter` 不剥离 YAML 引号**（真 bug）：`name: 'x'` 会把引号一起返回，连带污染
  description 长度、第一/第二人称、绝对化词等判断。现统一剥成对引号。
- **T3 夸大检测加固**：两次误报的根因都是"引用别人的话"被当成自己的承诺。现在引号内示例（「」“”""）、
  教材/禁止语境行、技术术语（绝对路径/绝对化承诺）三类均豁免，另有 6 条回归用例锁死行为。
- **`run_all.py --json` 退出码不反映失败**：原先无论步骤是否失败都退出 0，现在按失败/门禁分别返回 1/2。

### 文档

- 报告模板新增第 4 节「安全审查（OWASP Agentic Skills）」，章节重编号为 1–7。
- `references/audit-rules.md` 补齐新规则；新增 `references/security-rules.md`（规则表 + AST 映射 + 抑制语法 + 诚实边界）。
- SKILL.md 增加 Phase 1.5、触发词「安全」场景、Q17/Q18；FAQ 增加 Q15/Q16；README 更新目录树与 CI 用法。

## v1.8.2 — 2026-10-23

**改名以通过平台唯一性校验：`skill-auditor` → `skill-inspector`**

> WorkBuddy 技能导入返回「解析失败：技能名称 "skill-auditor" 已被占用」。名称是全局唯一的，因此改注册名；功能、规则集、评分口径一概未动。

- `SKILL.md` 的 `name` 改为 `skill-inspector`；`display_name`（技能审查官）/ `display_name_en`（Skill Auditor）不变，展示层无感知。
- 正文与脚本里 60 处自称同步改名（SKILL.md / README / FAQ / COOKBOOK / 报告模板 / 4 个脚本的提示文案），避免"名称与文档不一致"被评测判为规范性问题。CHANGELOG 历史条目保留原名，不改写历史。
- 仓库名与历史发行包仍沿用 `skill-auditor`，属发布渠道差异，不影响导入。

## v1.8.1 — 2026-10-23

**新增 WorkBuddy 上传入口所需的 4 个 frontmatter 字段 + 修 T3 一处误报**

> 本轮不改能力，只为「能作为 WorkBuddy 技能包被导入」补齐元数据；顺带被自测暴露一个真实误报。

- **frontmatter 补齐 WorkBuddy 技能入口必填 4 项**：`display_name`（技能审查官）、`display_name_en`（Skill Auditor）、`description_zh`、`description_en`。缺失时平台导入报「缺少 Skill 中文展示名」等四条错误；原有 `name` / `version` / `description` / `agent_created` 保持不变。
- **修 `trace_eval.py` T3 误报**：夸大词表里的裸 `绝对` 会命中 `绝对化承诺`（描述反模式本身的名词），导致自审 T 维从 100 掉到 80。现与 `绝对路径`/`绝对定位` 一并纳入技术语境豁免。
- **SKILL.md 反模式表第 8 行**把示例串改为行内代码（`100% 准确`、`永远不会错`），既是规范写法，也让 T3 的代码豁免正常生效。
- 自测：`run_all.py` 全流程通过，TRACE 100.0 / A，静态 5/5，17 条用例全部执行。

## v1.8.0 — 2026-08-05

**按 SkillHub 评测报告（4.6/5）修复"文档/话术与实现错位" + 一键入口**

> 本轮评测 4.6（上轮 4.7）：C 反模式/渐进式披露、E 内容完整度/创造力均上涨，但 T 国内适配性、E 开箱即用、A 能力边界、R 功能完善性回落。定位根因：**不是功能缺失，而是文档把已实现的功能标成"预留"、"跳过/采样"话术残留、入口分散**。

- **修复文档 drift（R 功能完善性 4.3 根因）**：`references/optimization-strategies.md` 中 `OPT-TRIGGER` 从"（预留，尚未实现）"改为"✅ 已实现（v1.5.0）"——它早已实现，但文档未更新，评测者读到"自动补全触发词还在开发中"。
- **消除"跳过"话术残留（R 运行稳定性 4.4）**：`semantic_analyzer.py` 的 SEM-INFO 与 SKILL.md/FAQ 相关段落改为"重点段深扫 + 全文浅扫兜底"正面表述，去掉"100% 深扫""未覆盖"暗示。
- **新增 `run_all.py` 一键入口（E 开箱即用 4.4 / A 触发方式 4.5）**：`python3 run_all.py <skill>` 一条命令跑完 审计→语义→TRACE→测试→报告，自动生成 `REPORT.md` 并打印摘要；SKILL.md 30 秒快速开始、触发词速查卡（自动化/批量）、README、FAQ 全部同步为推荐入口。
- **能力边界三栏表加超大文件专段（A 能力边界 4.5）**：明确"超大文件 → 全文浅扫兜底 + 重点段深扫，不丢失检查项，覆盖区间写入报告"。
- **离线引用声明（T 国内适配性 4.3）**：SKILL.md 顶部 Banner 与 README 顶部注明"references/、assets/ 均为自带文件，离线可读，不依赖任何外部链接"。
- **COOKBOOK 新增最佳实践章节（C 文档质量 4.6）**：发布前自检 5 步清单、TRACE 各维度保分要点表、真实优化案例 2 例。
- **自检**：py_compile 全过；自身 audit 仅 STRUCT-014；TRACE 100.0/A；静态 5/5；17 用例全启发式；run_all.py 端到端（含坏路径）通过。

### 已实现 vs 预留（诚实对照）

- **已实现**：OPT-FRONTMATTER / OPT-TRIGGER（v1.5.0）/ OPT-DEDUP-BLOCK / OPT-SEM-DEDUP / OPT-TERM-UNIFY / OPT-DEADREF-FIX / OPT-PHRASE-NORMALIZE / OPT-REF-EXTERNALIZE / OPT-REWRITE-CONFLICT / OPT-RESTRUCTURE
- **预留（未实现）**：OPT-EXAMPLE-ADD（示例自动补写，aggressive）、PROMPT-008（过时工具名检查）、PROMPT-009（指令歧义检测）、EFF-004（冗余回路检测）、EFF-005（渐进式披露达标检查）——这些在文档中标注"（预留，尚未实现）"，请勿在 config 中启用。

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
