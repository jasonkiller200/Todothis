# 📊 報告中心優化升級計畫

## 🎯 需求概述

### 目標
將報告中心優化為兩個獨立頁面：
1. **Todo 任務報告頁面**
2. **Meeting Task 任務報告頁面**

每個頁面提供豐富的統計分析功能。

---

## 📋 現有架構分析

### 當前報告中心功能

#### 1. 現有頁面結構
- **路由**: `/reports` (app.py line 1392-1395)
- **模板**: `templates/reports.html`
- **功能**: 
  - ✅ 顯示本週報告
  - ✅ 顯示本月報告
  - ✅ 僅顯示已歸檔的 Todo 任務 (ArchivedTodo)
  - ❌ 沒有 MeetingTask 報告
  - ❌ 沒有歷史任務查詢
  - ❌ 沒有個人排行功能

#### 2. 現有 API 端點
```python
# 本週報告 (app.py line 1349-1368)
GET /api/reports/weekly
- 查詢本週已歸檔的 Todo
- 按部門和使用者統計
- 權限: admin, executive-manager, manager

# 本月報告 (app.py line 1370-1390)
GET /api/reports/monthly
- 查詢本月已歸檔的 Todo
- 按部門和使用者統計
- 權限: admin, executive-manager, manager
```

#### 3. 資料來源
- **ArchivedTodo**: 已完成並歸檔的任務
- **Todo**: 當前活動中的任務（未使用在報告中）
- **MeetingTask**: 會議任務（未使用在報告中）

#### 4. 統計維度
- ✅ 部門統計
- ✅ 使用者統計
- ✅ 完成率計算
- ❌ 缺少時間趨勢
- ❌ 缺少個人排行
- ❌ 缺少任務類型分析

---

## 🎨 優化設計方案

### 新架構設計

```
報告中心 (/reports)
├── 📝 Todo 任務報告 (/reports/todo)
│   ├── 歷史任務統計
│   ├── 當前未完成任務
│   ├── 個人排行榜
│   ├── 部門統計
│   └── 時間趨勢分析
│
└── 📋 Meeting Task 報告 (/reports/meeting-tasks)
    ├── 會議任務統計
    ├── 追蹤項目分析
    ├── 決議項目分析
    ├── 完成率排行
    └── 逾期任務分析
```

---

## 📊 Todo 任務報告頁面設計

### 1. 頁面結構

#### 頂部導航
```
[Todo 任務報告] [Meeting Task 報告]
```

