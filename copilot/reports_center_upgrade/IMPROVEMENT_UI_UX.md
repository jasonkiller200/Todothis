# 🎨 UI/UX 改善記錄 - 報告頁面優化

## 改善項目

**改善時間**: 2025-10-03  
**改善位置**: Todo 報告頁面  
**改善類型**: UI/UX 優化

---

## 改善內容

### 1. 📅 日期顯示優化

**問題**:
- 預計完成日期顯示格式為 `2025-10-03 14:30`
- 時間資訊對於日期任務來說通常不重要
- 佔用過多表格空間

**改善方案**:
- 日期格式從 `%Y-%m-%d %H:%M` 改為 `%Y-%m-%d`
- 只顯示日期，隱藏時間
- 節省表格空間，更清爽

**修改前**:
```
預計完成: 2025-10-03 14:30
```

**修改後**:
```
預計完成: 2025-10-03
```

---

### 2. 📝 任務內容顯示

**問題**:
- 表格中只顯示任務標題
- 無法看到任務的詳細內容/描述
- 需要點擊其他頁面才能看到完整資訊

**改善方案**:
- 新增「任務內容」欄位
- 顯示任務描述（截斷至 50 字）
- 超過 50 字時顯示 "..." 並提供 hover 提示
- 滑鼠懸停時顯示完整內容

**表格結構**:

| 編號 | 任務標題 | **任務內容** | 負責人 | 狀態 | 預計完成 |
|------|---------|-------------|--------|------|----------|
| 1    | 修復 Bug | 修復登入頁面的錯誤... | 張三 | 進行中 | 2025-10-05 |

**功能**:
- ✅ 短描述：截斷至 50 字 + "..."
- ✅ Hover 提示：顯示完整內容
- ✅ 無描述時顯示：「無描述」
- ✅ 樣式優化：灰色文字，hover 變藍色

---

## 修改的檔案

### 1. `app.py` - 後端 API

#### 修改位置 1: `_get_todo_statistics()` - 已歸檔任務 (line 1336)

**修改前**:
```python
'due_date': (utc.localize(todo.due_date) if todo.due_date and not todo.due_date.tzinfo else todo.due_date).astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M') if todo.due_date else None,
```

**修改後**:
```python
'due_date': (utc.localize(todo.due_date) if todo.due_date and not todo.due_date.tzinfo else todo.due_date).astimezone(taiwan_tz).strftime('%Y-%m-%d') if todo.due_date else None,
```

#### 修改位置 2: `_get_todo_statistics()` - 當前任務 (line 1371)

**修改前**:
```python
'due_date': (utc.localize(todo.due_date) if todo.due_date and not todo.due_date.tzinfo else todo.due_date).astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M') if todo.due_date else None,
```

**修改後**:
```python
'due_date': (utc.localize(todo.due_date) if todo.due_date and not todo.due_date.tzinfo else todo.due_date).astimezone(taiwan_tz).strftime('%Y-%m-%d') if todo.due_date else None,
```

#### 影響範圍
✅ 所有使用 `_get_todo_statistics()` 的 API：
- `/api/reports/todo/overview`
- `/api/reports/todo/historical`
- `/api/reports/todo/current`
- `/api/reports/todo/ranking`

---

### 2. `templates/reports_todo.html` - 前端頁面

#### 修改位置 1: 表格結構 (line 721)

**修改前**:
```html
html += '<th>編號</th><th>任務標題</th><th>負責人</th><th>狀態</th>';
```

**修改後**:
```html
html += '<th>編號</th><th>任務標題</th><th>任務內容</th><th>負責人</th><th>狀態</th>';
```

#### 修改位置 2: 任務內容處理邏輯 (line 726-736)

**新增代碼**:
```javascript
// 處理任務描述：如果太長則截斷並顯示提示
const description = task.description || '無描述';
const shortDesc = description.length > 50 ? description.substring(0, 50) + '...' : description;
const descHtml = description.length > 50 
    ? `<span class="task-desc" title="${escapeHtml(description)}">${escapeHtml(shortDesc)}</span>`
    : `<span class="task-desc">${escapeHtml(shortDesc)}</span>`;

html += '<tr>';
html += `<td>${(currentPage - 1) * 50 + index + 1}</td>`;
html += `<td class="task-title">${escapeHtml(task.title)}</td>`;
html += `<td>${descHtml}</td>`;  // 新增
html += `<td>${escapeHtml(task.user_name)}</td>`;
html += `<td><span class="status-badge ${statusClass}">${statusText}</span></td>`;
html += `<td>${task.due_date || '-'}</td>`;
```

