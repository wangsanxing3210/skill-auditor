#!/usr/bin/env python3
"""security_analyzer.py — 启发式安全扫描（对标 OWASP Agentic Skills Top 10）。

设计取向与"密钥扫描器"不同：Skill 的威胁同时存在于**代码层**（shell / python）
与**自然语言指令层**（markdown 正文）。因此本脚本逐行扫描 SKILL.md 正文和
每一个文本文件，两类命中都报。

规则族（SEC-*）与 OWASP AST 编号的对应见 references/security-rules.md：

  SEC-001 危险命令                    AST01 Malicious Skills
  SEC-002 敏感读取 + 网络外发          AST01 Malicious Skills
  SEC-003 越权/隐蔽指令（提示注入）     AST05 Untrusted External Instructions
  SEC-004 过度授权                     AST03 Over-Privileged Skills
  SEC-005 硬编码凭据                   AST04 Insecure Metadata
  SEC-006 写入身份/记忆/配置           AST01 + AST03
  SEC-007 隐藏 Unicode                 AST05 Untrusted External Instructions
  SEC-008 跨文件读取+外发组合           AST01 Malicious Skills

诚实边界：这是**正则启发式**，不是行为分析。命中要人读，不替代深度审计；
教材/反模式语境里的示例会被降一级并标注「示例语境」。全离线、零依赖。

抑制标记（同 semgrep / `# nosec` 思路，写在被豁免的那一行或文件任意处）：

    skill-inspector: ignore SEC-001,SEC-007        # 只豁免本行
    skill-inspector: ignore-file SEC-002           # 豁免整个文件
    skill-inspector: ignore ALL                    # 本行全豁免

Usage:
  python3 security_analyzer.py <target> [--json] [--config config.json]
"""
import os
import re
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C

# 本文件就是规则定义本身，命中自己的模式属预期：
# skill-inspector: ignore-file SEC-001,SEC-002,SEC-008

# 扫描预算：单文件超过此大小只扫前 N 字节，避免把仓库级文件全读进内存
MAX_SCAN_BYTES = 512 * 1024

RULE_META = {
    "SEC-001": ("high", "AST01", "危险命令：远程脚本直连 shell、反连、破坏性删除"),
    "SEC-002": ("high", "AST01", "敏感数据读取与网络外发同时出现"),
    "SEC-003": ("high", "AST05", "越权或隐蔽指令（提示注入）"),
    "SEC-004": ("medium", "AST03", "过度授权：通配工具、无限制 shell"),
    "SEC-005": ("high", "AST04", "硬编码凭据"),
    "SEC-006": ("high", "AST01", "写入身份/记忆/宿主配置文件"),
    "SEC-007": ("medium", "AST05", "隐藏 Unicode（零宽/双向控制字符）"),
    "SEC-008": ("medium", "AST01", "跨文件组合：一处读取敏感数据、另一处具备外发能力"),
}

# 教材/反模式语境标记：命中这些词的行降一级严重度并标注，避免自审误报
TEACHING_MARKERS = (
    "反模式", "反例", "错误示范", "不要", "禁止", "避免", "示例", "例如",
    "anti-pattern", "avoid", "do not", "don't", "never", "bad example", "❌",
)

# 行内抑制标记（同 semgrep/nosec 的 # nosec 思路）：
#   skill-inspector: ignore SEC-001,SEC-002    只对本行抑制指定规则
#   skill-inspector: ignore-file SEC-002       对整个文件抑制指定规则
#   ignore ALL / ignore-file ALL               抑制全部
_RID = r"[A-Z]{3}-\d{3}"
SUPPRESS_LINE = re.compile(
    r"(?:skill-inspector|skill-auditor)\s*:\s*ignore(?!-file)\s*[:\s]\s*"
    r"(ALL|%s(?:\s*,\s*%s)*)" % (_RID, _RID), re.I)
SUPPRESS_FILE = re.compile(
    r"(?:skill-inspector|skill-auditor)\s*:\s*ignore-file\s*[:\s]\s*"
    r"(ALL|%s(?:\s*,\s*%s)*)" % (_RID, _RID), re.I)


