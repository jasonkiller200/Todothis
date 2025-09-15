# 使用 Waitress 啟動應用程序的 PowerShell 腳本
Write-Host "🚀 啟動待辦事項協作系統 (使用 Waitress)..." -ForegroundColor Green
Write-Host ""

try {
    # 檢查 Python 是否安裝
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python 版本: $pythonVersion" -ForegroundColor Green

    Write-Host ""

    # 檢查虛擬環境是否存在
    if (Test-Path "venv\Scripts\Activate.ps1") {
        Write-Host "🔄 啟動虛擬環境..." -ForegroundColor Blue
        & ".\venv\Scripts\Activate.ps1"
        
        Write-Host "📦 檢查套件 (Waitress)..." -ForegroundColor Blue
        pip list | Select-String "waitress"
        
        Write-Host ""
        Write-Host "🌐 啟動 Web 服務器 (Waitress)..." -ForegroundColor Green
        Write-Host "應用程序將在以下地址運行：" -ForegroundColor Cyan
        Write-Host "  http://localhost:5001" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "按 Ctrl+C 停止服務器" -ForegroundColor Yellow
        Write-Host "=" * 50 -ForegroundColor Gray
        Write-Host ""
        
        # 使用 Waitress 啟動應用程序，並增加工作執行緒數量以提升效能
        & ".\venv\Scripts\waitress-serve.exe" --host=0.0.0.0 --port=5001 --threads=8 app:app
        
    } else {
        Write-Host "❌ 虛擬環境不存在" -ForegroundColor Red
        Write-Host "請先執行 setup_and_run.ps1 來設置環境並安裝套件" -ForegroundColor Yellow
    }

} catch {
    Write-Host "❌ 腳本執行時發生嚴重錯誤:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "請檢查您的 Python 環境或腳本權限。" -ForegroundColor Yellow
}

Write-Host ""
Read-Host "腳本執行完畢或已出錯，按 Enter 鍵退出..."
