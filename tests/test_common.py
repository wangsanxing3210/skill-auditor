"""共享工具与解析层的单元测试（stdlib unittest，无第三方依赖）。

运行：
  python3 scripts/selftest.py
或
  python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPT_DIR)

import _common as C  # noqa: E402


class TestSlugifyAnchor(unittest.TestCase):
    def test_ascii_heading(self):
        self.assertEqual(C.slugify_anchor("Hello World"), "hello-world")

    def test_cjk_heading(self):
        # 中文标题保留字符，去掉标点
        self.assertEqual(C.slugify_anchor("能力边界（异常处理）"), "能力边界异常处理")

    def test_punctuation_and_spaces(self):
        self.assertEqual(C.slugify_anchor("  A / B: C?  "), "a-b-c")

    def test_parens_removed(self):
        self.assertEqual(C.slugify_anchor("中文（English）"), "中文english")

    def test_empty(self):
        self.assertEqual(C.slugify_anchor(None), "")
        self.assertEqual(C.slugify_anchor(""), "")


class TestStripHelpers(unittest.TestCase):
    def test_strip_code_fences_removes_fence_and_inline(self):
        text = "前 `100%` 中\n```bash\nrm -rf /\n```\n后"
        out = C.strip_code_fences(text)
        self.assertNotIn("100%", out)
        self.assertNotIn("rm -rf", out)
        self.assertIn("前", out)

    def test_strip_quoted_examples_cjk_and_ascii(self):
        text = '含「100% 准确」与“永远不出错”与 "always accurate" 三个引号'
        out = C.strip_quoted_examples(text)
        self.assertNotIn("100%", out)
        self.assertNotIn("永远", out)
        self.assertNotIn("always accurate", out)
        self.assertIn("三个引号", out)

    def test_strip_quoted_examples_keeps_bare_text(self):
        text = "本技能保证 100% 正确"
        self.assertIn("100%", C.strip_quoted_examples(text))


class TestFrontmatter(unittest.TestCase):
    def test_valid(self):
        fm, body, ok = C.parse_frontmatter("---\nname: x\ndescription: y\n---\n\n# T\n")
        self.assertTrue(ok)
        self.assertEqual(fm["name"], "x")
        self.assertEqual(fm["description"], "y")
        self.assertIn("# T", body)

    def test_quoted_value(self):
        fm, _, ok = C.parse_frontmatter("---\nname: 'a-b'\ndescription: \"d\"\n---\nx")
        self.assertTrue(ok)
        self.assertEqual(fm["name"], "a-b")
        self.assertEqual(fm["description"], "d")

    def test_missing(self):
        fm, _, ok = C.parse_frontmatter("# no frontmatter\n")
        self.assertFalse(ok)
        self.assertEqual(fm, {})


class TestConfig(unittest.TestCase):
    def test_defaults_present(self):
        cfg = C.read_config(None)
        self.assertIn("weights", cfg)
        for dim in ("T", "R", "A", "C", "E"):
            self.assertIn(dim, cfg["weights"])
        self.assertAlmostEqual(sum(cfg["weights"].values()), 1.0, places=6)

    def test_missing_file_falls_back(self):
        cfg = C.read_config("/nonexistent/config.json")
        self.assertIn("thresholds", cfg)


class TestReferencedPaths(unittest.TestCase):
    def test_collects_three_kinds(self):
        body = "见 references/a.md 与 scripts/b.py 和 assets/c.json"
        got = C.referenced_paths(body)
        self.assertIn("references/a.md", got)
        self.assertIn("scripts/b.py", got)
        self.assertIn("assets/c.json", got)


class TestMakeFinding(unittest.TestCase):
    def test_shape(self):
        f = C.make_finding("X-1", "high", "structure", "SKILL.md", "ev", "rec")
        self.assertEqual(set(f), {"rule_id", "severity", "category", "location", "evidence", "recommendation"})


class TestCrossPlatform(unittest.TestCase):
    """跨平台契约：路径统一 `/`、子进程强制 UTF-8、标准输出可安全输出中文。

    这三条是 Windows 上最容易静默出错的地方——在 macOS 上跑全绿不代表 Windows 能跑，
    所以把契约写成用例，交给 CI 的三个平台各自验证。
    """

    def test_posix_rel_uses_forward_slash(self):
        rel = C.posix_rel(os.path.join("a", "b", "c.md"), "a")
        self.assertEqual(rel, "b/c.md")
        self.assertNotIn(os.sep if os.sep != "/" else "\\", rel)

    def test_loaded_skill_files_use_posix_paths(self):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="si-xplat-")
        try:
            os.makedirs(os.path.join(tmp, "references"))
            with open(os.path.join(tmp, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: xplat\ndescription: 跨平台用例，当需要验证路径分隔符时使用\n---\n\n# X\n")
            with open(os.path.join(tmp, "references", "a.md"), "w", encoding="utf-8") as f:
                f.write("ref\n")
            skill = C.load_skill(tmp)
            self.assertIn("references/a.md", skill["files"])
            for rel in skill["files"]:
                self.assertNotIn("\\", rel, "文件清单里不应出现反斜杠：%s" % rel)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_child_env_forces_utf8(self):
        env = C.child_env()
        self.assertEqual(env.get("PYTHONIOENCODING"), "utf-8")
        self.assertEqual(env.get("PYTHONUTF8"), "1")

    def test_stdout_can_emit_chinese(self):
        enc = (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "")
        if not hasattr(sys.stdout, "reconfigure") or not enc:
            self.skipTest("当前 stdout 不支持 reconfigure，跳过")
        self.assertIn("utf8", enc)
        sys.stdout.write("中文输出自检\n")   # 编码不对时这里会抛 UnicodeEncodeError
        sys.stdout.flush()


if __name__ == "__main__":
    unittest.main(verbosity=2)
