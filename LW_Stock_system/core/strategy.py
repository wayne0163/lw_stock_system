# 策略管理模块

import json
from pathlib import Path
from typing import Dict, List, Any

# 获取项目根目录 (假设该文件在 core/ 目录下)
PROJECT_ROOT = Path(__file__).parent.parent

class Strategy:
    """策略类"""
    
    def __init__(self, data: dict):
        self.name = data.get('name', '未命名策略')
        self.description = data.get('description', '')
        self.version = data.get('version', '1.0')
        self.params = data.get('params', {})
        self.file_path = data.get('_file_path')  # 文件路径（内部使用）
    
    def to_dict(self):
        """导出为字典"""
        return {
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'params': self.params
        }
    
    def save(self):
        """保存到文件"""
        if not self.file_path:
            return False
        
        try:
            data = self.to_dict()
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存策略失败: {e}")
            return False
    
    def get_param(self, key_path, default=None):
        """获取嵌套参数，如 'basic_filters.market_cap_min'"""
        keys = key_path.split('.')
        value = self.params
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def set_param(self, key_path, value):
        """设置嵌套参数"""
        keys = key_path.split('.')
        target = self.params
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        target[keys[-1]] = value

class StrategyManager:
    """策略管理器"""
    
    def __init__(self, strategies_dir=None):
        # 如果未指定，使用项目根目录下的 config/strategies
        if strategies_dir is None:
            self.strategies_dir = PROJECT_ROOT / 'config' / 'strategies'
        else:
            self.strategies_dir = Path(strategies_dir)
            
        self.strategies_dir.mkdir(parents=True, exist_ok=True)
        self.strategies: Dict[str, Strategy] = {}
        self.current_strategy = None
        
        self.load_all()
    
    def load_all(self):
        """加载所有策略"""
        self.strategies.clear()
        
        # 确保目录存在
        if not self.strategies_dir.exists():
            print(f"⚠️ 策略目录不存在: {self.strategies_dir}")
            return

        for file_path in self.strategies_dir.glob('*.json'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['_file_path'] = str(file_path)
                    strategy = Strategy(data)
                    self.strategies[strategy.name] = strategy
            except Exception as e:
                print(f"加载策略失败 {file_path}: {e}")
        
        # 设置默认策略（如果存在 default）
        if 'default' in self.strategies:
            self.set_current('default')
        elif self.strategies:
            # 使用第一个
            first = next(iter(self.strategies.values()))
            self.set_current(first.name)
    
    def get_all(self) -> List[Strategy]:
        """获取所有策略"""
        return list(self.strategies.values())
    
    def get(self, name: str) -> Strategy:
        """获取指定策略"""
        return self.strategies.get(name)
    
    def create(self, name: str, description: str, template_name=None):
        """创建新策略"""
        if name in self.strategies:
            raise ValueError(f"策略 '{name}' 已存在")
        
        # 基于模板创建
        params = {}
        if template_name and template_name in self.strategies:
            template = self.strategies[template_name]
            import copy
            params = copy.deepcopy(template.params)
        else:
            # 默认空策略
            params = {
                'basic_filters': {
                    'market_cap_min': 50,
                    'market_cap_max': 300
                },
                'momentum_filters': {
                    'rsi_min': 25,
                    'rsi_max': 55,
                    'ma20_above_ma60': True
                },
                'signal_weights': {
                    'ma20_bounce': 25,
                    'rsi_rebound': 20,
                    'macd_strong': 15,
                    'short_oversold': 20
                },
                'financial_filters': {
                    'roe_dt_min': 10,
                    'roic_min': 8,
                    'tr_yoy_min': 5,
                    'gpm_min': 20,
                    'debt_to_assets_max': 70
                },
                'financial_min_satisfied': 3,
                'require_annual': True
            }
        
        data = {
            'name': name,
            'description': description,
            'version': '1.0',
            'params': params
        }
        
        file_path = self.strategies_dir / f"{name}.json"
        data['_file_path'] = str(file_path)
        
        strategy = Strategy(data)
        if strategy.save():
            self.strategies[name] = strategy
            return strategy
        return None
    
    def delete(self, name: str):
        """删除策略"""
        if name not in self.strategies:
            return False
        
        strategy = self.strategies[name]
        if strategy.file_path and Path(strategy.file_path).exists():
            Path(strategy.file_path).unlink()
        
        del self.strategies[name]
        if self.current_strategy and self.current_strategy.name == name:
            self.current_strategy = None
        
        return True
    
    def set_current(self, name: str):
        """设置当前策略"""
        if name in self.strategies:
            self.current_strategy = self.strategies[name]
            return True
        return False
    
    def get_current(self) -> Strategy:
        """获取当前策略"""
        return self.current_strategy
    
    def copy(self, source_name: str, new_name: str):
        """复制策略"""
        if source_name not in self.strategies:
            raise ValueError(f"源策略 '{source_name}' 不存在")
        if new_name in self.strategies:
            raise ValueError(f"目标策略 '{new_name}' 已存在")
        
        source = self.strategies[source_name]
        import copy
        new_data = copy.deepcopy(source.to_dict())
        new_data['name'] = new_name
        new_data['description'] = f"复制自 {source_name}"
        
        file_path = self.strategies_dir / f"{new_name}.json"
        new_data['_file_path'] = str(file_path)
        
        strategy = Strategy(new_data)
        if strategy.save():
            self.strategies[new_name] = strategy
            return strategy
        return None
    
    def reset_to_default(self, name: str):
        """重置为默认参数（基于 conservative 模板）"""
        if name not in self.strategies:
            return False
        
        conservative = self.strategies.get('conservative')
        if not conservative:
            return False
        
        import copy
        strategy = self.strategies[name]
        strategy.params = copy.deepcopy(conservative.params)
        return strategy.save()

if __name__ == '__main__':
    # 测试
    mgr = StrategyManager()
    
    print(f"策略目录: {mgr.strategies_dir}")
    print("所有策略:")
    for s in mgr.get_all():
        print(f"  - {s.name}: {s.description}")