#### 統計卡片區（4個卡片）
```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│ 歷史總任務  │ 已完成任務  │ 未完成任務  │ 平均完成率  │
│   1,234     │   1,100     │    134      │   89.2%     │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

#### 篩選條件區
```
時間範圍: [本週▼] [本月▼] [本季▼] [本年▼] [自定義▼]
部門: [全部▼] [第一廠▼] [第三廠▼] ...
使用者: [全部▼] [張三▼] [李四▼] ...
狀態: [全部▼] [已完成▼] [未完成▼] [進行中▼]
```

#### 功能分頁
```
[歷史任務] [當前未完成] [個人排行] [部門統計] [趨勢圖表]
```

### 2. 功能詳細設計

#### 📜 歷史任務分頁
**顯示內容**:
- 已歸檔的任務列表 (ArchivedTodo)
- 可按時間、部門、使用者篩選
- 顯示欄位：
  - 任務標題
  - 負責人
  - 指派人
  - 預計完成日期
  - 實際完成日期
  - 狀態
  - 任務天數（完成日期 - 建立日期）

**表格設計**:
```
┌──────┬──────────┬────────┬────────┬──────────┬──────────┬────────┬────────┐
│ 編號 │ 任務標題 │ 負責人 │ 指派人 │ 預計完成 │ 實際完成 │  狀態  │ 天數   │
├──────┼──────────┼────────┼────────┼──────────┼──────────┼────────┼────────┤
│  1   │ 測試任務 │ 張三   │ 李四   │ 01/15    │ 01/14    │ 已完成 │  5天   │
└──────┴──────────┴────────┴────────┴──────────┴──────────┴────────┴────────┘
```

#### 🔴 當前未完成任務分頁
**顯示內容**:
- 當前 Todo 表中未完成的任務
- 突出顯示逾期任務（紅色標記）
- 顯示欄位：
  - 任務標題
  - 負責人
  - 預計完成日期
  - 狀態
  - 逾期天數
  - 操作按鈕

**表格設計**:
```
┌──────┬──────────┬────────┬──────────┬────────┬──────────┬──────────┐
│ 編號 │ 任務標題 │ 負責人 │ 預計完成 │  狀態  │ 逾期天數 │   操作   │
├──────┼──────────┼────────┼──────────┼────────┼──────────┼──────────┤
│  1   │ 🔴測試   │ 張三   │ 01/10    │ 進行中 │  5天     │ [查看]   │
│  2   │ 開發功能 │ 李四   │ 01/20    │ 待開始 │  -       │ [查看]   │
└──────┴──────────┴────────┴──────────┴────────┴──────────┴──────────┘
```

#### 🏆 個人排行榜分頁
**排行維度**:
1. **完成任務數排行** (本週/本月/本年)
2. **完成率排行**
3. **平均完成天數排行** (越短越好)
4. **準時完成率排行** (未逾期完成的比例)

**表格設計**:
```
┌──────┬────────┬────────┬──────────┬──────────┬──────────┬──────────┐
│ 排名 │  姓名  │  部門  │ 完成任務 │ 總任務數 │  完成率  │ 平均天數 │
├──────┼────────┼────────┼──────────┼──────────┼──────────┼──────────┤
│  🥇  │ 張三   │ 第一廠 │   120    │   130    │  92.3%   │  3.5天   │
│  🥈  │ 李四   │ 第三廠 │   98     │   110    │  89.1%   │  4.2天   │
│  🥉  │ 王五   │ 品保部 │   85     │   100    │  85.0%   │  5.1天   │
└──────┴────────┴────────┴──────────┴──────────┴──────────┴──────────┘
```

#### 🏢 部門統計分頁
**統計維度**:
- 各部門任務分布
- 各部門完成率
- 各部門平均完成天數
- 部門任務負荷量

**視覺化**:
- 圓餅圖：任務分布
- 柱狀圖：完成率對比
- 折線圖：月度趨勢

#### 📈 趨勢圖表分頁
**圖表類型**:
1. **月度任務趨勢** - 折線圖
   - X軸：月份
   - Y軸：任務數量
   - 線條：已完成、未完成

2. **週度完成率趨勢** - 折線圖
   - X軸：週次
   - Y軸：完成率

3. **部門任務分布** - 圓餅圖
   - 各部門任務比例

4. **狀態分布** - 環形圖
   - 已完成、進行中、待開始、未完成

---

## 📋 Meeting Task 報告頁面設計

### 1. 頁面結構

#### 統計卡片區
```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│ 總會議任務  │ 已完成任務  │ 進行中任務  │ 逾期任務    │
│    456      │    320      │    100      │     36      │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

#### 篩選條件區
```
時間範圍: [本週▼] [本月▼] [本季▼] [本年▼]
任務類型: [全部▼] [追蹤項目▼] [決議項目▼]
狀態: [全部▼] [已完成▼] [進行中▼] [未指派▼]
負責人: [全部▼] [張三▼] [李四▼] ...
```

#### 功能分頁
```
[會議任務列表] [完成率分析] [逾期任務] [個人排行] [會議效率]
```

### 2. 功能詳細設計

#### 📋 會議任務列表分頁
**顯示內容**:
- 所有 MeetingTask 列表
- 關聯的會議資訊
- 任務狀態和進度

