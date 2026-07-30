# skill-auditor 场景案例手册（Cookbook）

> 像菜谱一样可照着做的 3 个完整场景：审查一个臃肿 Skill、给 Skill 冲 TRACE 高分、安全地优化并对比前后。

---

## 自然语言使用速查（无需记命令）

除了对 skill-auditor 说"审查这个 skill"，你也可以直接用下面这些日常说法：

| 你想做什么 | 可以直接这样说 |
|-----------|---------------|
| 审查某个 Skill 的质量 | "帮我审一下 ~/.workbuddy/skills/example" |
| 看 TRACE 评分 | "给这个 skill 跑个 TRACE" / "评测一下质量" |
| 检查语义问题 | "看看这个 SKILL.md 有没有重复、冲突" |
| 安全优化 | "帮我优化这个 skill" / "补全 frontmatter 和触发词" |
| 生成最终报告 | "把审计结果汇总成 REPORT.md" |
| 只看不动 | "先预览一下会改哪些地方" |

> skill-auditor 会先进入审计阶段；如果你没指定路径，它会追问"要审哪个 Skill"。

---

## 场景一：审查一个"越来越长"的 Skill

**背景**：你的 Skill 经过多轮迭代，SKILL.md 从 800 字涨到 4000 字，你怀疑里面有重复提示词、死链接、该外置的细节没外置。

**目标**：快速拿到问题清单，不动原文件。

### 步骤

```bash
# 1. 进入 skill-auditor 目录
cd ~/.workbuddy/skills/skill-auditor

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

**背景**：审查发现术语混用、frontmatter 缺字段、有连续重复文本，你想让 skill-auditor 自动修，但怕改坏。

**目标**：先预览，确认后再落盘，且保留回退能力。

### 步骤

```bash
# 0. 先合并审计发现为一个 findings.json
cd /path/to/your/skill
mkdir -p .skill-audit

# 1. 生成 findings.json（这里手动合并示例；实际可用脚本或让 skill-auditor 自动合并）
python3 ~/.workbuddy/skills/skill-auditor/scripts/audit_skill.py . --json > .skill-audit/audit.json
python3 ~/.workbuddy/skills/skill-auditor/scripts/semantic_analyzer.py SKILL.md --json > .skill-audit/semantic.json

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
python3 ~/.workbuddy/skills/skill-auditor/scripts/optimize_apply.py . \
  --findings .skill-audit/findings.json --dry-run

# 4. 检查 diff 满意后，确认落盘
python3 ~/.workbuddy/skills/skill-auditor/scripts/optimize_apply.py . \
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

## 更多小技巧

- **只想知道能不能改**：先跑 `--dry-run`，零风险。
- **某个规则总误报**：在 `config.json` 里把该 `rule_id` 的 `enabled` 设成 `false`。
- **要审多个 Skill**：写个 shell for 循环，批量跑 `audit_skill.py` 和 `trace_eval.py`。
- **要归档报告**：把 `.skill-audit/` 目录一起提交到版本控制，方便追踪质量变化。
