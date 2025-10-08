# 逾期任務重設預計完成日期功能 - 實施總結

## 📅 實施日期
2025年（實際日期）

## ✅ 完成的修改

### 1. 後端 API 修改 (app.py)
**位置**: `update_todo_status()` 函數 (約 line 1618-1715)

**修改內容**:
- ✅ 新增接收 `new_due_date` 參數
- ✅ 在未完成狀態處理中，解析並更新 `todo.due_date`
- ✅ 記錄日期變更事件到 `history_log`，包含：
  - `event_type`: 'due_date_changed'
  - `old_due_date` 和 `new_due_date`（台北時區格式）
  - `reason`: 未完成原因
- ✅ 同步更新關聯的 `MeetingTask.expected_completion_date`
- ✅ 將日期變更事件同步到 `MeetingTask.history_log`
- ✅ 添加錯誤處理和日誌記錄

**關鍵改動**:
```python
# 接收新參數
new_due_date = data.get('new_due_date', None)

# 處理日期更新
if new_due_date:
    new_due_date_parsed = isoparse(new_due_date)
    old_due_date = todo.due_date
    todo.due_date = new_due_date_parsed
    
    # 記錄到履歷
    due_date_change_entry = {
        'event_type': 'due_date_changed',
        'timestamp': datetime.now(utc).isoformat(),
        'actor': {...},
        'details': {
            'old_due_date': old_due_date.astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M'),
            'new_due_date': new_due_date_parsed.astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M'),
            'reason': uncompleted_reason
        }
    }
```

### 2. 前端界面修改 (static/js/main.js)

#### 2.1 HTML 生成部分 (約 line 145-157)
**修改內容**:
- ✅ 在未完成原因容器中添加日期選擇器
- ✅ 添加標籤文字說明
- ✅ 使用 `datetime-local` 輸入類型

**新增 HTML**:
```html
<label for="uncompleted-reason-${todo.id}">未完成原因：</label>
<textarea id="uncompleted-reason-${todo.id}" ...></textarea>
<label for="new-due-date-${todo.id}">新的預計完成日期：</label>
<input type="datetime-local" id="new-due-date-${todo.id}" class="new-due-date-input" />
<button type="button" class="btn confirm-uncompleted-btn" ...>確認</button>
```

#### 2.2 履歷顯示部分 (約 line 173-196)
**修改內容**:
- ✅ 新增 `due_date_changed` 事件類型的顯示邏輯
- ✅ 顯示舊日期 → 新日期的變更
- ✅ 顯示變更原因

**新增代碼**:
```javascript
} else if (entry.event_type === 'due_date_changed') {
    const actorDisplayName = `由 ${getActorName(entry.actor)}`;
    eventText = `${actorDisplayName} 預計完成日期從 ${escapeHTML(entry.details.old_due_date)} 變更為 ${escapeHTML(entry.details.new_due_date)}`;
    if (entry.details.reason) {
        eventText += ` (原因: ${escapeHTML(entry.details.reason)})`;
    }
}
```

#### 2.3 事件處理器 (約 line 383-406)
**修改內容**:
- ✅ 獲取新的預計完成日期輸入值
- ✅ 驗證日期必填
- ✅ 傳遞日期參數到 API

**新增驗證**:
```javascript
const newDueDateInput = document.getElementById(`new-due-date-${todoId}`);
const newDueDate = newDueDateInput.value;

if (!newDueDate) {
    alert('請選擇新的預計完成日期');
    return;
}

updateTodoStatus(todoId, 'uncompleted', reason, newDueDate);
```

#### 2.4 API 調用函數 (約 line 409-430)
**修改內容**:
- ✅ 添加 `newDueDate` 參數
- ✅ 轉換為 ISO 格式傳送到後端

**修改簽名**:
```javascript
function updateTodoStatus(todoId, status, reason = null, newDueDate = null) {
    const body = { status: status };
    if (reason) {
        body.uncompleted_reason = reason;
    }
    if (newDueDate) {
        body.new_due_date = new Date(newDueDate).toISOString();
    }
    // ... fetch 邏輯
}
```

### 3. 郵件通知修改 (scheduler.py)
**位置**: `check_overdue_tasks()` 函數 (約 line 90-107)

**修改內容**:
- ✅ 在逾期任務列表後添加提示訊息
- ✅ 使用 HTML 粗體標記 `<b>💡 小提示：</b>`
- ✅ 說明如何使用重設日期功能