**表格設計**:
```
┌──────┬──────────┬────────┬──────────┬──────────┬──────────┬────────┐
│ 編號 │ 會議主題 │ 任務描述│ 負責人  │ 預計完成 │  狀態    │ 類型   │
├──────┼──────────┼────────┼──────────┼──────────┼──────────┼────────┤
│  1   │ 月會     │ 改善方案│ 張三    │ 01/25    │ 進行中   │ 追蹤   │
│  2   │ 檢討會   │ 提交報告│ 李四    │ 01/20    │ 已完成   │ 決議   │
└──────┴──────────┴────────┴──────────┴──────────┴──────────┴────────┘
```

#### 📊 完成率分析分頁
**分析維度**:
1. **整體完成率**
2. **按任務類型分析** (追蹤 vs 決議)
3. **按負責人分析**
4. **按會議分析**

**圖表**:
- 完成率儀表板
- 任務類型對比圖
- 負責人完成率柱狀圖

#### 🔴 逾期任務分頁
**顯示內容**:
- 所有逾期的會議任務
- 逾期天數
- 未完成原因（如果有）

**表格設計**:
```
┌──────┬──────────┬────────┬────────┬──────────┬──────────┬──────────┐
│ 編號 │ 會議日期 │ 任務   │ 負責人 │ 預計完成 │ 逾期天數 │ 未完成原因│
├──────┼──────────┼────────┼────────┼──────────┼──────────┼──────────┤
│  1   │ 12/15    │ 測試   │ 張三   │ 01/10    │  10天    │ 等待回覆  │
└──────┴──────────┴────────┴────────┴──────────┴──────────┴──────────┘
```

#### 🏆 個人排行榜分頁
**排行維度**:
1. **完成會議任務數排行**
2. **會議任務完成率排行**
3. **準時完成率排行**

#### 📈 會議效率分析分頁
**分析指標**:
1. **會議產生任務數**
2. **任務完成週期**
3. **會議決議執行率**
4. **追蹤項目閉環率**

---

## 🔧 技術實施方案

### 1. 資料庫查詢優化

#### Todo 任務查詢
```python
# 歷史任務（已歸檔）
def get_archived_todos(start_date=None, end_date=None, user_id=None, department=None, status=None):
    query = ArchivedTodo.query
    
    if start_date:
        query = query.filter(ArchivedTodo.archived_at >= start_date)
    if end_date:
        query = query.filter(ArchivedTodo.archived_at <= end_date)
    if user_id:
        query = query.filter(ArchivedTodo.user_id == user_id)
    if status:
        query = query.filter(ArchivedTodo.status == status)
    
    return query.all()

# 當前未完成任務
def get_active_todos(user_id=None, department=None, status=None):
    query = Todo.query.filter(Todo.status != TodoStatus.COMPLETED.value)
    
    if user_id:
        query = query.filter(Todo.user_id == user_id)
    if status:
        query = query.filter(Todo.status == status)
    
    return query.all()

# 個人統計
def get_user_statistics(user_id, start_date, end_date):
    completed = ArchivedTodo.query.filter(
        ArchivedTodo.user_id == user_id,
        ArchivedTodo.archived_at >= start_date,
        ArchivedTodo.archived_at <= end_date,
        ArchivedTodo.status == TodoStatus.COMPLETED.value
    ).count()
    
    total = ArchivedTodo.query.filter(
        ArchivedTodo.user_id == user_id,
        ArchivedTodo.archived_at >= start_date,
        ArchivedTodo.archived_at <= end_date
    ).count()
    
    return {
        'completed': completed,
        'total': total,
        'completion_rate': (completed / total * 100) if total > 0 else 0
    }
```

#### MeetingTask 查詢
```python
# 會議任務統計
def get_meeting_task_statistics(start_date=None, end_date=None, task_type=None, status=None):
    query = MeetingTask.query
    
    if start_date:
        query = query.join(Meeting).filter(Meeting.meeting_date >= start_date)
    if end_date:
        query = query.join(Meeting).filter(Meeting.meeting_date <= end_date)
    if task_type:
        query = query.filter(MeetingTask.task_type == task_type)
    if status:
        query = query.filter(MeetingTask.status == status)
    
    return query.all()

# 逾期會議任務
def get_overdue_meeting_tasks():
    taiwan_tz = timezone('Asia/Taipei')
    today = datetime.now(taiwan_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc = today.astimezone(utc)
    
    return MeetingTask.query.filter(
        MeetingTask.expected_completion_date < today_utc,
        MeetingTask.status != MeetingTaskStatus.COMPLETED.value
    ).all()
```

