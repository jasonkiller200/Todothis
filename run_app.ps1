# 簡化的應用程序啟動腳本
# 假設 Python 和虛擬環境已經設置好

Write-Host "🚀 啟動待辦事項協作系統..." -ForegroundColor Green
Write-Host ""

# 檢查虛擬環境是否存在
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "🔄 啟動虛擬環境..." -ForegroundColor Blue
    & ".\venv\Scripts\Activate.ps1"
    
    Write-Host "📦 檢查套件..." -ForegroundColor Blue
    pip list | Select-String "Flask"
    
    Write-Host ""
    Write-Host "🌐 啟動 Web 服務器..." -ForegroundColor Green
    Write-Host "應用程序將在以下地址運行：" -ForegroundColor Cyan
    Write-Host "  http://localhost:5001" -ForegroundColor Yellow
    Write-Host "  http://192.168.6.119:5001"
    Write-Host "按 Ctrl+C 停止服務器" -ForegroundColor Yellow
    Write-Host "=" * 50 -ForegroundColor Gray
    Write-Host ""
    
    # 啟動應用程序
    & ".\venv\Scripts\python.exe" app.py
    
} else {
    Write-Host "❌ 虛擬環境不存在" -ForegroundColor Red
    Write-Host "請先執行 setup_and_run.ps1 來設置環境" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "按 Enter 鍵退出"
}
