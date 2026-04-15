# 报告查看标签页（简化版）

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

class ReportsTab:
    """报告查看页面"""
    
    def __init__(self, parent):
        self.parent = parent
        self.reports_dir = Path('output/reports')
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.setup_ui()
        self.refresh_list()
    
    def setup_ui(self):
        """构建界面"""
        # 顶部工具栏
        toolbar = ttk.Frame(self.parent, padding=10)
        toolbar.pack(fill=tk.X)
        
        ttk.Button(toolbar, text="🔄 刷新", command=self.refresh_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="📂 打开文件夹", command=self.open_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="📤 导出 PDF", command=self.export_pdf).pack(side=tk.LEFT, padx=5)
        
        # 分割面板
        paned = ttk.PanedWindow(self.parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧：报告列表
        left_frame = ttk.Frame(paned, width=300)
        paned.add(left_frame, weight=1)
        
        ttk.Label(left_frame, text="📋 历史报告", font=('Microsoft YaHei', 10, 'bold')).pack(pady=5)
        
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ('name', 'date', 'size')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=25)
        self.tree.heading('name', text='文件名')
        self.tree.heading('date', text='日期')
        self.tree.heading('size', text='大小')
        
        self.tree.column('name', width=180)
        self.tree.column('date', width=100)
        self.tree.column('size', width=80)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree.bind('<<TreeviewSelect>>', self.on_report_selected)
        
        # 右侧：预览区
        right_frame = ttk.Frame(paned, width=600)
        paned.add(right_frame, weight=2)
        
        ttk.Label(right_frame, text="👁️ 报告预览", font=('Microsoft YaHei', 10, 'bold')).pack(pady=5)
        
        preview_frame = ttk.Frame(right_frame)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 使用 Text 显示 Markdown（简单显示）
        self.preview_text = tk.Text(preview_frame, wrap=tk.WORD, font=('Microsoft YaHei', 10))
        scrollbar2 = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=scrollbar2.set)
        
        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar2.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.preview_text.insert(tk.END, "请从左侧选择一个报告文件进行预览")
        self.preview_text.config(state=tk.DISABLED)
    
    def refresh_list(self):
        """刷新报告列表"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 获取所有 Markdown 文件
        files = sorted(self.reports_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        for file in files[:50]:  # 最多显示 50 个
            stat = file.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            size = stat.st_size / 1024  # KB
            
            self.tree.insert('', tk.END, values=(
                file.name,
                mtime.strftime('%Y-%m-%d %H:%M'),
                f"{size:.1f} KB"
            ))
    
    def on_report_selected(self, event=None):
        """选择报告事件"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = selection[0]
        filename = self.tree.item(item, 'values')[0]
        filepath = self.reports_dir / filename
        
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                self.preview_text.config(state=tk.NORMAL)
                self.preview_text.delete(1.0, tk.END)
                self.preview_text.insert(tk.END, content)
                self.preview_text.config(state=tk.DISABLED)
            except Exception as e:
                messagebox.showerror("错误", f"无法读取文件: {e}")
    
    def open_folder(self):
        """打开报告文件夹"""
        import subprocess
        try:
            subprocess.Popen(['explorer', str(self.reports_dir.resolve())])
        except:
            messagebox.showinfo("提示", f"文件夹路径: {self.reports_dir}")
    
    def export_pdf(self):
        """导出为 PDF（待实现）"""
        messagebox.showinfo("提示", "导出 PDF 功能待实现")
