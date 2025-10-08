# 權限修正總結

## 修正日期
2025年1月3日

## 問題描述
1. **Todo 報表權限問題**：廠長和組件課長在 `/reports/todo` 只能看到自己的數據，無法看到部門或單位的統計
2. **個人排行榜權限**：組件課長無法查看排行榜，顯示「您沒有權限查看排行榜」
3. **首頁報工中心連結**：副課長在首頁看不到「📊 報告中心」連結

## 修正內容

### 1. Todo 報表權限邏輯修正 (`app.py` line 1813-1838)

**修正前：**
```python
# 根據使用者權限決定查詢範圍
user_filter = None
if current_user.level not in [UserLevel.ADMIN.value, UserLevel.EXECUTIVE_MANAGER.value]:
    user_filter = current_user.id

# 獲取統計數據
week_stats = _get_todo_statistics(start_date=start_of_week_utc, user_id=user_filter)
```

**修正後：**
```python
# 根據使用者權限決定查詢範圍
# 管理員和協理可以看全部
if current_user.level in [UserLevel.ADMIN.value, UserLevel.EXECUTIVE_MANAGER.value]:
    week_stats = _get_todo_statistics(start_date=start_of_week_utc)
    # ... 其他統計
# 廠長、經理、副理可以看自己單位的
elif current_user.level in [UserLevel.PLANT_MANAGER.value, UserLevel.MANAGER.value, UserLevel.ASSISTANT_MANAGER.value]:
    unit_users = User.query.filter_by(unit=current_user.unit).all()
    unit_user_ids = [u.id for u in unit_users]
    week_stats = _get_todo_statistics_multi_users(start_date=start_of_week_utc, user_ids=unit_user_ids)
    # ... 其他統計
# 課長、副課長可以看自己部門和單位的
elif current_user.level in [UserLevel.SECTION_CHIEF.value, UserLevel.DEPUTY_SECTION_CHIEF.value]:
    dept_users = User.query.filter_by(department=current_user.department, unit=current_user.unit).all()
    dept_user_ids = [u.id for u in dept_users]
    week_stats = _get_todo_statistics_multi_users(start_date=start_of_week_utc, user_ids=dept_user_ids)
    # ... 其他統計
else:
    # 一般員工只能看自己的
    week_stats = _get_todo_statistics(start_date=start_of_week_utc, user_id=current_user.id)
```

### 2. 新增多使用者統計函數 (`app.py` line 1390-1502)

新增 `_get_todo_statistics_multi_users()` 函數，用於支援多使用者的 Todo 統計查詢：

```python
def _get_todo_statistics_multi_users(start_date=None, end_date=None, user_ids=None, status=None, include_archived=True):
    """
    多使用者的 Todo 統計查詢函數
    
    Args:
        start_date: 開始日期 (UTC)
        end_date: 結束日期 (UTC)
        user_ids: 使用者 ID 列表
        status: 任務狀態
        include_archived: 是否包含已歸檔的任務
    
    Returns:
        dict: 統計數據
    """
    # 查詢已歸檔的任務
    archived_query = ArchivedTodo.query
    if user_ids:
        archived_query = archived_query.filter(ArchivedTodo.user_id.in_(user_ids))
    
    # 查詢當前任務
    current_query = Todo.query
    if user_ids:
        current_query = current_query.filter(Todo.user_id.in_(user_ids))
    
    # ... 統計邏輯
```

### 3. Todo 排行榜權限修正 (`app.py` line 2161-2166)

**修正前：**
```python
# 權限檢查：只有管理層可以查看排行榜
if current_user.level not in [UserLevel.ADMIN.value, UserLevel.EXECUTIVE_MANAGER.value, UserLevel.MANAGER.value]:
    return jsonify({'error': '您沒有權限查看排行榜'}), 403
```

**修正後：**
```python
# 權限檢查：管理層及課長可以查看排行榜
if current_user.level not in [UserLevel.ADMIN.value, UserLevel.EXECUTIVE_MANAGER.value, 
                               UserLevel.PLANT_MANAGER.value, UserLevel.MANAGER.value, 
                               UserLevel.ASSISTANT_MANAGER.value, UserLevel.SECTION_CHIEF.value, 
                               UserLevel.DEPUTY_SECTION_CHIEF.value]:
    return jsonify({'error': '您沒有權限查看排行榜'}), 403
```

