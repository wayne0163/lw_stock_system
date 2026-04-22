import tkinter as tk
from tkinter import messagebox, simpledialog
import threading
import subprocess
import os
import sys
from pathlib import Path

def center_window(window, parent):
    """
    将窗口居中显示在父窗口范围内
    :param window: 需要居中的窗口 (Toplevel)
    :param parent: 父窗口 (Tk 或 Toplevel)
    """
    window.update_idletasks()
    
    # 获取父窗口的位置和尺寸
    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()
    
    # 获取子窗口的尺寸
    window_width = window.winfo_width()
    window_height = window.winfo_height()
    
    # 计算居中位置
    x = parent_x + (parent_width // 2) - (window_width // 2)
    y = parent_y + (parent_height // 2) - (window_height // 2)
    
    # 防止窗口超出屏幕左上角
    x = max(0, x)
    y = max(0, y)
    
    window.geometry(f"+{x}+{y}")

def generate_stock_report(parent, ts_code, name=None):
    """
    调用后台脚本生成深度财务报告
    :param parent: 父窗口（用于显示弹窗）
    :param ts_code: 股票代码
    :param name: 股票名称（可选）
    """
    if not ts_code:
        ts_code = simpledialog.askstring("生成财务报告", "请输入股票代码 (如 301389.SZ):", parent=parent)
        if not ts_code: return

    def worker():
        try:
            # 使用 sys.executable 确保使用相同的 python 环境
            cmd = [sys.executable, "scripts/gen_stock_report.py", ts_code]
            if name: cmd.append(name)
            
            # 运行脚本
            result = subprocess.run(cmd, capture_output=True)
            
            # 自动处理编码 (Windows 默认为 GBK, Python 脚本内部可能输出 UTF-8)
            try:
                output = result.stdout.decode('utf-8')
                error_output = result.stderr.decode('utf-8')
            except UnicodeDecodeError:
                output = result.stdout.decode('gbk', errors='ignore')
                error_output = result.stderr.decode('gbk', errors='ignore')
            
            if result.returncode == 0:
                # 解析输出找到文件名
                if "✅ 报告生成成功:" in output:
                    report_path = output.split("✅ 报告生成成功:")[1].strip()
                    msg = f"报告生成成功！\n路径: {report_path}\n\n是否立即打开查看？"
                    if messagebox.askyesno("成功", msg, parent=parent):
                        # 跨平台打开文件
                        if sys.platform == 'win32':
                            os.startfile(report_path)
                        elif sys.platform == 'darwin':
                            subprocess.run(['open', report_path])
                        else:
                            subprocess.run(['xdg-open', report_path])
                else:
                    messagebox.showinfo("完成", f"脚本运行完成，但未检测到路径信息：\n{output}", parent=parent)
            else:
                messagebox.showerror("失败", f"生成报告失败：\n{error_output}", parent=parent)
        except Exception as e:
            messagebox.showerror("错误", f"发生意外错误：\n{str(e)}", parent=parent)

    # 开启线程执行，避免界面卡死
    threading.Thread(target=worker, daemon=True).start()
    messagebox.showinfo("处理中", f"正在为 {name or ts_code} 生成深度分析报告，请稍候...", parent=parent)