**新增內容**:
```python
body_parts.append("<b>💡 小提示：</b>")
body_parts.append("如任務無法在原定期限完成，您可以在系統中將任務狀態設為「未完成」，")
body_parts.append("填寫未完成原因後，同時重新設定新的預計完成日期。")
body_parts.append("")
```

### 4. CSS 樣式修改 (static/css/styles.css)
**位置**: 約 line 286-300

**修改內容**:
- ✅ 新增 `.new-due-date-input` 樣式類
- ✅ 添加 focus 狀態樣式（藍色邊框和陰影）
- ✅ 新增標籤樣式 `.uncompleted-reason-label`
- ✅ 確保輸入框寬度和間距一致

**新增樣式**:
```css
.new-due-date-input {
    width: 100%;
    padding: 8px;
    margin-top: 5px;
    border: 1px solid #ccc;
    border-radius: 5px;
    font-size: 0.9em;
    box-sizing: border-box;
    font-family: inherit;
}

.new-due-date-input:focus {
    outline: none;
    border-color: #3498db;
    box-shadow: 0 0 5px rgba(52, 152, 219, 0.3);
}
```

## 🔧 技術細節

### 資料流程
1. 使用者選擇「未完成」狀態
2. 前端顯示未完成原因輸入框 + 日期選擇器
3. 使用者填寫原因並選擇新日期
4. 前端驗證兩個欄位都已填寫
5. 發送 PUT 請求到 `/api/todo/<id>/status`，包含：
   - `status`: 'uncompleted'
   - `uncompleted_reason`: 原因文字
   - `new_due_date`: ISO 格式日期字串
6. 後端更新 Todo：
   - 記錄日期變更到 history_log
   - 記錄未完成事件到 history_log
   - 更新 due_date
   - 狀態自動切換為 'in-progress'
7. 如果有關聯的 MeetingTask：
   - 同步更新 expected_completion_date
   - 同步更新 uncompleted_reason_from_todo
   - 同步履歷事件
8. 前端重新載入任務列表，顯示更新後的資料

### 履歷記錄格式
```json
{
  "event_type": "due_date_changed",
  "timestamp": "2025-01-15T10:30:00Z",
  "actor": {
    "id": 123,
    "name": "張三",
    "user_key": "zhangsan"
  },
  "details": {
    "old_due_date": "2025-01-10 17:00",
    "new_due_date": "2025-01-20 17:00",
    "reason": "等待供應商回覆"
  }
}
```

### 時區處理
- 後端接收 ISO 格式 UTC 時間
- 資料庫儲存 UTC 時間
- 履歷記錄顯示台北時區 (Asia/Taipei)
- 郵件通知使用台北時區

## 🎯 功能特點

### ✅ 向後兼容
- 新參數 `new_due_date` 為可選
- 沒有修改資料庫結構
- 不影響現有的未完成流程
- 如果不提供日期，仍可正常運作

### ✅ 完整同步
- Todo 和 MeetingTask 的日期同步更新
- 履歷記錄完整同步
- 狀態變更同步

### ✅ 使用者體驗
- 清楚的標籤說明
- 必填欄位驗證
- 友善的錯誤提示
- 日期選擇器使用原生 HTML5 控件
- 郵件提醒引導使用

### ✅ 錯誤處理
- 日期格式驗證
- 必填欄位檢查
- 後端錯誤日誌記錄
- 前端錯誤提示

## 📊 測試建議

### 基本功能測試
1. **建立逾期任務**
   - 建立一個 Todo，due_date 設為過去時間
   - 確認任務顯示為逾期（紅色標記）

2. **執行未完成並重設日期**
   - 選擇「未完成」狀態
   - 填寫未完成原因（例如：「等待供應商回覆」）
   - 選擇新的預計完成日期（未來日期）
   - 點擊「確認」按鈕
   - 驗證：
     - ✅ 任務狀態變為「進行中」
     - ✅ due_date 已更新
     - ✅ 履歷顯示兩筆記錄（日期變更 + 狀態變更）
     - ✅ 成功提示訊息

3. **驗證必填欄位**
   - 只填寫原因，不選日期 → 應提示「請選擇新的預計完成日期」
   - 只選日期，不填原因 → 應提示「請輸入未完成原因」

### MeetingTask 同步測試
1. **建立關聯任務**
   - 建立一個會議任務（MeetingTask）
   - 指派到 Todo
   - 設定為逾期

2. **執行未完成並重設日期**
   - 在 Todo 中執行未完成操作
   - 填寫原因和新日期
   - 驗證 MeetingTask：
     - ✅ expected_completion_date 已同步更新
     - ✅ uncompleted_reason_from_todo 已記錄
     - ✅ history_log 包含日期變更和狀態變更事件
     - ✅ status 為 'uncompleted_todo'

