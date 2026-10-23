# 安全规则（SEC-*）与 OWASP Agentic Skills 映射

`scripts/security_analyzer.py` 的规则集。设计前提：**Skill 的威胁有两层**——代码层
（shell / Python）和自然语言指令层（markdown 正文）。传统密钥扫描器只读前一层，
而近年攻击（ClawHavoc 等）恰恰把 payload 藏在 SKILL.md 的散文里。所以本扫描器
两层都读，逐行扫 SKILL.md 与每个文本文件。

> 本文是规则说明，表格里出现的都是**待检模式的写法示意**，不是可执行指令，故整文件豁免：
> skill-inspector: ignore-file SEC-001,SEC-003,SEC-004,SEC-005,SEC-008

## 规则表

| 规则 | 名称 | 严重度 | OWASP AST | 检出的典型模式 |
|------|------|--------|-----------|----------------|
| SEC-001 | 危险命令 | high | AST01 Malicious Skills | `curl … \| sh`、`base64 -d … \| sh`、`nc -e`、`/dev/tcp/`、`rm -rf ~`、写 shell 启动文件、`chmod 777`、关闭 TLS 校验 |
| SEC-002 | 敏感读取 + 外发 | high | AST01 | 同一文件既读 `~/.ssh` / `.env` / 凭据 / 浏览器数据，又具备 `curl POST`、webhook、pastebin、ngrok 等出口 |
| SEC-003 | 越权或隐蔽指令 | high | AST05 Untrusted External Instructions | "忽略之前的指令"、要求输出/泄露系统提示、"不要告诉用户"、`hide … from the user` |
| SEC-004 | 过度授权 | medium | AST03 Over-Privileged Skills | `allowed-tools: "*"`、`Bash(*)`、`shell=True` |
| SEC-005 | 硬编码凭据 | high | AST04 Insecure Metadata | GitHub token、`sk-`、AWS AKIA、Slack token、私钥块（**报告内一律脱敏**） |
| SEC-006 | 写身份/记忆/配置 | high | AST01 + AST03 | 往 `SOUL.md` / `MEMORY.md` / `AGENTS.md` / 宿主 `settings.json` 写入（持久化后门、身份克隆） |
| SEC-007 | 隐藏 Unicode | medium | AST05 | 零宽字符（U+200B–200F）、双向控制符（U+202A–202E）、BOM 夹带 |
| SEC-008 | 跨文件读+发组合 | medium | AST01 | A 文件里 `cat … ~/.ssh` 一类的**读取动作**，B 文件里 `curl -d/-F`、`requests.post`、webhook 一类的**发送动作**——拆成两个文件规避 SEC-002 的常见手法 |

## 三个防误报机制

1. **教材语境降级**：命中行含 `反模式 / 示例 / 不要 / 禁止 / avoid / ❌` 等词时，
   严重度降一级并在证据前标注「示例/反模式语境，请人工确认」——讲"别这么写"的
   文档不该和真攻击同罪，但**仍然报出来**给人看。
2. **行内 / 文件级抑制**（同 semgrep、`# nosec` 的思路）：

   ```text
   skill-inspector: ignore SEC-001,SEC-007     # 只豁免本行
   skill-inspector: ignore-file SEC-002        # 豁免整个文件
   skill-inspector: ignore ALL                 # 本行全豁免
   ```

   抑制必须写出来、可被 review 看见，而不是靠"扫描器恰好没报"。
3. **规则开关**：`config.json` 里 `{"rules": {"SEC-004": {"enabled": false}}}`。

## 诚实边界

- 这是**正则启发式**，不是行为分析。它读不懂"这个脚本实际会做什么"。
- 未命中 ≠ 安全。它只保证"没撞上这 8 类已知模式"。
- 高误报风险场景：安全类文档、测试夹具、规则库自身——用抑制标记显式说明，
  而不是关掉规则。
- **跨文件拆分只做到"两段证据碰面"**：SEC-002 判同文件；SEC-008 补跨文件——但要求两侧都是
  **动作级证据**（`cat … ~/.ssh` 这类读取动作 + `curl -d` / `requests.post` 这类发送动作），
  且只报 medium。它看不见"数据从 A 流到 B"的真实链路，也无法识别先加密再外发、变量间传递、
  运行时拼路径这些手法。挡的是粗糙投毒，不是精细渗透。
- 不能替代：依赖审计（SBOM / CVE）、签名校验、沙箱隔离、运行时日志。AST01 的
  预防措施里，静态扫描只占一项。

## 参考

- OWASP Agentic Skills Top 10（AST01–AST10）与配套 Skill Security Assessment Checklist
- agentskills.io / Agent Skills 规范（渐进式披露、name/description 约束）
- 同类开源扫描器的规则切分方式（SX-CMD / SX-EXF / SX-INJ / SX-PRM / SX-SEC / SX-UNI）
