# TUSHARE_TOKEN 环境变量设置指南

## 方法一：临时设置（仅当前终端会话）

### Windows PowerShell
```powershell
$env:TUSHARE_TOKEN="your_token_here"
```

### Windows CMD
```cmd
set TUSHARE_TOKEN=your_token_here
```

### Linux/macOS
```bash
export TUSHARE_TOKEN=your_token_here
```

---

## 方法二：永久设置（推荐）

### Windows（PowerShell，管理员运行）

```powershell
[System.Environment]::SetEnvironmentVariable('TUSHARE_TOKEN', 'your_token_here', 'User')
```

**验证**：
```powershell
[System.Environment]::GetEnvironmentVariable('TUSHARE_TOKEN', 'User')
```

**重启终端**后即可生效。

---

### Windows（CMD）

```cmd
setx TUSHARE_TOKEN your_token_here
```

---

### Linux/macOS（bash/zsh）

添加到 `~/.bashrc` 或 `~/.zshrc`：
```bash
echo "export TUSHARE_TOKEN=your_token_here" >> ~/.bashrc
source ~/.bashrc
```

---

## 验证设置

```bash
# Windows PowerShell
echo $env:TUSHARE_TOKEN

# Windows CMD
echo %TUSHARE_TOKEN%

# Linux/macOS
echo $TUSHARE_TOKEN
```

---

## 程序运行逻辑

1. **环境变量存在** → 自动使用，无需输入
2. **环境变量不存在** → 提示输入 token（可临时使用）
3. **输入后选择保存** → 程序会提示设置环境变量方法

---

## 更换电脑时

在新电脑上：
1. 重新设置环境变量（方法二）
2. 运行程序会自动读取

---

**你的 token**: ``

请按上述方法设置环境变量，设置后重启终端，运行：
```bash
python scripts/download_financial_data.py --help
```

确认能自动读取 token 后，我继续开发 GUI 其他模块。 🚀
