# 逾期任務重設預計完成日期功能 - 升級計畫

## 功能需求概述
針對逾期任務(todo 或 meeting_task)，當事者在變更狀態為未完成時：
1. 原本已有填寫未完成原因欄位 ✅
2. **新增**：重設新的預定完成日期功能
3. 將變更預計完成日期的操作寫入履歷(history_log)
4. 在每日 check_overdue_tasks 郵件提醒中，加入提示可以使用該功能重新設定預計完成日期

## 當前系統架構分析

### 1. 資料模型 (app.py)
- **Todo 模型** (line 341-355)
  - `due_date`: DateTime, nullable=False - 預計完成日期
  - `history_log`: Text - JSON格式的履歷記錄
  - `status`: 狀態欄位 (pending, in-progress, completed, uncompleted)

- **MeetingTask 模型** (line 372-399)
  - `expected_completion_date`: DateTime, nullable=True - 預計完成日期
  - `uncompleted_reason_from_todo`: Text - 未完成原因
  - `history_log`: Text - JSON格式的履歷記錄
  - `todo_id`: 關聯的Todo任務ID

### 2. 現有未完成原因功能
- **後端** (app.py line 1618-1715)
  - `/api/todo/<int:todo_id>/status` PUT endpoint
  - 接收 `uncompleted_reason` 參數
  - 當狀態為 `uncompleted` 時，記錄到履歷並自動切換為 `in-progress`
  - 同步更新關聯的 MeetingTask 狀態和未完成原因

- **前端** (static/js/main.js)
  - line 150-154: 未完成選項和原因輸入界面
  - line 375-385: 確認未完成原因按鈕事件
  - line 388-413: `updateTodoStatus()` 函數

### 3. 逾期任務檢查 (scheduler.py)
- `check_overdue_tasks()` 函數 (line 66-107)
  - 每日檢查逾期任務
  - 發送郵件通知給當事者
  - 目前僅列出逾期任務信息

## 升級實施計畫

### Phase 1: 資料庫架構 (不需要修改)
**評估結果**：現有資料表欄位已足夠
- Todo.due_date 和 MeetingTask.expected_completion_date 已存在
- history_log 欄位可記錄日期變更

### Phase 2: 後端 API 修改

#### 2.1 修改 `/api/todo/<int:todo_id>/status` endpoint (app.py)
**位置**: line 1618-1715

**修改內容**:
```python
# 接收新參數
data = request.get_json()
new_status = data.get('status')
uncompleted_reason = data.get('uncompleted_reason', None)
new_due_date = data.get('new_due_date', None)  # 新增: 接收新的預計完成日期

# 在未完成狀態處理中
if new_status == TodoStatus.UNCOMPLETED.value:
    # 更新預計完成日期
    if new_due_date:
        try:
            new_due_date_parsed = isoparse(new_due_date)
            old_due_date = todo.due_date
            todo.due_date = new_due_date_parsed
            
            # 記錄日期變更到履歷
            history_entry = {
                'event_type': 'due_date_changed',
                'timestamp': datetime.now(utc).isoformat(),
                'actor': {'id': current_user.id, 'name': current_user.name, 'user_key': current_user.user_key},
                'details': {
                    'old_due_date': old_due_date.isoformat(),
                    'new_due_date': new_due_date_parsed.isoformat(),
                    'reason': uncompleted_reason
                }
            }
            history.append(history_entry)
            
            # 同步更新關聯的 MeetingTask
            if todo.meeting_task_id:
                meeting_task = db.session.get(MeetingTask, todo.meeting_task_id)
                if meeting_task:
                    meeting_task.expected_completion_date = new_due_date_parsed
                    # 同步履歷到 MeetingTask
                    
        except Exception as e:
            logging.error(f"Failed to parse new_due_date: {e}")
    
    # 記錄未完成事件 (原有邏輯)
    history_entry = {
        'event_type': 'status_changed',
        'timestamp': datetime.now(utc).isoformat(),
        'actor': {...},
        'details': {'old_status': old_status, 'new_status': TodoStatus.UNCOMPLETED.value, 'reason': uncompleted_reason}
    }
```

**影響範圍**: 
- `update_todo_status()` 函數 (約20行修改)
- 需要同步更新關聯的 MeetingTask.expected_completion_date

### Phase 3: 前端界面修改

#### 3.1 修改未完成原因輸入界面 (static/js/main.js)
**位置**: line 150-154

**修改內容**:
```javascript
<div id="uncompleted-reason-container-${todo.id}" style="display:none; margin-top: 5px;">
    <textarea id="uncompleted-reason-${todo.id}" class="uncompleted-reason-input" 
              placeholder="請輸入未完成原因"></textarea>
    
    <!-- 新增: 預計完成日期輸入 -->
    <label for="new-due-date-${todo.id}">新的預計完成日期:</label>
    <input type="datetime-local" id="new-due-date-${todo.id}" 
           class="new-due-date-input" />
    
    <button type="button" class="btn confirm-uncompleted-btn" 
            data-todo-id="${todo.id}">確認</button>
</div>
```

#### 3.2 修改事件處理器 (static/js/main.js)
**位置**: line 375-385

**修改內容**:
```javascript
if (e.target && e.target.classList.contains('confirm-uncompleted-btn')) {
    const todoId = e.target.dataset.todoId;
    const reasonInput = document.getElementById(`uncompleted-reason-${todoId}`);
    const reason = reasonInput.value.trim();
    
    // 新增: 獲取新的預計完成日期
    const newDueDateInput = document.getElementById(`new-due-date-${todoId}`);
    const newDueDate = newDueDateInput.value;
    
    if (!reason) {
        alert('請輸入未完成原因');
        return;
    }
    
    // 新增: 驗證日期
    if (!newDueDate) {
        alert('請選擇新的預計完成日期');
        return;
    }
    
    updateTodoStatus(todoId, 'uncompleted', reason, newDueDate);
}
```