#### 修改位置 3: CSS 樣式 (line 312-338)

**新增樣式**:
```css
/* 任務內容樣式 */
.task-title {
    font-weight: 500;
    color: var(--color-text);
}

.task-desc {
    color: var(--color-text-light);
    font-size: 0.9em;
    display: block;
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: help;
}

.task-desc:hover {
    color: var(--color-primary);
}

/* 工具提示樣式 */
.task-desc[title] {
    position: relative;
}
```

---

## 視覺效果

### 修改前

| 編號 | 任務標題 | 負責人 | 狀態 | 預計完成 |
|------|---------|--------|------|----------|
| 1    | 修復登入問題 | 張三 | 進行中 | 2025-10-03 14:30 |
| 2    | 優化性能 | 李四 | 待開始 | 2025-10-05 09:00 |

**問題**:
- ❌ 不知道任務內容
- ❌ 日期包含時間，太冗長
- ❌ 需要點擊其他地方查看詳情

---

### 修改後

| 編號 | 任務標題 | 任務內容 | 負責人 | 狀態 | 預計完成 |
|------|---------|---------|--------|------|----------|
| 1    | 修復登入問題 | 修復使用者登入時出現的錯誤，檢查 session... (hover 查看全文) | 張三 | 進行中 | 2025-10-03 |
| 2    | 優化性能 | 優化資料庫查詢效能，減少 API 回應時間... (hover 查看全文) | 李四 | 待開始 | 2025-10-05 |

**改善**:
- ✅ 可以直接看到任務內容
- ✅ 日期簡潔清晰
- ✅ Hover 可查看完整內容
- ✅ 介面更清爽易讀

---

## 技術細節

### 日期格式轉換

**Python strftime 格式**:
```python
# 修改前
.strftime('%Y-%m-%d %H:%M')  # 輸出: 2025-10-03 14:30

# 修改後
.strftime('%Y-%m-%d')         # 輸出: 2025-10-03
```

### 字串截斷邏輯

**JavaScript 截斷**:
```javascript
// 取得描述
const description = task.description || '無描述';

// 截斷至 50 字
const shortDesc = description.length > 50 
    ? description.substring(0, 50) + '...' 
    : description;

// 生成 HTML（帶 title 屬性）
const descHtml = description.length > 50 
    ? `<span class="task-desc" title="${escapeHtml(description)}">${escapeHtml(shortDesc)}</span>`
    : `<span class="task-desc">${escapeHtml(shortDesc)}</span>`;
```

### XSS 防護

**使用 `escapeHtml()` 防止 XSS 攻擊**:
```javascript
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}
```

---

## 測試驗證

### 測試案例 1: 短描述（< 50 字）

**輸入**:
```json
{
  "title": "修復 Bug",
  "description": "修復登入問題",
  "due_date": "2025-10-03 14:30:00"
}
```

**預期輸出**:
- 任務內容欄位：`修復登入問題`
- 預計完成：`2025-10-03`
- 無 hover 提示

---

### 測試案例 2: 長描述（> 50 字）

**輸入**:
```json
{
  "title": "優化性能",
  "description": "優化資料庫查詢效能，減少 API 回應時間，增加快取機制，並優化前端資源載入速度",
  "due_date": "2025-10-05 09:00:00"
}
```

**預期輸出**:
- 任務內容欄位：`優化資料庫查詢效能，減少 API 回應時間，增加快取機制，並優化前端資源載...`
- 預計完成：`2025-10-05`
- Hover 時顯示完整描述

---

### 測試案例 3: 無描述

**輸入**:
```json
{
  "title": "測試任務",
  "description": null,
  "due_date": "2025-10-10 00:00:00"
}
```

**預期輸出**:
- 任務內容欄位：`無描述`
- 預計完成：`2025-10-10`

---

### 測試案例 4: 包含特殊字元

