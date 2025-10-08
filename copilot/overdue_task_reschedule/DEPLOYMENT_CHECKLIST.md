# 🚀 部署檢查清單 - 逾期任務重設預計完成日期功能

## 📋 部署前準備

### 1. 代碼驗證
- [x] Python 語法檢查通過（app.py, scheduler.py）
- [x] JavaScript 無語法錯誤（main.js）
- [x] CSS 格式正確（styles.css）
- [x] 單元測試通過（test_new_feature.py）

### 2. 變更確認
已修改的檔案：
- [x] `app.py` - 後端 API（約 60 行新增）
- [x] `scheduler.py` - 郵件通知（4 行新增）
- [x] `static/js/main.js` - 前端邏輯（約 30 行新增/修改）
- [x] `static/css/styles.css` - 樣式（約 30 行新增）

新增的文檔：
- [x] `UPGRADE_PLAN.md` - 升級計畫
- [x] `IMPLEMENTATION_SUMMARY.md` - 實施總結
- [x] `CHANGES_SUMMARY.md` - 變更摘要
- [x] `DEPLOYMENT_CHECKLIST.md` - 本檔案
- [x] `test_new_feature.py` - 測試腳本

### 3. 資料庫檢查
- [x] 不需要資料庫遷移
- [x] 不需要修改現有欄位
- [x] 完全向後兼容

## 🔄 部署步驟

### 步驟 1: 備份 ⚠️ **重要**
```powershell
# 1. 備份資料庫
$date = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item "C:\app\Todothis_v4\instance\todo_system.db" `
          "C:\app\Todothis_v4\backups\todo_system_${date}.db"

# 2. 備份關鍵檔案
Copy-Item "C:\app\Todothis_v4\app.py" `
          "C:\app\Todothis_v4\backups\app_${date}.py"
Copy-Item "C:\app\Todothis_v4\static\js\main.js" `
          "C:\app\Todothis_v4\backups\main_${date}.js"
Copy-Item "C:\app\Todothis_v4\scheduler.py" `
          "C:\app\Todothis_v4\backups\scheduler_${date}.py"
Copy-Item "C:\app\Todothis_v4\static\css\styles.css" `
          "C:\app\Todothis_v4\backups\styles_${date}.css"
```

**檢查點**:
- [ ] 資料庫備份完成（檢查檔案大小 > 0）
- [ ] 關鍵檔案備份完成

### 步驟 2: 停止服務
```powershell
# 找到運行中的 Python 進程
Get-Process python | Where-Object {$_.Path -like "*Todothis_v4*"}

# 停止服務（根據實際情況選擇）
# 方法 1: 如果使用 run_waitress.ps1
Stop-Process -Name "python" -Force

# 方法 2: 或手動結束相關進程
```

**檢查點**:
- [ ] 確認服務已停止
- [ ] 確認沒有 Python 進程佔用 5001 端口

### 步驟 3: 部署新版本
檔案已經修改完成，不需要額外操作。

**檢查點**:
- [ ] 確認所有修改的檔案都已儲存

### 步驟 4: 重啟服務
```powershell
cd C:\app\Todothis_v4

# 方法 1: 使用 waitress
.\run_waitress.ps1

# 方法 2: 或直接運行
python app.py
```

**檢查點**:
- [ ] 服務成功啟動
- [ ] 沒有錯誤訊息
- [ ] 可以訪問 http://192.168.6.119:5001

### 步驟 5: 清除快取
**瀏覽器操作**:
1. 開啟瀏覽器開發者工具（F12）
2. 右鍵點擊重新整理按鈕
3. 選擇「清除快取並強制重新整理」
4. 或使用 Ctrl + Shift + Delete 清除快取

**檢查點**:
- [ ] 新的 CSS 樣式已載入
- [ ] 新的 JavaScript 功能已載入
- [ ] 無控制台錯誤

## ✅ 功能測試

### 測試 1: 基本功能
**步驟**:
1. 建立一個新的 Todo 任務
2. 將 due_date 設為昨天（建立逾期任務）
3. 選擇「未完成」狀態
4. 觀察界面變化

**預期結果**:
- [ ] 顯示未完成原因輸入框
- [ ] 顯示新的預計完成日期選擇器
- [ ] 兩個輸入框都有清楚的標籤
- [ ] 有「確認」按鈕

### 測試 2: 驗證邏輯
**步驟**:
1. 只填寫原因，不選日期，點擊「確認」
2. 只選日期，不填原因，點擊「確認」

**預期結果**:
- [ ] 第一種情況：提示「請選擇新的預計完成日期」
- [ ] 第二種情況：提示「請輸入未完成原因」

### 測試 3: 完整流程
**步驟**:
1. 填寫未完成原因：「測試重設日期功能」
2. 選擇新日期：明天下午 5:00
3. 點擊「確認」

**預期結果**:
- [ ] 顯示成功訊息
- [ ] 任務狀態變為「進行中」
- [ ] 預計完成日期已更新為新日期
- [ ] 履歷顯示兩筆記錄：
  - 「預計完成日期從 ... 變更為 ...」
  - 「狀態從 ... 變更為 未完成 (原因: ...)」
- [ ] 逾期紅色標記消失（因為日期已更新為未來）

### 測試 4: MeetingTask 同步
**步驟**:
1. 建立一個會議任務（MeetingTask）
2. 指派到 Todo
3. 將 Todo 設為逾期
4. 執行未完成並重設日期操作
5. 檢查 MeetingTask

**預期結果**:
- [ ] MeetingTask 的 expected_completion_date 已更新
- [ ] MeetingTask 的 uncompleted_reason_from_todo 已記錄
- [ ] MeetingTask 的 history_log 包含變更記錄
- [ ] MeetingTask 的 status 為 'uncompleted_todo'

### 測試 5: 郵件通知
**步驟**:
1. 等待每日排程任務執行（或手動觸發）
2. 檢查逾期任務提醒郵件

**預期結果**:
- [ ] 郵件包含逾期任務列表
- [ ] 郵件包含「💡 小提示」段落
- [ ] 提示文字說明如何重設日期
- [ ] 郵件格式正確、易讀

### 測試 6: 瀏覽器兼容性
測試瀏覽器：
- [ ] Chrome/Edge（datetime-local 完整支援）
- [ ] Firefox（datetime-local 完整支援）
- [ ] Safari（如果有使用）

## 🔍 監控檢查

### 日誌監控
```powershell
# 查看最新日誌
Get-Content "C:\app\Todothis_v4\logs\*.log" -Tail 50 -Wait

