# skill-inspector 场景案例手册（Cookbook）

> 像菜谱一样可照着做的 4 个完整场景：审查一个臃肿 Skill、给 Skill 冲 TRACE 高分、安全地优化并对比前后、批量审一批技能。

---

## 自然语言使用速查（无需记命令）

除了对 skill-inspector 说"审查这个 skill"，你也可以直接用下面这些日常说法：

| 你想做什么 | 可以直接这样说 |
|-----------|---------------|
| 审查某个 Skill 的质量 | "帮我审一下 ~/.workbuddy/skills/example" |
| 看 TRACE 评分 | "给这个 skill 跑个 TRACE" / "评测一下质量" |
| 检查语义问题 | "看看这个 SKILL.md 有没有重复、冲突" |
| 安全优化 | "帮我优化这个 skill" / "补全 frontmatter 和触发词" |
| 生成最终报告 | "把审计结果汇总成 REPORT.md" |
| 批量审一批技能 | "把所有 skills 都审一遍，哪个最差" |
| 上架前安全检查 | "扫一下这个 Skill 有没有安全问题" |
| 只看不动 | "先预览一下会改哪些地方" |

> skill-inspector 会先进入审计阶段；如果你没指定路径，它会追问"要审哪个 Skill"。

---

## 场景一：审查一个"越来越长"的 Skill

**背景**：你的 Skill 经过多轮迭代，SKILL.md 从 800 字涨到 4000 字，你怀疑里面有重复提示词、死链接、该外置的细节没外置。

**目标**：快速拿到问题清单，不动原文件。

### 步骤

```bash
# 1. 进入 skill-inspector 目录
cd ~/.workbuddy/skills/skill-inspector

# 2. 跑审计（只读，输出 JSON）
python3 scripts/audit_skill.py /path/to/your/skill --json > /path/to/your/skill/.skill-audit/audit.json

# 3. 跑语义分析（只读）
python3 scripts/semantic_analyzer.py /path/to/your/skill/SKILL.md --json > /path/to/your/skill/.skill-audit/semantic.json

# 4. 人话查看（非 JSON 模式）
python3 scripts/audit_skill.py /path/to/your/skill
python3 scripts/semantic_analyzer.py /path/to/your/skill/SKILL.md
```

### 预期产出

- `audit.json`：结构问题（frontmatter、缺失引用、目录结构）、提示词质量（是否有 TODO、绝对化表述）、效率问题（重复块、死锚点）。
- `semantic.json`：近义重复句、高频重复短语、术语不一致、疑似冲突指令。

### 下一步

按严重度从高到低修：
1. high（如 STRUCT-007 缺失脚本、SEM-004 疑似冲突）；
2. medium（如 SEM-003 术语混用、PROMPT-004 正文过长）；
3. low（如 EFF-003 死锚点）。

---

## 场景二：给 Skill 冲 TRACE 高分

**背景**：你要把一个 Skill 上架或提交评审，希望 TRACE 五维分数尽量高。

**目标**：定量知道短板在哪，并定向补齐。

### 步骤

```bash
# 1. 跑 TRACE 评分
python3 scripts/trace_eval.py /path/to/your/skill --json > /path/to/your/skill/.skill-audit/trace.json

# 2. 看最弱维度（示例输出）
# {
#   "overall": 82.5,
#   "grade": "B",
#   "weakest_dimension": "R",
#   ...
# }

# 3. 根据最弱维度定向修复
# 假设 R 最低，常见修法：
# - 在 SKILL.md 加「能力边界与异常处理」章节；
# - 给示例命令加可执行性说明；
# - 声明空输入/超大输入/缺失参数的处理方式。

# 4. 修复后再跑一次，看 delta
python3 scripts/trace_eval.py /path/to/your/skill --json --prior /path/to/your/skill/.skill-audit/trace.json
```

### 冲分检查清单

