# PowerShell 套件安裝腳本
Write-Host "🐍 正在安裝 Python 套件..." -ForegroundColor Green
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

# 升級 pip
Write-Host "📦 升級 pip..." -ForegroundColor Blue
python -m pip install --upgrade pip

Write-Host ""

# 安裝套件
Write-Host "🔧 安裝 Flask 相關套件..." -ForegroundColor Blue

$packages = @(
    "Flask==2.3.3",
    "Flask-SQLAlchemy==3.0.5", 
    "Werkzeug==2.3.7"
)

foreach ($package in $packages) {
    Write-Host "安裝 $package..." -ForegroundColor Cyan
    pip install $package
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ $package 安裝成功" -ForegroundColor Green
    } else {
        Write-Host "❌ $package 安裝失敗" -ForegroundColor Red
    }
    Write-Host ""
}

# 使用 requirements.txt 安裝
Write-Host "📋 使用 requirements.txt 確認所有套件..." -ForegroundColor Blue
pip install -r requirements.txt

Write-Host ""
Write-Host "🎉 所有套件安裝完成！" -ForegroundColor Green
Write-Host ""
Write-Host "現在您可以執行以下指令啟動應用程序：" -ForegroundColor Yellow
Write-Host "python app.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "或者在瀏覽器中訪問：" -ForegroundColor Yellow
Write-Host "http://localhost:5000" -ForegroundColor Cyan
Write-Host ""

Read-Host "按 Enter 鍵退出"