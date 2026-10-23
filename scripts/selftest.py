#!/usr/bin/env python3
"""selftest.py — 一条命令跑本 Skill 自带的全部单元 / 端到端测试。

  python3 scripts/selftest.py              # 全部
  python3 scripts/selftest.py -k sarif     # 只跑 id 里含 sarif 的用例

只用标准库（unittest discover），不需要 pytest，也不联网。
退出码：0 全通过；1 有失败。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _flatten(suite):
    for t in suite:
        if isinstance(t, unittest.TestSuite):
            yield from _flatten(t)
        else:
            yield t


def main(argv):
    keyword = None
    if "-k" in argv:
        i = argv.index("-k")
        keyword = argv[i + 1] if i + 1 < len(argv) else None

    suite = unittest.defaultTestLoader.discover(
        os.path.join(ROOT, "tests"), top_level_dir=ROOT)
    if keyword:
        picked = unittest.TestSuite(
            t for t in _flatten(suite) if keyword.lower() in t.id().lower())
        suite = picked
        print("筛选：id 含 %r 的用例 %d 项" % (keyword, suite.countTestCases()))

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("\n== 自测结果 ==")
    # 平台信息进日志：CI 三平台矩阵跑同一份用例，出问题第一眼看这里
    print("  平台: %s / Python %s" % (sys.platform, sys.version.split()[0]))
    print("  用例: %d 项，失败 %d，错误 %d" %
          (result.testsRun, len(result.failures), len(result.errors)))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
