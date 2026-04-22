#!/usr/bin/env python3
"""综合测试 - 一次性测试所有模块"""
import sys
import io
from pathlib import Path

# 修复 Windows 编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("股票筛选系统 - 模块测试")
print("=" * 60)

def test_module(name, module_path):
    """测试模块导入"""
    try:
        __import__(module_path)
        print(f"✓ {name}")
        return True
    except Exception as e:
        print(f"✗ {name}: {e}")
        return False

# 测试列表
tests = [
    ("core.config", "core.config"),
    ("core.financial_data", "core.financial_data"),
    ("core.watchlist", "core.watchlist"),
    ("gui.main_window", "gui.main_window"),
    ("gui.navigation", "gui.navigation"),
    ("gui.tabs.base_tab", "gui.tabs.base_tab"),
    ("gui.tabs.financial_tab", "gui.tabs.financial_tab"),
    ("gui.tabs.watchlist_tab", "gui.tabs.watchlist_tab"),
]

passed = 0
failed = 0

for name, module in tests:
    if test_module(name, module):
        passed += 1
    else:
        failed += 1

print("\n" + "=" * 60)
print(f"测试结果: {passed} 通过, {failed} 失败")
print("=" * 60)

if failed == 0:
    print("✅ 所有模块导入正常！")
    sys.exit(0)
else:
    print("❌ 部分模块有问题，请检查")
    sys.exit(1)