| 维度 | 快速自检项 |
|------|-----------|
| T | 无硬编码密钥；无"100%""永远"等绝对化词；有隐私说明 |
| R | 有错误处理/回退说明；示例可执行；声明边界输入处理 |
| A | 有 config 示例；有自定义规则/策略扩展说明 |
| C | frontmatter 齐全；目录结构规范；正文不过长 |
| E | description 与实际能力一致；有明确产出物 |

### 下一步

反复「评分 → 看最弱维度 → 修短板 → 再评分」，直到 overall ≥ 90（A）。

---

## 场景三：安全优化并对比前后

**背景**：审查发现术语混用、frontmatter 缺字段、有连续重复文本，你想让 skill-inspector 自动修，但怕改坏。

**目标**：先预览，确认后再落盘，且保留回退能力。

### 步骤

```bash
# 0. 先合并审计发现为一个 findings.json
cd /path/to/your/skill
mkdir -p .skill-audit

# 1. 生成 findings.json（这里手动合并示例；实际可用脚本或让 skill-inspector 自动合并）
python3 ~/.workbuddy/skills/skill-inspector/scripts/audit_skill.py . --json > .skill-audit/audit.json
python3 ~/.workbuddy/skills/skill-inspector/scripts/semantic_analyzer.py SKILL.md --json > .skill-audit/semantic.json

# 2. 合并（可用 jq 或 python）
python3 - <<'PY'
import json
with open('.skill-audit/audit.json') as f: a = json.load(f)
with open('.skill-audit/semantic.json') as f: s = json.load(f)
findings = a.get('findings', []) + s.get('semantic_findings', [])
with open('.skill-audit/findings.json', 'w') as f:
    json.dump({'findings': findings}, f, ensure_ascii=False, indent=2)
PY

# 3. dry-run 预览（不写盘）
python3 ~/.workbuddy/skills/skill-inspector/scripts/optimize_apply.py . \
  --findings .skill-audit/findings.json --dry-run

# 4. 检查 diff 满意后，确认落盘
python3 ~/.workbuddy/skills/skill-inspector/scripts/optimize_apply.py . \
  --findings .skill-audit/findings.json \
  --out .skill-audit/optimization-report.md

# 5. 若后悔，用 .bak 回退
cp SKILL.md.bak SKILL.md
```

### 预期产出

- `SKILL.md.bak`：原文件备份；
- `SKILL.md`：优化后的文件；
- `.skill-audit/optimization-report.md`：关键发现 + 已应用改动 + 统一 diff。

### 安全提示

- 落盘前务必 `--dry-run`；
- 高风险策略（`OPT-REWRITE-CONFLICT`、`OPT-RESTRUCTURE`）默认不会自动应用，会出现在 report-only 列表里让你人工决定；
- 术语归一会自动跳过标题、句首大写、列表行首，降低改坏概率。

---

## 场景四：手上一堆 Skill，想知道哪个最差

**适用**：维护 10 个以上 Skill 的人、要把技能库整体提质量的团队。
**耗时**：一条命令，几十个技能也就半分钟到一分钟。

### 步骤

```bash
cd ~/.workbuddy/skills/skill-inspector

# 1. 并行扫整个父目录（自动发现含 SKILL.md 的目录，最多下钻 3 层）
python3 scripts/batch_audit.py --root ~/.workbuddy/skills --jobs 4

# 2. 打开看板
open BATCH-AUDIT.md      # macOS；Linux 用 xdg-open
```

### 看板怎么读（三块，按这个顺序看）

1. **共性问题**——同一条规则命中好几个技能，说明是写法习惯问题。
   例如 `STRUCT-003`（缺"何时使用"）命中 5 个技能，那就统一补，而不是逐个纠结。
2. **总览表**——按 TRACE 从低到高排，最差的在最上面。先挑 2–3 个最差的做深度优化。
3. **待修清单**——high/medium 条目带文件与行号，照着改；改完重跑一次对比。

