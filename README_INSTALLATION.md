# 📦 安裝指南

## 🔧 系統需求

- **Python 3.7+** (建議 Python 3.9 或更新版本)
- **pip** (Python 套件管理器)

## 🚀 快速安裝

### 方法一：使用自動安裝腳本

#### Windows (PowerShell)
```powershell
# 以管理員身份執行 PowerShell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\install_packages.ps1
```

#### Windows (命令提示字元)
```cmd
install_packages.bat
```

### 方法二：手動安裝

#### 1. 檢查 Python 版本
```bash
python --version
# 或
python3 --version
```

#### 2. 升級 pip
```bash
python -m pip install --upgrade pip
```

#### 3. 安裝套件
```bash
# 使用 requirements.txt 一次安裝所有套件
pip install -r requirements.txt

# 或者逐個安裝
pip install Flask==2.3.3
pip install Flask-SQLAlchemy==3.0.5
pip install Werkzeug==2.3.7
```

## 📋 所需套件清單

| 套件名稱 | 版本 | 用途 |
|----------|------|------|
| Flask | 2.3.3 | Web 框架 |
| Flask-SQLAlchemy | 3.0.5 | 資料庫 ORM |
| Werkzeug | 2.3.7 | 密碼雜湊和安全功能 |

## 🏃‍♂️ 啟動應用程序

### 1. 啟動開發服務器
```bash
python app.py
```

### 2. 訪問應用程序
在瀏覽器中打開：
```
http://localhost:5000
```

## 🔐 首次使用

### 測試帳戶
| 角色 | 電子郵件 | 密碼 |
|------|----------|------|
| 廠長 | director@company.com | password123 |
| 協理 | manager1@company.com | password123 |
| 副理 | assistant1@company.com | password123 |
| 課長 | chief1@company.com | password123 |
| 組長 | leader1@company.com | password123 |
| 作業員 | staff1@company.com | password123 |

⚠️ **重要**: 生產環境中請立即更改所有預設密碼！

## 🛠️ 故障排除

### 常見問題

#### 1. "python 不是內部或外部命令"
**解決方案**: 
- 安裝 Python: https://www.python.org/downloads/
- 安裝時勾選 "Add Python to PATH"

#### 2. "pip 不是內部或外部命令"
**解決方案**:
```bash
python -m ensurepip --upgrade
```

#### 3. 套件安裝失敗
**解決方案**:
```bash
# 清除 pip 快取
pip cache purge

# 使用國內鏡像源（中國用戶）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

#### 4. 權限錯誤
**解決方案**:
```bash
# Windows: 以管理員身份執行命令提示字元
# 或使用用戶安裝
pip install --user -r requirements.txt
```

#### 5. 資料庫錯誤
**解決方案**:
- 刪除 `instance/todo_system.db` 檔案
- 重新啟動應用程序讓系統重建資料庫

## 🔄 更新套件

```bash
# 更新所有套件到最新版本
pip install --upgrade -r requirements.txt

# 查看已安裝的套件
pip list

# 查看套件詳細資訊
pip show Flask
```

## 🐳 Docker 部署（可選）

如果您偏好使用 Docker：

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["python", "app.py"]
```

```bash
# 建立和執行
docker build -t todo-system .
docker run -p 5000:5000 todo-system
```

## 📞 技術支援

如果遇到安裝問題，請檢查：
1. Python 版本是否符合需求
2. 網路連線是否正常
3. 防火牆設定是否阻擋
4. 磁碟空間是否足夠

---
*最後更新: 2024年*