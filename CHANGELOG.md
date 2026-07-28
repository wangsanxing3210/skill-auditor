# Changelog

## v1.1.0 — 2026-07-28

**按 medinfo-solution-expert 冲分 4.9 的结构范式升级可用性 / 健壮性**

- **框架无关化**：SKILL.md `description`、Overview、README、trace-framework 去除"WorkBuddy 专用"措辞，明确适用于任何基于 `SKILL.md` 的 Skill。
- **OPT-TERM-UNIFY 默认中立**：移除硬编码的 WorkBuddy 产品术语簇，默认仅含跨框架通用写法；新增 `config.term_clusters` 支持按需自定义产品簇（`semantic_analyzer.py` / `optimize_apply.py` 同步支持）。
- **新增「30 秒快速开始」+ 安全与伦理声明**：讲清启动方式 / 产出 / 改动确认机制；声明本地运行、不联网、不改坏。
- **新增「能力边界与异常处理」**：✅能做 / ⛔不做 / 🔽降级做 三栏表 + 诊断→修复话术库 + 澄清问卷。
- **新增「示例（Few-shot）」**：审查 / TRACE / 优化三类输入-输出骨架，降低使用差异。
- **新增「References / Assets 引用表」+「常见问题 FAQ」**：任务→文档映射、7 条高频问答（是否改坏 / 框架支持 / 分数解读 / 泄露 / 自定义等）。
- **文档一致性修复**：SKILL.md Scripts 表格移除 `audit_skill.py` 不存在的 `--rules-only`；README 用法示例修正为真实参数（`target` 位置参数 + `--json`）。

## v1.0.0 — 2026-07-28

- 初始发布：审查 / 语义分析 / TRACE 五维评测 / 自动化测试 / 安全自动优化五大能力，6 个 stdlib-only 脚本 + 4 个 references + 3 个 assets。
- 自审自身：audit 0 发现，TRACE 100.0/A；第二轮加固新增 STRUCT-013 与 OPT-TERM-UNIFY 三重保护。