# 搜尋日期變更相關日誌
Select-String -Path "C:\app\Todothis_v4\logs\*.log" -Pattern "due_date_changed|Updated due date"
```

**檢查點**:
- [ ] 沒有錯誤訊息
- [ ] 'due_date_changed' 事件有記錄
- [ ] 'Updated due date' 日誌正常

### 資料庫檢查（選擇性）
```python
# 可以使用 Python 快速檢查
import sqlite3
conn = sqlite3.connect('C:/app/Todothis_v4/instance/todo_system.db')
cursor = conn.cursor()

# 檢查最近的履歷記錄
cursor.execute("""
    SELECT id, title, history_log 
    FROM todo 
    WHERE history_log LIKE '%due_date_changed%'
    ORDER BY updated_at DESC 
    LIMIT 5
""")
print(cursor.fetchall())
conn.close()
```

**檢查點**:
- [ ] history_log 包含 'due_date_changed' 事件
- [ ] JSON 格式正確
- [ ] 時間戳記正確

## 🔙 回滾計畫（如果需要）

### 快速回滾步驟
```powershell
$date = "YYYYMMDD_HHmmss"  # 替換為備份時的時間戳

# 1. 停止服務
Stop-Process -Name "python" -Force

# 2. 還原檔案
Copy-Item "C:\app\Todothis_v4\backups\app_${date}.py" `
          "C:\app\Todothis_v4\app.py" -Force
Copy-Item "C:\app\Todothis_v4\backups\main_${date}.js" `
          "C:\app\Todothis_v4\static\js\main.js" -Force
Copy-Item "C:\app\Todothis_v4\backups\scheduler_${date}.py" `
          "C:\app\Todothis_v4\scheduler.py" -Force
Copy-Item "C:\app\Todothis_v4\backups\styles_${date}.css" `
          "C:\app\Todothis_v4\static\css\styles.css" -Force

# 3. 還原資料庫（如果需要）
Copy-Item "C:\app\Todothis_v4\backups\todo_system_${date}.db" `
          "C:\app\Todothis_v4\instance\todo_system.db" -Force

# 4. 重啟服務
.\run_waitress.ps1
```

## 📊 部署後確認

### 立即檢查（部署後 1 小時內）
- [ ] 服務運行正常
- [ ] 無系統錯誤
- [ ] 基本功能測試通過
- [ ] 日誌無異常

### 短期監控（部署後 24 小時內）
- [ ] 使用者回報無問題
- [ ] 郵件提醒正常發送
- [ ] 新功能使用正常
- [ ] 效能無異常

### 長期追蹤（部署後 1 週內）
- [ ] 收集使用者反饋
- [ ] 統計功能使用率
- [ ] 檢視任務日期變更記錄
- [ ] 評估是否需要優化

## 📢 使用者通知

### 通知方式
- [ ] Email 通知（使用逾期提醒郵件自動說明）
- [ ] 系統公告（如果有公告功能）
- [ ] 內部文件更新

### 通知內容範本
```
【系統更新通知】逾期任務管理功能增強

親愛的使用者，

系統新增了一個實用功能：當您的任務逾期無法完成時，現在可以在標記為「未完成」的同時，重新設定新的預計完成日期。

使用方式：
1. 在逾期任務中選擇「未完成」狀態
2. 填寫未完成原因（例如：等待供應商回覆）
3. 選擇新的預計完成日期
4. 點擊「確認」

所有變更都會記錄在任務履歷中，方便您追蹤任務進度。

如有任何問題，請聯繫系統管理員。

謝謝！
```

## ✅ 最終確認

部署完成後，請確認以下所有項目：

### 技術檢查
- [ ] 服務正常運行
- [ ] 無錯誤日誌
- [ ] 資料庫正常
- [ ] 備份已完成

### 功能檢查
- [ ] 基本功能測試通過
- [ ] 驗證邏輯正確
- [ ] 履歷記錄正常
- [ ] MeetingTask 同步正常
- [ ] 郵件提醒正確

### 文檔檢查
- [ ] 部署記錄已更新
- [ ] 使用者通知已發送
- [ ] 變更日誌已記錄

## 🎉 部署完成！

如果所有檢查都通過，恭喜！新功能已成功部署！

**下一步**:
1. 持續監控系統運行狀態
2. 收集使用者反饋
3. 記錄任何問題或改進建議
4. 更新系統文檔

**需要協助？**
- 查看 `IMPLEMENTATION_SUMMARY.md` 了解技術細節
- 查看 `UPGRADE_PLAN.md` 了解設計思路
- 查看日誌檔案排查問題