### 履歷顯示測試
1. 執行未完成並重設日期後
2. 查看任務履歷
3. 驗證顯示：
   - ✅ 「由 [使用者名稱] 預計完成日期從 [舊日期] 變更為 [新日期] (原因: [原因文字])」
   - ✅ 「由 [使用者名稱] 狀態從 進行中 變更為 未完成 (原因: [原因文字])」
   - ✅ 時間戳記正確（台北時區）

### 郵件通知測試
1. **觸發逾期檢查**
   - 等待排程任務執行，或手動觸發 `check_overdue_tasks()`
   
2. **檢查郵件內容**
   - ✅ 收到逾期任務提醒郵件
   - ✅ 包含提示訊息：「💡 小提示」
   - ✅ 說明如何重設日期
   - ✅ 格式正確，易於閱讀

### 邊界條件測試
1. **選擇過去的日期** - 系統應接受（讓使用者自行判斷）
2. **選擇很久以後的日期** - 系統應接受
3. **多次重設日期** - 每次都應記錄到履歷
4. **無關聯 MeetingTask 的 Todo** - 應正常運作，不影響功能

## 🚀 部署步驟

### 1. 備份
```bash
# 備份資料庫
cp C:\app\Todothis_v4\instance\todo_system.db C:\app\Todothis_v4\backups\todo_system_backup_YYYYMMDD.db

# 備份重要檔案
cp C:\app\Todothis_v4\app.py C:\app\Todothis_v4\backups\app_backup_YYYYMMDD.py
cp C:\app\Todothis_v4\static\js\main.js C:\app\Todothis_v4\backups\main_backup_YYYYMMDD.js
```

### 2. 重啟服務
```powershell
# 停止現有服務（如果使用 waitress）
# 找到運行中的 Python 進程並停止

# 重新啟動
.\run_waitress.ps1
# 或
python app.py
```

### 3. 驗證
- 訪問系統首頁，確認正常載入
- 檢查瀏覽器控制台，確認無 JavaScript 錯誤
- 執行基本測試案例

### 4. 監控
- 檢查日誌檔案 (`logs/`)
- 監控錯誤訊息
- 收集使用者反饋

## 📝 使用說明（給使用者）

### 如何重設逾期任務的預計完成日期

1. **查看逾期任務**
   - 登入系統後，逾期任務會以紅色標記顯示
   - 您也會收到逾期任務提醒郵件

2. **標記為未完成並重設日期**
   - 在任務卡片中，找到「狀態」下拉選單
   - 選擇「未完成」
   - 系統會顯示兩個輸入欄位：
     - **未完成原因**：請說明為何無法如期完成（例如：等待供應商回覆、技術問題待解決等）
     - **新的預計完成日期**：選擇新的目標完成時間
   - 點擊「確認」按鈕

3. **查看變更記錄**
   - 任務會自動切換回「進行中」狀態
   - 在任務履歷中可以看到：
     - 預計完成日期的變更記錄
     - 未完成的原因
     - 操作時間和操作人員

4. **追蹤任務**
   - 新的預計完成日期會成為任務的新目標
   - 如果再次逾期，您可以重複此流程

## ⚠️ 注意事項

### 系統管理員
1. **資料庫**：不需要執行資料庫遷移
2. **快取**：可能需要清除瀏覽器快取以載入新的 CSS/JS
3. **日誌**：監控日誌中的 'due_date_changed' 事件
4. **效能**：此功能對效能影響極小

### 開發者
1. **時區**：確保所有時間處理使用正確的時區
2. **驗證**：前後端都有驗證，但可考慮添加更多業務邏輯驗證
3. **擴展**：如需添加日期變更限制（例如：不能選過去的日期），可在前端或後端添加驗證邏輯

## 🎉 總結

此次升級成功實現了以下目標：
- ✅ 使用者可以在標記任務為未完成時重設預計完成日期
- ✅ 所有變更都記錄在履歷中
- ✅ Todo 和 MeetingTask 的日期保持同步
- ✅ 郵件提醒引導使用者使用此功能
- ✅ 零資料庫遷移，零風險部署
- ✅ 完全向後兼容

**升級狀態**: ✅ **完成並可部署**

**預估使用者影響**: 🟢 **正面** - 提供更靈活的任務管理方式

**建議**: 立即部署到生產環境，並監控使用者反饋