### 2. 新增 API 端點

#### Todo 報告 API
```python
# GET /api/reports/todo/historical
# 歷史任務統計
@app.route('/api/reports/todo/historical')
@login_required
def get_todo_historical_report():
    # 參數: start_date, end_date, user_id, department, status
    pass

# GET /api/reports/todo/current
# 當前未完成任務
@app.route('/api/reports/todo/current')
@login_required
def get_todo_current_report():
    # 參數: user_id, department, status
    pass

# GET /api/reports/todo/ranking
# 個人排行榜
@app.route('/api/reports/todo/ranking')
@login_required
def get_todo_ranking():
    # 參數: period (week/month/year), metric (completed/rate/days)
    pass

# GET /api/reports/todo/department-stats
# 部門統計
@app.route('/api/reports/todo/department-stats')
@login_required
def get_todo_department_stats():
    # 參數: period
    pass

# GET /api/reports/todo/trends
# 趨勢數據
@app.route('/api/reports/todo/trends')
@login_required
def get_todo_trends():
    # 參數: period, type (monthly/weekly)
    pass
```

#### MeetingTask 報告 API
```python
# GET /api/reports/meeting-tasks/list
# 會議任務列表
@app.route('/api/reports/meeting-tasks/list')
@login_required
def get_meeting_tasks_list():
    # 參數: start_date, end_date, task_type, status, user_id
    pass

# GET /api/reports/meeting-tasks/completion
# 完成率分析
@app.route('/api/reports/meeting-tasks/completion')
@login_required
def get_meeting_tasks_completion():
    # 參數: period, group_by (type/user/meeting)
    pass

# GET /api/reports/meeting-tasks/overdue
# 逾期任務
@app.route('/api/reports/meeting-tasks/overdue')
@login_required
def get_meeting_tasks_overdue():
    pass

# GET /api/reports/meeting-tasks/ranking
# 個人排行
@app.route('/api/reports/meeting-tasks/ranking')
@login_required
def get_meeting_tasks_ranking():
    # 參數: period, metric
    pass

# GET /api/reports/meeting-tasks/efficiency
# 會議效率分析
@app.route('/api/reports/meeting-tasks/efficiency')
@login_required
def get_meeting_tasks_efficiency():
    pass
```

### 3. 前端頁面結構

#### 主報告入口頁面
```html
<!-- templates/reports.html -->
<div class="reports-container">
    <h1>📊 報告中心</h1>
    
    <div class="report-cards">
        <div class="report-card" onclick="location.href='/reports/todo'">
            <div class="card-icon">📝</div>
            <h2>Todo 任務報告</h2>
            <p>查看歷史任務、當前任務、個人排行等統計</p>
        </div>
        
        <div class="report-card" onclick="location.href='/reports/meeting-tasks'">
            <div class="card-icon">📋</div>
            <h2>Meeting Task 報告</h2>
            <p>查看會議任務、完成率、逾期分析等統計</p>
        </div>
    </div>
</div>
```

#### Todo 報告頁面
```html
<!-- templates/reports_todo.html -->
<div class="todo-reports">
    <!-- 頂部導航 -->
    <div class="tab-navigation">
        <a href="/reports/todo" class="active">Todo 任務報告</a>
        <a href="/reports/meeting-tasks">Meeting Task 報告</a>
    </div>
    
    <!-- 統計卡片 -->
    <div class="stats-cards" id="todo-stats"></div>
    
    <!-- 篩選條件 -->
    <div class="filters" id="todo-filters"></div>
    
    <!-- 功能分頁 -->
    <div class="function-tabs">
        <button class="tab active" data-tab="historical">歷史任務</button>
        <button class="tab" data-tab="current">當前未完成</button>
        <button class="tab" data-tab="ranking">個人排行</button>
        <button class="tab" data-tab="department">部門統計</button>
        <button class="tab" data-tab="trends">趨勢圖表</button>
    </div>
    
    <!-- 內容區域 -->
    <div class="tab-content" id="content-area"></div>
</div>
```