### 4. 排行榜函數權限邏輯 (`app.py` line 1504-1596)

修改 `_get_user_ranking()` 函數，增加 `current_user` 參數並實現分層權限控制：

```python
def _get_user_ranking(period='week', metric='completed', limit=10, current_user=None):
    # 根據權限決定查詢範圍
    if current_user:
        if current_user.level in [UserLevel.ADMIN.value, UserLevel.EXECUTIVE_MANAGER.value]:
            # 管理員和協理可以看所有人
            users = User.query.filter_by(is_active=True).filter(User.level != UserLevel.ADMIN.value).all()
        elif current_user.level in [UserLevel.PLANT_MANAGER.value, UserLevel.MANAGER.value, UserLevel.ASSISTANT_MANAGER.value]:
            # 廠長、經理、副理可以看自己單位的人
            users = User.query.filter_by(is_active=True, unit=current_user.unit).filter(User.level != UserLevel.ADMIN.value).all()
        elif current_user.level in [UserLevel.SECTION_CHIEF.value, UserLevel.DEPUTY_SECTION_CHIEF.value]:
            # 課長、副課長可以看自己部門和單位的人
            users = User.query.filter_by(is_active=True, department=current_user.department, unit=current_user.unit).filter(User.level != UserLevel.ADMIN.value).all()
        else:
            # 其他人只能看自己
            users = [current_user]
```

### 5. 首頁報工中心連結修正 (`templates/index.html` line 23-25)

**修正前：**
```html
{% if current_user.level in ['admin', 'executive-manager', 'plant-manager', 'manager', 'assistant-manager', 'section-chief'] %}
    <a href="{{ url_for('reports') }}">📊 報告中心</a>
{% endif %}
```

**修正後：**
```html
{% if current_user.level in ['admin', 'executive-manager', 'plant-manager', 'manager', 'assistant-manager', 'section-chief', 'deputy-section-chief'] %}
    <a href="{{ url_for('reports') }}">📊 報告中心</a>
{% endif %}
```

## 權限層級說明

修正後的權限架構：

| 職位 | Todo 報表數據範圍 | 排行榜權限 | 首頁報工中心連結 |
|------|------------------|-----------|-----------------|
| 系統管理員 (admin) | 全部 | 全部人員 | ✓ |
| 協理 (executive-manager) | 全部 | 全部人員 | ✓ |
| 廠長 (plant-manager) | 自己單位 | 單位人員 | ✓ |
| 經理 (manager) | 自己單位 | 單位人員 | ✓ |
| 副理 (assistant-manager) | 自己單位 | 單位人員 | ✓ |
| 課長 (section-chief) | 自己部門 | 部門人員 | ✓ |
| 副課長 (deputy-section-chief) | 自己部門 | 部門人員 | ✓ |
| 一般員工 | 僅自己 | 僅自己 | ✗ |

## 測試建議

1. **廠長測試**：
   - 登入廠長帳號
   - 訪問 `/reports/todo`
   - 確認可以看到單位內所有人員的統計數據
   - 確認個人排行榜顯示單位內所有人員

2. **組件課長測試**：
   - 登入組件課長帳號
   - 確認首頁有「📊 報告中心」連結
   - 訪問 `/reports/todo`
   - 確認可以看到組件課內所有人員的統計數據
   - 確認個人排行榜顯示組件課內所有人員

3. **副課長測試**：
   - 登入副課長帳號
   - 確認首頁有「📊 報告中心」連結
   - 確認權限與課長相同

## 相關文件

- Meeting Task 報表已經有正確的權限邏輯 (`app.py` line 2073-2102)
- 此次修正使 Todo 報表與 Meeting Task 報表的權限邏輯保持一致

## 注意事項

- 所有修改已向後兼容，不影響現有功能
- 權限檢查在後端 API 層級實施，確保安全性
- 前端顯示邏輯與後端權限檢查保持一致
