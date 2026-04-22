# 标签页基类

import tkinter as tk
from tkinter import ttk

class BaseTab(ttk.Frame):
    """所有标签页的基类"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        
    def setup_ui(self):
        """子类实现此方法"""
        raise NotImplementedError
    
    def on_show(self):
        """标签页显示时调用"""
        pass
    
    def on_hide(self):
        """标签页隐藏时调用"""
        pass
