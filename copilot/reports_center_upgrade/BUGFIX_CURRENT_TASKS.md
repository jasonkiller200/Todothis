# 🐛 Bug 修復記錄 - 當前未完成任務顯示已完成任務

## 問題描述

**發現時間**: 2025-10-03  
**發現位置**: Todo 報告頁面 → 「當前未完成」分頁  
**問題**: 當前未完成任務列表中顯示了已完成的任務

---

## 問題分析

### 預期行為
「當前未完成任務」分頁應該只顯示：
- ✅ 進行中 (in-progress)
- ✅ 待開始 (pending)
- ✅ 未完成 (uncompleted)

**不應該顯示**：
- ❌ 已完成 (completed)
- ❌ 已歸檔的任務

### 實際行為
列表中混入了狀態為 `completed` 的任務。

---

## 原因分析

### 代碼邏輯問題

**位置**: `app.py` → `get_todo_current()` 函數 (line 1842)

**原始代碼**:
```python
# 過濾出當前任務
current_tasks = [t for t in stats['tasks'] if not t.get('is_archived')]
```

**問題**:
- 只過濾了 `is_archived` (是否已歸檔)
- **沒有過濾** `status` (任務狀態)
- 導致 `status='completed'` 的任務也被包含在列表中

### 資料流程

1. `_get_todo_statistics()` 返回所有當前任務（包括已完成）
2. `get_todo_current()` 接收所有任務
3. 只過濾 `is_archived=False`
4. **已完成但未歸檔的任務仍然在列表中** ❌

---

## 修復方案

### 修改內容

**檔案**: `app.py` (line 1841-1856)

**修改前**:
```python
# 過濾出當前任務
current_tasks = [t for t in stats['tasks'] if not t.get('is_archived')]

# 如果只顯示逾期任務
if show_overdue_only:
    current_tasks = [t for t in current_tasks if t.get('is_overdue')]

return jsonify({
    'total': len(current_tasks),
    'tasks': current_tasks,
    'stats': {
        'in_progress': stats['in_progress'],
        'pending': stats['pending'],
        'overdue': stats['overdue']
    }
})
```

**修改後**:
```python
# 過濾出當前未完成任務（排除已完成和已歸檔）
current_tasks = [
    t for t in stats['tasks'] 
    if not t.get('is_archived') and t.get('status') != TodoStatus.COMPLETED.value
]

# 如果只顯示逾期任務
if show_overdue_only:
    current_tasks = [t for t in current_tasks if t.get('is_overdue')]

return jsonify({
    'total': len(current_tasks),
    'tasks': current_tasks,
    'stats': {
        'in_progress': stats['in_progress'],
        'pending': stats['pending'],
        'overdue': stats['overdue'],
        'uncompleted': stats['uncompleted']  # 新增
    }
})
```

### 修改重點

1. **新增過濾條件**:
   ```python
   and t.get('status') != TodoStatus.COMPLETED.value
   ```
   - 排除狀態為 `completed` 的任務

2. **新增統計欄位**:
   ```python
   'uncompleted': stats['uncompleted']
   ```
   - 返回未完成任務的數量

3. **改善註解**:
   ```python
   # 過濾出當前未完成任務（排除已完成和已歸檔）
   ```
   - 更清楚說明過濾邏輯

---

## 測試驗證

### 測試步驟

1. **重新啟動應用**:
   ```powershell
   .\run_waitress.ps1
   ```

2. **訪問頁面**:
   ```
   http://192.168.6.119:5001/reports/todo
   ```

3. **點擊「當前未完成」分頁**

4. **驗證**:
   - ✅ 只顯示進行中、待開始、未完成的任務
   - ✅ 不顯示已完成的任務
   - ✅ 統計數字正確

### 測試案例

#### 測試案例 1: 基本過濾
**資料**:
- 任務 A: status=in-progress, is_archived=False
- 任務 B: status=completed, is_archived=False
- 任務 C: status=pending, is_archived=False
- 任務 D: status=completed, is_archived=True

**預期結果**:
- ✅ 顯示：任務 A, 任務 C
- ❌ 不顯示：任務 B, 任務 D

#### 測試案例 2: 逾期任務
**資料**:
- 任務 E: status=in-progress, is_overdue=True
- 任務 F: status=completed, is_overdue=True

**預期結果** (overdue_only=true):
- ✅ 顯示：任務 E
- ❌ 不顯示：任務 F

---

## 影響範圍

### 受影響的功能
- ✅ `/api/reports/todo/current` API
- ✅ Todo 報告頁面 → 「當前未完成」分頁

### 不受影響的功能
- ✅ 概覽統計分頁
- ✅ 歷史任務分頁
- ✅ 個人排行分頁
- ✅ 其他 API 端點

---

## 相關問題

### 為什麼會有「已完成但未歸檔」的任務？

在系統中，任務完成後不會立即歸檔：
1. 使用者完成任務（status=completed）
2. 任務保留在當前列表中，供查看和確認
3. 稍後由系統或管理員手動歸檔（is_archived=True）

這是正常的工作流程，但在「當前未完成」列表中應該排除這些已完成的任務。

---

## 經驗教訓

### 命名要精確
- API 名稱是 `get_todo_current()`（獲取當前任務）
- 但實際用途是「獲取當前**未完成**任務」
- 建議：將函數名改為 `get_todo_incomplete()` 更清楚

### 過濾條件要完整
- 過濾邏輯應該考慮所有相關欄位
- `is_archived` 和 `status` 都是重要的過濾條件
- 不應該假設「未歸檔」就等於「未完成」

### 文檔要清楚
```python
def get_todo_current():
    """獲取當前未完成任務列表"""  # ✅ 清楚
    # vs
    """獲取當前任務"""  # ❌ 含糊
```

---

## 建議改進

### 1. 重新命名函數（可選）

**建議**:
```python
# 改名更精確
@app.route('/api/reports/todo/incomplete')
def get_todo_incomplete():
    """獲取當前未完成任務列表"""
```

### 2. 增加單元測試

```python
def test_current_tasks_excludes_completed():
    """測試當前任務列表不包含已完成任務"""
    response = client.get('/api/reports/todo/current')
    data = response.json()
    
    # 確認沒有已完成的任務
    for task in data['tasks']:
        assert task['status'] != 'completed'
```

### 3. 增加 API 文檔

```python
@app.route('/api/reports/todo/current')
@login_required
def get_todo_current():
    """
    獲取當前未完成任務列表
    
    Returns:
        只包含以下狀態的任務：
        - in-progress (進行中)
        - pending (待開始)
        - uncompleted (未完成)
        
        排除：
        - completed (已完成)
        - is_archived=True (已歸檔)
    """
```

---

## 修復記錄

| 日期 | 修復人員 | 版本 | 說明 |
|------|----------|------|------|
| 2025-10-03 | AI Assistant | 1.0 | 初始修復，增加 status 過濾條件 |

---

*最後更新: 2025-10-03*  
*狀態: ✅ 已修復並驗證*  
*優先級: 中*