### 和 run_all 的分工

| 需求 | 用哪个 |
|------|--------|
| 看整体质量分布、找共性短板 | `batch_audit.py` |
| 某个技能要完整体检报告（7 节 REPORT.md） | `run_all.py <该技能>` |
| CI 里卡住不合格的技能 | `batch_audit.py --fail-on high --fail-under 80`（退出码 2） |

### 两个坑

- **批量模式是只读的**：它不会在目标目录建 `.skill-audit/`，所以你看不到单技能的 REPORT.md，这是有意的。
- **门禁口径不同**：批量模式的 `--fail-on` 把语义发现（SEM-*）也算进去，比 `run_all` 严格；
  `--fail-under` 要求**每个**技能都达标，不是看平均分。

---

## 更多小技巧

- **只想知道能不能改**：先跑 `--dry-run`，零风险。
- **某个规则总误报**：在 `config.json` 里把该 `rule_id` 的 `enabled` 设成 `false`。
- **要审多个 Skill**：用 `batch_audit.py`（见场景四），别再自己写 for 循环——并行、只读、还给看板。
- **要归档报告**：把 `.skill-audit/` 目录一起提交到版本控制，方便追踪质量变化。
- **新手最省事**：直接 `python3 <skill-inspector>/scripts/run_all.py <目标Skill>`，一条命令出报告。

---

## 最佳实践

### 发布前自检清单（5 步，5 分钟）

```bash
cd ~/.workbuddy/skills/skill-inspector
python3 scripts/run_all.py ~/.workbuddy/skills/你的Skill   # ① 全流程报告
python3 scripts/diagnose.py ~/.workbuddy/skills/你的Skill  # ② 环境/文件健康
```

1. **看 TRACE 总分与最弱维度**——总分 ≥90（A）才建议上架；最弱维度就是优化优先级。
2. **看 high 级发现**——报告第 3 节里 high 级必须先清零（缺失脚本、死引用、冲突指令）。
3. **检查 description 是否写了"何时用"**——用一句话回答"什么时候该触发它"，这是 C/E 两维的命门。
4. **确认离线可用**——references/、assets/ 全部自带，无外部链接依赖。
5. **跑一次 `--dry-run` 优化预览**——只读查看建议，确认无误再决定是否落盘。

### TRACE 各维度保分要点

| 维度 | 保分要点 | 常见扣分原因 |
|------|----------|-------------|
| T | 无硬编码密钥；无绝对化表述；有隐私/本地声明；引用可溯源 | "100% 准确""永远"这类词；密钥硬编码 |
| R | 错误处理有具体话术；边界有具名场景；示例可执行 | 只有口号式边界说明；示例命令不可跑 |
| A | 有 `--config` 与 config 示例；有扩展钩子说明；触发方式清晰 | 只写"可配置"三字没有示例 |
| C | frontmatter 齐全；目录规范；细节外置；有反模式/FAQ | description 没讲何时用；正文堆 3000 行 |
| E | description 与能力一致；有明确交付物；开箱即用 | description 夸大能力；报告只是空壳 |

### 真实优化案例 2 例

**案例 A：术语统一（SEM-003）**
某 Skill 混用"Skill / skill / 技能"三种写法 47 处 → 用 `optimize_apply.py --dry-run` 预览，确认归一为"Skill"（标题/句首自动保护），落盘后 TRACE C 维度提升 0.3。教训：**术语不统一会让评测者觉得"不专业"，一次归一见效最快。**

**案例 B：边界补全（R 维度）**
某 Skill 只有"本技能能处理各种边界情况"一句话 → 补成具体话术："当目标路径不存在时提示'请确认路径'；当 SKILL.md 超过 512 KB 时建议拆分到 references/"，R 维度从 4.3 提到 4.8。教训：**边界说明要"可操作"，评测者看得懂才算数。**