#### 3.3 修改 updateTodoStatus 函數 (static/js/main.js)
**位置**: line 388-413

**修改內容**:
```javascript
function updateTodoStatus(todoId, status, reason = null, newDueDate = null) {
    const body = { status: status };
    if (reason) {
        body.uncompleted_reason = reason;
    }
    // 新增: 添加新的預計完成日期
    if (newDueDate) {
        body.new_due_date = new Date(newDueDate).toISOString();
    }
    
    // ... 其餘邏輯不變
}
```

### Phase 4: 郵件通知修改 (scheduler.py)

#### 4.1 修改 check_overdue_tasks 函數
**位置**: line 66-107

**修改內容**:
```python
if user_overdue_tasks:
    subject = f"【逾期任務提醒】您有 {len(user_overdue_tasks)} 項任務已逾期！"
    body_parts = [f"您好 {user.name}，", "", "以下是您已逾期的任務：", ""]
    for task in user_overdue_tasks:
        due_date_str = task.due_date.astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M')
        body_parts.append(f"    標題: {task.title}")
        body_parts.append(f"    描述: {task.description}")
        body_parts.append(f"    預計完成日期: {due_date_str}")
        body_parts.append("")
    
    # 新增提醒訊息
    body_parts.append("<b>💡 小提示：</b>")
    body_parts.append("如任務無法在原定期限完成，您可以在系統中將任務狀態設為「未完成」，")
    body_parts.append("填寫未完成原因後，同時重新設定新的預計完成日期。")
    body_parts.append("")
    
    body_parts.append("請登入系統查看並盡快處理您的逾期任務：")
    body_parts.append("http://192.168.6.119:5001")
    body = "<br>".join(body_parts)
```

### Phase 5: 樣式調整 (static/css/styles.css)

**新增樣式**:
```css
/* 新的預計完成日期輸入框 */
.new-due-date-input {
    width: 100%;
    padding: 8px;
    margin-top: 8px;
    margin-bottom: 8px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 14px;
}

.new-due-date-input:focus {
    outline: none;
    border-color: #3498db;
    box-shadow: 0 0 5px rgba(52, 152, 219, 0.3);
}

#uncompleted-reason-container label {
    display: block;
    margin-top: 8px;
    margin-bottom: 4px;
    font-weight: 600;
    color: #333;
}
```

## 實施步驟順序

1. **Step 1**: 修改後端 API (app.py)
   - 修改 `update_todo_status()` 函數
   - 添加新的參數處理邏輯
   - 測試 API endpoint

2. **Step 2**: 修改前端界面 (main.js)
   - 添加日期輸入框到 HTML 生成邏輯
   - 修改事件處理器
   - 修改 API 調用函數
   - 測試前端交互

3. **Step 3**: 修改郵件通知 (scheduler.py)
   - 更新 `check_overdue_tasks()` 郵件內容
   - 測試郵件發送

4. **Step 4**: 添加樣式 (styles.css)
   - 添加新輸入框樣式
   - 測試界面美觀性

5. **Step 5**: 整合測試
   - 測試完整流程
   - 驗證履歷記錄
   - 驗證 MeetingTask 同步

## 測試計畫

### 測試案例 1: Todo 任務未完成並重設日期
1. 創建一個逾期的 Todo 任務
2. 將狀態改為「未完成」
3. 填寫未完成原因
4. 選擇新的預計完成日期
5. 確認提交
6. 驗證：
   - Todo.due_date 已更新
   - history_log 記錄了日期變更
   - 任務狀態變為「進行中」

### 測試案例 2: MeetingTask 關聯任務同步
1. 創建一個與 MeetingTask 關聯的逾期 Todo
2. 執行未完成並重設日期操作
3. 驗證：
   - MeetingTask.expected_completion_date 已同步更新
   - MeetingTask.uncompleted_reason_from_todo 已記錄
   - MeetingTask.history_log 已同步

### 測試案例 3: 郵件通知
1. 等待或手動觸發 check_overdue_tasks
2. 驗證：
   - 郵件包含新的提示訊息
   - 格式正確，可讀性好

### 測試案例 4: 邊界條件
1. 未填寫未完成原因 - 應提示錯誤
2. 未選擇新日期 - 應提示錯誤
3. 選擇過去的日期 - 可選：添加驗證
4. 無關聯 MeetingTask 的 Todo - 應正常運作

## 風險評估

### 低風險
- ✅ 不需要修改資料庫結構
- ✅ 現有功能不受影響（向後兼容）
- ✅ 新增欄位為可選參數

### 中風險
- ⚠️ 履歷記錄格式需要正確處理
- ⚠️ Todo 和 MeetingTask 同步邏輯需要完整測試

### 緩解措施
- 在開發環境充分測試
- 保留資料庫備份
- 逐步部署，先測試 Todo，再測試 MeetingTask 同步
- 詳細的日誌記錄

## 預估工作量

- **後端開發**: 2-3 小時
- **前端開發**: 2-3 小時
- **郵件修改**: 0.5 小時
- **測試**: 2-3 小時
- **總計**: 6.5-9.5 小時

## 部署計畫

1. 在測試環境部署並測試
2. 備份生產環境資料庫
3. 部署到生產環境
4. 監控日誌和用戶反饋
5. 必要時快速回滾

## 結論

此升級計畫為**低風險、高價值**的功能改進：
- ✅ 不需要資料庫遷移
- ✅ 向後兼容
- ✅ 改善用戶體驗
- ✅ 符合業務需求
- ✅ 實施複雜度適中

建議立即開始實施。
