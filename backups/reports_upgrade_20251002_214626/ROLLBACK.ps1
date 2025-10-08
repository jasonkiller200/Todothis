# 報告中心優化 - 一鍵回滾腳本
# 建立時間: 2025-10-02 21:46:26

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   報告中心優化 - 回滾腳本" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# 設定備份目錄
$backupDir = $PSScriptRoot
$projectDir = "C:\app\Todothis_v4"

Write-Host "備份目錄: $backupDir" -ForegroundColor Yellow
Write-Host "專案目錄: $projectDir" -ForegroundColor Yellow
Write-Host ""

# 確認操作
$confirmation = Read-Host "確定要回滾到此備份版本嗎？ (yes/no)"
if ($confirmation -ne "yes") {
    Write-Host "❌ 已取消回滾操作" -ForegroundColor Red
    exit
}

Write-Host ""
Write-Host "開始回滾..." -ForegroundColor Green
Write-Host ""

# 回滾檔案
$files = @(
    @{Source="app.py"; Dest="$projectDir\app.py"},
    @{Source="reports.html"; Dest="$projectDir\templates\reports.html"},
    @{Source="styles.css"; Dest="$projectDir\static\css\styles.css"}
)

$successCount = 0
$failCount = 0

foreach ($file in $files) {
    $sourcePath = Join-Path $backupDir $file.Source
    $destPath = $file.Dest
    
    if (Test-Path $sourcePath) {
        try {
            Copy-Item -Path $sourcePath -Destination $destPath -Force
            Write-Host "✅ 已回滾: $($file.Source)" -ForegroundColor Green
            $successCount++
        } catch {
            Write-Host "❌ 回滾失敗: $($file.Source) - $_" -ForegroundColor Red
            $failCount++
        }
    } else {
        Write-Host "⚠️  備份檔案不存在: $($file.Source)" -ForegroundColor Yellow
        $failCount++
    }
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "回滾完成！" -ForegroundColor Cyan
Write-Host "成功: $successCount 個檔案" -ForegroundColor Green
Write-Host "失敗: $failCount 個檔案" -ForegroundColor Red
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

if ($failCount -eq 0) {
    Write-Host "✅ 所有檔案已成功回滾到備份版本！" -ForegroundColor Green
    Write-Host ""
    Write-Host "建議執行以下步驟：" -ForegroundColor Yellow
    Write-Host "1. 重啟應用程式服務" -ForegroundColor White
    Write-Host "2. 清除瀏覽器快取" -ForegroundColor White
    Write-Host "3. 驗證功能是否正常" -ForegroundColor White
} else {
    Write-Host "⚠️  部分檔案回滾失敗，請檢查錯誤訊息" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "按任意鍵退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
