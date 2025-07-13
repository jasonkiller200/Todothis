# 🚀 快速啟動指南

## ⚠️ 重要提醒
目前系統中沒有檢測到 Python，請先完成 Python 安裝。

## 📋 完整啟動步驟

### 第一步：安裝 Python
1. **下載 Python**
   - 訪問：https://www.python.org/downloads/
   - 下載最新版本 (建議 Python 3.9+)

2. **安裝 Python**
   - 執行下載的安裝程序
   - ⚠️ **重要**：勾選 "Add Python to PATH"
   - 選擇 "Install Now"

3. **驗證安裝**
   - 重新打開 PowerShell
   - 執行：`python --version`

### 第二步：設置虛擬環境並啟動應用

Python 安裝完成後，選擇以下任一方式：

#### 方式一：使用 PowerShell 腳本（推薦）
```powershell
# 設置執行策略（如果需要）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 執行自動設置腳本
.\setup_and_run.ps1
```

#### 方式二：使用批次檔
```cmd
setup_and_run.bat
```

#### 方式三：手動執行
```powershell
# 1. 創建虛擬環境
python -m venv venv

# 2. 啟動虛擬環境
.\venv\Scripts\Activate.ps1

# 3. 升級 pip
python -m pip install --upgrade pip

# 4. 安裝套件
pip install -r requirements.txt

# 5. 啟動應用程序
python app.py
```

## 🌐 訪問應用程序

啟動成功後，在瀏覽器中訪問：
```
http://localhost:5000
```

## 🔐 測試帳戶

| 角色 | 電子郵件 | 密碼 |
|------|----------|------|
| 廠長 | director@company.com | password123 |
| 協理 | manager1@company.com | password123 |
| 作業員 | staff1@company.com | password123 |

## 🛠️ 故障排除

### 問題 1：PowerShell 執行策略錯誤
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 問題 2：虛擬環境啟動失敗
```powershell
# 嘗試使用 cmd 方式
venv\Scripts\activate.bat
```

### 問題 3：套件安裝失敗
```powershell
# 使用國內鏡像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

## 📁 專案檔案結構

```
📦 todo-system/
├── 📄 app.py                    # 主應用程序
├── 📄 requirements.txt          # 套件依賴
├── 📄 setup_and_run.ps1        # PowerShell 啟動腳本
├── 📄 setup_and_run.bat        # 批次檔啟動腳本
├── 📄 SECURITY_FEATURES.md     # 安全功能說明
├── 📄 README_INSTALLATION.md   # 詳細安裝指南
├── 📄 QUICK_START.md           # 本檔案
├── 📁 templates/               # HTML 模板
│   ├── 📄 index.html
│   ├── 📄 login.html
│   ├── 📄 change_password.html
│   └── 📄 admin_users.html
├── 📁 instance/               # 資料庫檔案
│   └── 📄 todo_system.db
└── 📁 venv/                   # 虛擬環境（執行後生成）
```

## 🎯 下一步

1. **安裝 Python** - 從官網下載並安裝
2. **執行啟動腳本** - 使用 `setup_and_run.ps1` 或 `setup_and_run.bat`
3. **訪問應用程序** - 打開瀏覽器訪問 http://localhost:5000
4. **使用測試帳戶登入** - 體驗系統功能

---

**需要幫助？**
- 檢查 Python 是否正確安裝：`python --version`
- 檢查 pip 是否可用：`pip --version`
- 確保網路連線正常以下載套件