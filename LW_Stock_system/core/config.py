# 配置管理模块

import os
from pathlib import Path
import json

class Config:
    """应用配置管理 - 统一版本"""
    
    def __init__(self):
        self.config_dir = Path('config')
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / 'app_config.json'
        self.settings_file = self.config_dir / 'app_settings.json'
        self.config = self.load_config()
    
    def load_config(self):
        """加载并合并配置文件"""
        config = {}
        
        # 1. 加载基础配置 (AI 设置等)
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config.update(json.load(f))
            except Exception as e:
                print(f"⚠️ app_config.json 读取失败: {e}")
        
        # 2. 加载用户设置 (投资画像、GUI 设置等)
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    config.update(json.load(f))
            except Exception as e:
                print(f"⚠️ app_settings.json 读取失败: {e}")
                
        return config
    
    def save_config(self):
        """保存配置文件 (按类别拆分保存)"""
        try:
            # 基础配置
            base_keys = ['ai_settings', 'env_configured']
            base_config = {k: self.config[k] for k in base_keys if k in self.config}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(base_config, f, indent=2, ensure_ascii=False)
            
            # 用户设置
            settings_keys = ['user_profile', 'gui_settings']
            settings_config = {k: self.config[k] for k in settings_keys if k in self.config}
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ 配置文件保存失败: {e}")
    
    def get_ai_config(self):
        """获取 AI 模型配置"""
        default_config = {
            'api_key': os.environ.get('AI_API_KEY', ''),
            'base_url': os.environ.get('AI_BASE_URL', 'https://api.openai.com/v1'),
            'model_name': os.environ.get('AI_MODEL_NAME', 'gpt-4o'),
            'provider': 'OpenAI'
        }
        ai_cfg = self.config.get('ai_settings', {})
        for k, v in default_config.items():
            if k not in ai_cfg:
                ai_cfg[k] = v
        return ai_cfg

    def set_ai_config(self, api_key, base_url, model_name):
        """设置 AI 模型配置"""
        if 'ai_settings' not in self.config:
            self.config['ai_settings'] = {}
        
        self.config['ai_settings'].update({
            'api_key': api_key,
            'base_url': base_url,
            'model_name': model_name
        })
        self.save_config()
        os.environ['AI_API_KEY'] = api_key
        os.environ['AI_BASE_URL'] = base_url
        os.environ['AI_MODEL_NAME'] = model_name

    def get_tushare_token(self, prompt_if_missing=True):
        token = os.environ.get('TUSHARE_TOKEN', '').strip()
        if token:
            return token
        if self.config.get('env_configured'):
            return None
        if prompt_if_missing:
            token = input("请输入 TUSHARE_TOKEN: ").strip()
            if token:
                self.config['env_configured'] = True
                self.save_config()
                return token
        return None
    
    def is_env_configured(self):
        return bool(os.environ.get('TUSHARE_TOKEN', '').strip())

# 全局配置实例
config = Config()
