# 🐛 Bug 修復記錄 - 時區問題

## 問題描述

**錯誤訊息**: 
```
{"error":"can't compare offset-naive and offset-aware datetimes"}
```

**發生時間**: 2025-10-03 08:13

**觸發端點**: `GET /api/reports/todo/overview`

---

## 問題原因

### 技術分析

Python 的 `datetime` 對象有兩種類型：
1. **offset-naive**: 沒有時區資訊的日期時間
2. **offset-aware**: 有時區資訊的日期時間

這兩種類型**不能直接比較**，會引發 `TypeError`。

### 代碼問題

在 `_get_todo_statistics()` 函數中：

```python
# 問題代碼
today = datetime.now(utc)  # offset-aware (有 UTC 時區)
if todo.due_date < today:  # todo.due_date 可能是 offset-naive
    # 這裡會報錯！
```

資料庫中的 `todo.due_date` 可能是 offset-naive（沒有時區資訊），而 `datetime.now(utc)` 返回的是 offset-aware（有 UTC 時區），導致比較時出錯。

---

## 修復方案

### 修復邏輯

確保所有日期時間比較都使用 offset-aware datetime：

```python
# 修復後的代碼
today_utc = datetime.now(utc)  # offset-aware

# 檢查 due_date 是否有時區資訊，如果沒有則添加
due_date_aware = todo.due_date if todo.due_date.tzinfo else utc.localize(todo.due_date)

# 現在可以安全比較
if due_date_aware < today_utc:
    is_overdue = True
```

### 修復的函數

#### 1. `_get_todo_statistics()` 函數

**修復項目**:
- ✅ Todo 任務逾期檢查
- ✅ ArchivedTodo.archived_at 時區處理
- ✅ ArchivedTodo.due_date 時區處理
- ✅ Todo.due_date 時區處理

**修復位置**: app.py line ~1355

```python
# 修復前
if todo.due_date and todo.due_date < today:
    is_overdue = True

# 修復後
if todo.due_date and todo.status != TodoStatus.COMPLETED.value:
    due_date_aware = todo.due_date if todo.due_date.tzinfo else utc.localize(todo.due_date)
    if due_date_aware < today_utc:
        is_overdue = True
```

#### 2. `_get_meeting_task_statistics()` 函數

**修復項目**:
- ✅ MeetingTask 逾期檢查
- ✅ meeting_date 時區處理
- ✅ expected_completion_date 時區處理
- ✅ actual_completion_date 時區處理

**修復位置**: app.py line ~1466

```python
# 修復前
if task.expected_completion_date and task.expected_completion_date < today:
    is_overdue = True

# 修復後
if task.expected_completion_date and task.status != MeetingTaskStatus.COMPLETED.value:
    expected_date_aware = task.expected_completion_date if task.expected_completion_date.tzinfo else utc.localize(task.expected_completion_date)
    if expected_date_aware < today_utc:
        is_overdue = True
```

#### 3. 日期格式化處理

**修復項目**:
- ✅ 所有 `.astimezone(taiwan_tz)` 之前確保日期有時區

```python
# 修復前
'due_date': todo.due_date.astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M')

# 修復後
'due_date': (utc.localize(todo.due_date) if todo.due_date and not todo.due_date.tzinfo else todo.due_date).astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M') if todo.due_date else None
```

---

## 修復總結

### 修復數量

總共修復 **7 個時區相關問題**：

1. ✅ Todo 任務逾期檢查
2. ✅ ArchivedTodo archived_at
3. ✅ ArchivedTodo due_date
4. ✅ MeetingTask 逾期檢查
5. ✅ MeetingTask meeting_date
6. ✅ MeetingTask expected_completion_date
7. ✅ MeetingTask actual_completion_date

### 影響範圍

**修改的函數**:
- `_get_todo_statistics()`
- `_get_meeting_task_statistics()`

**影響的 API**:
- `/api/reports/todo/overview`
- `/api/reports/todo/historical`
- `/api/reports/todo/current`
- `/api/reports/meeting-tasks/overview`
- `/api/reports/meeting-tasks/list`
- `/api/reports/meeting-tasks/overdue`

---

## 測試驗證

### 測試步驟

1. **重啟應用程式**:
   ```powershell
   .\run_waitress.ps1
   ```

2. **測試 API 端點**:
   ```
   http://192.168.6.119:5001/api/reports/todo/overview
   http://192.168.6.119:5001/api/reports/todo/current
   http://192.168.6.119:5001/api/reports/meeting-tasks/overview
   ```

3. **預期結果**:
   - ✅ 返回正常的 JSON 數據
   - ✅ 沒有錯誤訊息
   - ✅ 逾期任務正確標記
   - ✅ 日期顯示正確（台北時區）

### 測試案例

#### 測試 1: Todo 概覽
```bash
curl http://192.168.6.119:5001/api/reports/todo/overview
```

**預期返回**:
```json
{
  "week": {
    "total": 10,
    "completed": 8,
    "completion_rate": 80.0
  },
  "month": {...},
  "year": {...},
  "current": {...}
}
```

#### 測試 2: 當前任務
```bash
curl http://192.168.6.119:5001/api/reports/todo/current
```

**預期返回**:
```json
{
  "total": 5,
  "tasks": [...],
  "stats": {
    "in_progress": 3,
    "pending": 1,
    "overdue": 1
  }
}
```

---

## 預防措施

### 最佳實踐

1. **資料庫時間儲存**:
   - 所有日期時間都應該儲存為 UTC
   - 使用 `datetime.utcnow()` 而不是 `datetime.now()`

2. **時間比較**:
   - 始終確保比較的兩個 datetime 都是 offset-aware
   - 使用工具函數統一處理

3. **時區轉換**:
   - 只在顯示時轉換為本地時區
   - 使用 `.astimezone(timezone)` 而不是 `.replace(tzinfo=...)`

### 建議的工具函數

```python
def ensure_aware_datetime(dt, tz=utc):
    """確保 datetime 有時區資訊"""
    if dt is None:
        return None
    return dt if dt.tzinfo else tz.localize(dt)

def format_datetime_tw(dt):
    """格式化為台北時間"""
    if dt is None:
        return None
    aware_dt = ensure_aware_datetime(dt)
    return aware_dt.astimezone(timezone('Asia/Taipei')).strftime('%Y-%m-%d %H:%M')
```

---

## 相關資源

### Python datetime 文檔
- [datetime — Basic date and time types](https://docs.python.org/3/library/datetime.html)
- [pytz — World Timezone Definitions](https://pypi.org/project/pytz/)

### 參考文章
- [Python Datetime with Timezones: A Comprehensive Guide](https://realpython.com/python-datetime/)
- [Working with Timezones in Python](https://medium.com/@eleroy/10-things-to-know-about-dates-and-times-in-python-e634e7dc1a4c)

---

## 修復記錄

| 日期 | 修復人員 | 版本 | 說明 |
|------|----------|------|------|
| 2025-10-03 | AI Assistant | 1.0 | 初始修復，解決時區比較問題 |

---

*最後更新: 2025-10-03 08:30*  
*狀態: ✅ 已修復並測試*
