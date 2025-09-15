# 創建和啟動虛擬環境的 PowerShell 腳本
Write-Host "🐍 設置 Python 虛擬環境..." -ForegroundColor Green
Write-Host ""

# 檢查 Python 是否安裝
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python 版本: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ 錯誤: 找不到 Python" -ForegroundColor Red
    Write-Host "請先安裝 Python: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "按 Enter 鍵退出"
    exit 1
}

Write-Host ""

# 創建虛擬環境
Write-Host "📁 創建虛擬環境 'venv'..." -ForegroundColor Blue
if (Test-Path "venv") {
    Write-Host "⚠️ 虛擬環境已存在，跳過創建" -ForegroundColor Yellow
} else {
    python -m venv venv
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ 虛擬環境創建成功" -ForegroundColor Green
    } else {
        Write-Host "❌ 虛擬環境創建失敗" -ForegroundColor Red
        Read-Host "按 Enter 鍵退出"
        exit 1
    }
}
Write-Host ""

# 啟動虛擬環境
Write-Host "🔄 啟動虛擬環境..." -ForegroundColor Blue
& ".\venv\Scripts\Activate.ps1"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 虛擬環境已啟動" -ForegroundColor Green
} else {
    Write-Host "❌ 虛擬環境啟動失敗" -ForegroundColor Red
    Write-Host "嘗試手動啟動: .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
}

Write-Host ""

# 升級 pip
Write-Host "📦 升級 pip..." -ForegroundColor Blue
python -m pip install --upgrade pip

Write-Host ""

# 安裝套件
Write-Host "🔧 安裝所需套件..." -ForegroundColor Blue
pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 套件安裝完成" -ForegroundColor Green
} else {
    Write-Host "❌ 套件安裝失敗" -ForegroundColor Red
    Read-Host "按 Enter 鍵退出"
    exit 1
}

Write-Host ""
Write-Host "🚀 啟動應用程序..." -ForegroundColor Green
Write-Host "應用程序將在 http://localhost:5001 運行" -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止服務器" -ForegroundColor Yellow
Write-Host ""

# 啟動應用程序
python app.py