# (rule_id, 正则, 证据模板) —— 正则一律忽略大小写
PATTERNS = [
    # --- SEC-001 危险命令 ---
    ("SEC-001", r"(?:curl|wget)\b[^\n|]{0,120}\|\s*(?:sudo\s+)?(?:ba|z)?sh\b",
     "远程脚本直接管道进 shell"),
    ("SEC-001", r"base64\s+(?:-d|--decode)[^\n|]{0,80}\|\s*(?:ba|z)?sh\b",
     "base64 解码后直接执行"),
    ("SEC-001", r"\b(?:nc|ncat|netcat)\s+(?:-[a-z]*e|--exec)\b|/dev/tcp/",
     "反连 shell（nc -e / /dev/tcp）"),
    ("SEC-001", r"\brm\s+-[a-z]*r[a-z]*f?[a-z]*\s+(?:~|/|\$HOME)(?:\s|$|\*)",
     "对家目录或根目录的递归删除"),
    ("SEC-001", r">>?\s*~?/?\.(?:zshrc|bashrc|bash_profile|zprofile|profile)\b",
     "写入 shell 启动文件（持久化）"),
    ("SEC-001", r"\bchmod\s+(?:-R\s+)?777\b",
     "chmod 777 放宽权限"),
    ("SEC-001", r"verify\s*=\s*False|--insecure\b|InsecureSkipVerify",
     "关闭 TLS 证书校验"),
    # --- SEC-003 越权 / 隐蔽指令 ---
    ("SEC-003", r"忽略(?:掉)?(?:之前|以上|前面|先前)的?(?:所有)?(?:指令|规则|设定)",
     "要求忽略既有指令"),
    ("SEC-003", r"ignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above)\s+"
                r"(?:instructions?|rules?|prompts?)",
     "要求忽略既有指令（英文）"),
    ("SEC-003", r"(?:泄露|输出|打印|reveal|print|dump)\s*(?:你的|your)?\s*"
                r"(?:系统提示词|system\s*prompt|hidden\s*instructions?)",
     "要求泄露系统提示"),
    ("SEC-003", r"不要(?:告诉|告知|提醒)(?:用户|使用者)|不要让用户(?:知道|察觉)",
     "要求对用户隐瞒行为"),
    ("SEC-003", r"(?:hide|conceal)\s+(?:this|it|the\s+action)\s+from\s+the\s+user",
     "要求对用户隐瞒行为（英文）"),
    # --- SEC-004 过度授权 ---
    ("SEC-004", r"allowed-tools\s*:\s*(?:\[?\s*[\"']?\*[\"']?\s*\]?|[\"']?\*[\"']?)",
     "allowed-tools 授予全部工具"),
    ("SEC-004", r"\bBash\(\s*\*\s*\)|\bshell\s*=\s*True\b",
     "无限制 shell 执行"),
    # --- SEC-005 硬编码凭据（证据必须脱敏） ---
    ("SEC-005", r"gh[pousr]_[A-Za-z0-9]{20,}", "GitHub token"),
    ("SEC-005", r"github_pat_[A-Za-z0-9_]{20,}", "GitHub fine-grained token"),
    ("SEC-005", r"sk-[A-Za-z0-9]{20,}", "OpenAI/Anthropic 风格密钥"),
    ("SEC-005", r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    ("SEC-005", r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack token"),
    ("SEC-005", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "私钥块"),
    # --- SEC-006 写入身份/记忆/宿主配置 ---
    ("SEC-006", r"(?:write|写入|追加|append|覆盖|save|>>?)"
                r"[^\n]{0,60}?(?:SOUL|MEMORY|AGENTS|IDENTITY|CLAUDE|USER)\.md",
     "写入 Agent 身份/记忆文件"),
    ("SEC-006", r"(?:write|写入|追加|append|>>?)"
                r"[^\n]{0,60}?\.(?:claude|codebuddy|workbuddy)/(?:settings|config)[\w.]*\.json",
     "写入宿主配置文件"),
]

# SEC-002：同一文件内同时出现"敏感读取"与"网络外发"才报
SENSITIVE = re.compile(
    r"(?:~/\.ssh|id_rsa|id_ed25519|\.env\b|credentials|keychain|\.aws/|\.netrc|"
    r"Cookies|Login Data|wallet\.dat|\.kube/config)", re.I)
EGRESS = re.compile(
    r"(?:curl|wget|requests\.post|requests\.put|http\.client|urllib\.request|"
    r"webhook\.site|pastebin|ngrok|0x0\.st|transfer\.sh|/dev/tcp/)", re.I)

HIDDEN_UNICODE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")

# SEC-008 跨文件组合：把"读敏感数据"和"网络外发"拆到两个文件里，是绕开
# SEC-002（同文件判定）最常见的手法。这里两侧都要求**动作级证据**，而不是
# 只要出现关键词——否则一份讲安全的文档、一个测试夹具就会被误判。
SENSITIVE_READ = re.compile(
    r"(?:\b(?:cat|cp|scp|rsync|tar|zip|grep|awk|sed|base64|xxd|strings|"
    r"Get-Content|open|read_text|read_bytes|readFile)\b[^\n|]{0,80}?"
    r"(?:~/\.ssh|\.ssh/|id_rsa|id_ed25519|\.env\b|credentials|keychain|"
    r"\.aws/|\.netrc|wallet\.dat|\.kube/config))"
    r"|(?:(?:~/\.ssh|id_rsa|id_ed25519|\.aws/|\.netrc|wallet\.dat|\.kube/config)"
    r"[^\n|]{0,40}\|\s*(?:curl|nc|ncat)\b)", re.I)

EGRESS_SEND = re.compile(
    r"(?:curl\b[^\n]{0,120}?(?:-d\b|-F\b|-T\b|--data|--upload-file|-X\s*POST)"
    r"|wget\b[^\n]{0,120}?--post-(?:data|file)"
    r"|requests\.(?:post|put)\b|http\.client|urllib\.request"
    r"|webhook\.site|pastebin\.com|transfer\.sh|0x0\.st|ngrok\.io"
    r"|/dev/tcp/|\bnc\s+-[a-z]*e\b)", re.I)


def _downgrade(sev):
    return {"high": "medium", "medium": "low", "low": "low"}.get(sev, sev)


def _redact(text, keep=4):
    """凭据一律脱敏：保留前缀便于定位，其余打码。"""
    return text[:keep] + "*" * max(4, min(12, len(text) - keep))


def _iter_text_files(skill_dir, files):
    """依次产出 (相对路径, 内容)。非 UTF-8 / 超大文件跳过。"""
    for rel in sorted(files):
        if rel.startswith(".skill-audit/") or rel.startswith(".git/"):
            continue
        full = os.path.join(skill_dir, rel)
        try:
            if os.path.getsize(full) > MAX_SCAN_BYTES:
                continue
            with open(full, "r", encoding="utf-8") as f:
                yield rel, f.read()
        except (UnicodeDecodeError, OSError):
            continue


def _parse_ids(s):
    s = (s or "").strip()
    if s.upper() == "ALL":
        return {"ALL"}
    return {x.strip().upper() for x in s.split(",") if x.strip()}


def _is_off(rid, off_set):
    return "ALL" in off_set or rid in off_set


def scan_text(rel, text, file_off=frozenset()):
    """扫描单个文件的文本，返回 raw hits。

    raw_hits: list of (rule_id, line_no, snippet, note, teaching)
    """
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        off = set(file_off)
        m = SUPPRESS_LINE.search(line)
        if m:
            off |= _parse_ids(m.group(1))
        teaching = any(t in line.lower() for t in TEACHING_MARKERS)
        for rid, pat, note in PATTERNS:
            if _is_off(rid, off):
                continue
            hit = re.search(pat, line, re.I)
            if not hit:
                continue
            snippet = hit.group(0)
            if rid == "SEC-005":
                snippet = _redact(snippet)
            hits.append((rid, i, snippet, note, teaching))
        if not _is_off("SEC-007", off):
            for h in HIDDEN_UNICODE.finditer(line):
                hits.append(("SEC-007", i, "U+%04X" % ord(h.group(0)),
                             "隐藏字符，正常文本不需要", teaching))
    return hits


def analyze(skill, cfg):
    rules = cfg.get("rules", {})
    findings = []
    per_file = {}
    for rel, text in _iter_text_files(skill["dir"], skill["files"]):
        per_file[rel] = text
        file_off = set()
        for m in SUPPRESS_FILE.finditer(text):
            file_off |= _parse_ids(m.group(1))
        for rid, line_no, snippet, note, teaching in scan_text(rel, text, file_off):
            base_sev, ast, title = RULE_META[rid]
            sev = _downgrade(base_sev) if teaching else base_sev
            ev = "%s：`%s`" % (note, snippet)
            if teaching:
                ev = "（示例/反模式语境，请人工确认）" + ev
            f = C.make_finding(rid, sev, "security", "%s:%d" % (rel, line_no), ev,
                               _recommend(rid, note))
            f["owasp"] = ast
            f["title"] = title
            findings.append(f)

    # --- SEC-002 文件级组合判定 ---
    for rel, text in per_file.items():
        file_off = set()
        for m in SUPPRESS_FILE.finditer(text):
            file_off |= _parse_ids(m.group(1))
        if _is_off("SEC-002", file_off):
            continue
        if SENSITIVE.search(text) and EGRESS.search(text):
            sev, ast, title = RULE_META["SEC-002"]
            f = C.make_finding("SEC-002", sev, "security", rel,
                               "同一文件既读取敏感数据（密钥/凭据/浏览器数据）又具备网络外发能力",
                               _recommend("SEC-002", "敏感读取 + 外发"))
            f["owasp"] = ast
            f["title"] = title
            findings.append(f)

    # --- SEC-008 跨文件组合判定 ---
    # 只有当"读"和"发"落在**不同文件**时才报，避免与 SEC-002 重复报同一件事。
    def _off_of(text):
        s = set()
        for m in SUPPRESS_FILE.finditer(text):
            s |= _parse_ids(m.group(1))
        return s

    readers, senders = [], []
    for rel, text in per_file.items():
        off = _off_of(text)
        if _is_off("SEC-008", off):
            continue
        if SENSITIVE_READ.search(text):
            readers.append(rel)
        if EGRESS_SEND.search(text):
            senders.append(rel)
    for r in readers:
        others = [s for s in senders if s != r]
        if not others:
            continue       # 同一文件的情形由 SEC-002 负责
        sev, ast, title = RULE_META["SEC-008"]
        shown = "、".join(others[:3]) + ("等 %d 处" % len(others) if len(others) > 3 else "")
        f = C.make_finding(
            "SEC-008", sev, "security", r,
            "%s 读取敏感数据，而 %s 具备网络外发能力——拆成两个文件同样构成外发链，请人工确认二者是否配套" % (r, shown),
            _recommend("SEC-008", "跨文件外发链"))
        f["owasp"] = ast
        f["title"] = title
        findings.append(f)

    # 去重 + 按规则开关过滤
    out, seen = [], set()
    for f in findings:
        key = (f["rule_id"], f["location"])
        if key in seen:
            continue
        seen.add(key)
        en, sev = C.ref_enabled(rules, f["rule_id"], f["severity"])
        if not en:
            continue
        f["severity"] = sev
        out.append(f)
    out.sort(key=lambda x: ({"high": 0, "medium": 1, "low": 2}.get(x["severity"], 3), x["rule_id"]))
    return out


def _recommend(rid, note):
    table = {
        "SEC-001": "删掉该命令；确需安装则先下载脚本、人读一遍再执行",
        "SEC-002": "去掉外发那一半；凭据从环境变量在运行时读取，绝不随 Skill 分发",
        "SEC-003": "删掉该指令——Skill 描述能力，不指挥 Agent 绕过规则或对用户隐瞒",
        "SEC-004": "只声明本技能真正需要的最小权限，避免通配与无限制 shell",
        "SEC-005": "立即轮换该凭据，改为运行时从环境变量读取",
        "SEC-006": "Skill 不应写 Agent 身份/记忆或宿主配置；改为向用户输出建议，由其确认",
        "SEC-007": "删除隐藏字符（复制粘贴时常见），用纯文本重写该段",
        "SEC-008": "确认这两处是否属于同一条外发链：属于就删掉外发端；不属于则在配置里关掉 SEC-008 并写明理由",
    }
    return table.get(rid, "人工复核该处")


def summarize(findings):
    by_ast = {}
    for f in findings:
        by_ast.setdefault(f.get("owasp", "—"), 0)
        by_ast[f["owasp"]] += 1
    sev = {}
    for f in findings:
        sev[f["severity"]] = sev.get(f["severity"], 0) + 1
    return {"total": len(findings), "by_severity": sev, "by_owasp": by_ast}


def main():
    ap = argparse.ArgumentParser(description="启发式安全扫描（OWASP Agentic Skills AST）")
    ap.add_argument("target", help="Skill 目录或 SKILL.md 路径")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--config", default=None, help="config.json 路径（可用 rules 关闭单条规则）")
    args = ap.parse_args()

    try:
        cfg = C.read_config(args.config)
        skill = C.load_skill(args.target)
        findings = analyze(skill, cfg)
    except Exception as e:
        code, message, next_step = C.humanize_error(e, "security_analyzer")
        if args.json:
            print(json.dumps({"ok": False, "error": {"code": code, "message": message,
                                                     "next_step": next_step}}, ensure_ascii=False, indent=2))
        else:
            print("[%s] %s" % (code, message))
            if next_step:
                print("下一步: %s" % next_step)
        sys.exit(1)

    summary = summarize(findings)
    if args.json:
        print(json.dumps({"ok": True, "target": skill["dir"], "count": len(findings),
                          "summary": summary, "findings": findings}, ensure_ascii=False, indent=2))
        return

    print("安全扫描 %s（%d 条）" % (skill["dir"], len(findings)))
    for f in findings:
        print("  [%s] %s %s @ %s — %s" % (f["severity"], f["rule_id"], f["owasp"],
                                          f["location"], f["evidence"]))
    if not findings:
        print("  未发现已知的高危模式；这不等于安全，仅代表没撞上规则集。")


if __name__ == "__main__":
    main()