#### MeetingTask 報告頁面
```html
<!-- templates/reports_meeting_tasks.html -->
<div class="meeting-task-reports">
    <!-- 類似結構 -->
</div>
```

### 4. 前端 JavaScript

#### 使用圖表庫
推薦使用 **Chart.js** 或 **ECharts**：

```javascript
// 載入 Chart.js
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

// 繪製趨勢圖
function renderTrendChart(data) {
    const ctx = document.getElementById('trendChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: '已完成',
                data: data.completed,
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1
            }, {
                label: '未完成',
                data: data.uncompleted,
                borderColor: 'rgb(255, 99, 132)',
                tension: 0.1
            }]
        }
    });
}
```

---

## 📅 實施計畫

### Phase 1: 基礎架構 (2-3 天)
- ✅ 設計資料庫查詢函數
- ✅ 建立新的 API 端點
- ✅ 建立頁面路由
- ✅ 設計頁面布局

### Phase 2: Todo 報告頁面 (3-4 天)
- ✅ 實現歷史任務查詢
- ✅ 實現當前未完成任務
- ✅ 實現個人排行榜
- ✅ 實現部門統計
- ✅ 實現趨勢圖表

### Phase 3: MeetingTask 報告頁面 (3-4 天)
- ✅ 實現會議任務列表
- ✅ 實現完成率分析
- ✅ 實現逾期任務
- ✅ 實現個人排行
- ✅ 實現會議效率分析

### Phase 4: 優化與測試 (2-3 天)
- ✅ 性能優化
- ✅ UI/UX 優化
- ✅ 測試所有功能
- ✅ 修正 Bug

**總預估時間**: 10-14 天

---

## 🎯 預期效益

### 對管理層
- 📊 全面掌握任務執行狀況
- 🏆 識別高效能員工
- 📈 發現瓶頸和問題
- 💡 數據驅動決策

### 對員工
- 📝 清楚了解自己的任務完成情況
- 🎯 明確改進方向
- 🏅 激勵機制（排行榜）

### 對系統
- 🔍 更好的數據可視化
- 📊 豐富的統計維度
- 🚀 提升用戶體驗

---

## 🎨 UI/UX 設計建議

### 色彩方案
- 主色調：藍色系（專業、可信賴）
- 強調色：橙色（重要數據）
- 警告色：紅色（逾期任務）
- 成功色：綠色（已完成）

### 交互設計
- 響應式設計（支援桌面和平板）
- 流暢的頁面切換動畫
- 即時數據更新（無需刷新）
- 可導出 Excel/PDF

### 數據可視化
- 使用圖表呈現趨勢
- 使用顏色編碼狀態
- 使用圖標增強識別
- 使用進度條顯示完成率

---

## ⚠️ 注意事項

### 性能考量
1. **資料量**: 如果歷史數據很大，需要分頁或限制查詢範圍
2. **查詢優化**: 添加適當的資料庫索引
3. **快取機制**: 對不常變動的統計數據進行快取

### 權限控制
1. **一般使用者**: 只能查看自己的報告
2. **課長/副課長**: 可查看自己部門的報告
3. **經理/廠長**: 可查看管轄範圍的報告
4. **協理/管理員**: 可查看所有報告

### 數據準確性
1. 確保時區正確（台北時區）
2. 處理邊界情況（無數據、異常值）
3. 定期驗證統計數據

---

## 🎉 總結

這個優化方案將大幅提升報告中心的功能性和實用性：

✅ **功能豐富**: 從簡單的週月報告擴展到多維度分析  
✅ **數據全面**: 涵蓋 Todo 和 MeetingTask 兩大任務類型  
✅ **使用者友善**: 清晰的導航和豐富的視覺化  
✅ **管理價值**: 提供決策支援的數據洞察  

**建議立即開始實施！** 🚀