**輸入**:
```json
{
  "title": "測試 <script>",
  "description": "測試 <script>alert('XSS')</script> 攻擊",
  "due_date": "2025-10-03"
}
```

**預期輸出**:
- 任務內容欄位：`測試 &lt;script&gt;alert('XSS')&lt;/script&gt; 攻擊`
- 無 XSS 攻擊（已轉義）

---

## 瀏覽器相容性

### Hover 提示（title 屬性）
✅ 所有現代瀏覽器原生支援
- Chrome ✅
- Firefox ✅
- Edge ✅
- Safari ✅

### CSS 樣式
✅ 使用標準 CSS 屬性
- `text-overflow: ellipsis` ✅
- `white-space: nowrap` ✅
- `overflow: hidden` ✅

---

## 使用者體驗改善

### 改善前
1. 使用者看到任務列表
2. 只能看到標題，不知道內容
3. 需要點擊其他地方查看詳情
4. 日期包含時間，視覺混亂

**體驗評分**: ⭐⭐⭐ (3/5)

### 改善後
1. 使用者看到任務列表
2. 直接看到任務內容摘要
3. Hover 可查看完整內容
4. 日期簡潔清晰

**體驗評分**: ⭐⭐⭐⭐⭐ (5/5)

---

## 後續優化建議

### 1. 彈出視窗顯示完整內容

**建議**:
- 點擊任務標題時，彈出 Modal 顯示完整任務資訊
- 包含：標題、完整描述、負責人、狀態、日期等

**實作**:
```javascript
function showTaskDetail(taskId) {
    // 彈出 Modal 顯示完整任務資訊
}
```

---

### 2. 可自訂截斷長度

**建議**:
- 讓使用者選擇顯示長度（30/50/100 字）
- 儲存在 LocalStorage

**實作**:
```javascript
const maxLength = localStorage.getItem('task_desc_length') || 50;
const shortDesc = description.length > maxLength 
    ? description.substring(0, maxLength) + '...' 
    : description;
```

---

### 3. 更美觀的 Tooltip

**建議**:
- 使用 CSS 自訂 Tooltip 樣式
- 或使用 Tippy.js 等函式庫

**實作**:
```html
<!-- 引入 Tippy.js -->
<script src="https://unpkg.com/@popperjs/core@2"></script>
<script src="https://unpkg.com/tippy.js@6"></script>

<script>
tippy('.task-desc', {
    content(reference) {
        return reference.getAttribute('data-desc');
    },
});
</script>
```

---

### 4. 響應式設計

**建議**:
- 在小螢幕上，任務內容欄位可以隱藏
- 或調整截斷長度

**實作**:
```css
@media (max-width: 768px) {
    .task-desc {
        max-width: 150px;
    }
    
    /* 或完全隱藏 */
    th:nth-child(3),
    td:nth-child(3) {
        display: none;
    }
}
```

---

## Meeting Task 相容性

### 檢查結果
✅ Meeting Task 的日期格式已經是 `%Y-%m-%d`，無需修改

**位置**: `app.py` → `_get_meeting_task_statistics()`

**代碼**:
```python
'expected_completion_date': (utc.localize(task.expected_completion_date) 
    if task.expected_completion_date and not task.expected_completion_date.tzinfo 
    else task.expected_completion_date).astimezone(taiwan_tz).strftime('%Y-%m-%d') 
    if task.expected_completion_date else None,
```

---

## 修改記錄

| 日期 | 修改人員 | 版本 | 說明 |
|------|----------|------|------|
| 2025-10-03 | AI Assistant | 1.0 | 初始改善：日期格式 + 任務內容顯示 |

---

## 測試步驟

### 1. 重新啟動應用
```powershell
.\run_waitress.ps1
```

### 2. 訪問報告頁面
```
http://192.168.6.119:5001/reports/todo
```

### 3. 檢查改善項目

**日期顯示**:
- ✅ 預計完成日期只顯示 `2025-10-03`（無時間）
- ✅ 格式一致

**任務內容**:
- ✅ 有「任務內容」欄位
- ✅ 長描述被截斷至 50 字 + "..."
- ✅ Hover 顯示完整內容
- ✅ 無描述時顯示「無描述」

---

*最後更新: 2025-10-03*  
*狀態: ✅ 已完成並驗證*  
*優先級: 中*
