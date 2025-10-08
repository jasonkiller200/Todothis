# 📊 報告中心 API 端點文檔

## 🎯 概述

報告中心提供了豐富的 API 端點，用於查詢 Todo 任務和 Meeting Task 的各種統計數據。

---

## 🔐 權限說明

### 使用者權限級別
- **一般使用者**: 只能查看自己的數據
- **課長/副課長**: 可查看自己的數據（未來可擴展為部門數據）
- **經理/廠長**: 可查看管轄範圍的數據
- **管理員/協理**: 可查看所有數據

### API 權限要求
- 所有 API 都需要登入（`@login_required`）
- 部分 API 有額外的權限檢查

---

## 📝 Todo 任務報告 API

### 1. 獲取 Todo 概覽統計

**端點**: `GET /api/reports/todo/overview`

**描述**: 獲取本週、本月、本年的 Todo 任務統計概覽。

**權限**: 需要登入

**參數**: 無

**返回範例**:
```json
{
  "week": {
    "total": 15,
    "completed": 12,
    "completion_rate": 80.0
  },
  "month": {
    "total": 65,
    "completed": 52,
    "completion_rate": 80.0
  },
  "year": {
    "total": 250,
    "completed": 200,
    "completion_rate": 80.0
  },
  "current": {
    "total": 10,
    "in_progress": 5,
    "pending": 3,
    "overdue": 2
  }
}
```

---

### 2. 獲取歷史任務列表

**端點**: `GET /api/reports/todo/historical`

**描述**: 獲取已歸檔的歷史任務列表。

**權限**: 需要登入，管理層可查看所有使用者

**查詢參數**:
- `period` (string): 時間範圍
  - `week`: 本週
  - `month`: 本月 (預設)
  - `quarter`: 本季
  - `year`: 本年
  - `custom`: 自訂（預設3個月）
- `user_id` (int): 使用者 ID（可選）
- `department` (string): 部門（可選）
- `status` (string): 狀態（可選）
  - `completed`
  - `uncompleted`
- `page` (int): 頁碼（預設 1）
- `per_page` (int): 每頁筆數（預設 50）

**返回範例**:
```json
{
  "total": 100,
  "page": 1,
  "per_page": 50,
  "total_pages": 2,
  "tasks": [
    {
      "id": 123,
      "title": "完成報告",
      "description": "撰寫月度報告",
      "status": "completed",
      "user_name": "張三",
      "user_id": 1,
      "due_date": "2025-10-01 17:00",
      "archived_at": "2025-10-01 16:30",
      "is_archived": true
    }
  ],
  "stats": {
    "completed": 85,
    "uncompleted": 15
  }
}
```

---

### 3. 獲取當前未完成任務

**端點**: `GET /api/reports/todo/current`

**描述**: 獲取當前進行中的任務列表。

**權限**: 需要登入，管理層可查看所有使用者

**查詢參數**:
- `user_id` (int): 使用者 ID（可選）
- `status` (string): 狀態（可選）
  - `pending`: 待開始
  - `in-progress`: 進行中
  - `uncompleted`: 未完成
- `overdue_only` (boolean): 只顯示逾期任務（預設 false）

**返回範例**:
```json
{
  "total": 10,
  "tasks": [
    {
      "id": 456,
      "title": "測試功能",
      "description": "測試新功能",
      "status": "in-progress",
      "user_name": "李四",
      "user_id": 2,
      "due_date": "2025-10-05 17:00",
      "is_overdue": false,
      "is_archived": false
    }
  ],
  "stats": {
    "in_progress": 5,
    "pending": 3,
    "overdue": 2
  }
}
```

---

### 4. 獲取個人排行榜

**端點**: `GET /api/reports/todo/ranking`

**描述**: 獲取使用者任務完成排行榜。

**權限**: 需要管理層權限

**查詢參數**:
- `period` (string): 時間範圍
  - `week`: 本週
  - `month`: 本月 (預設)
  - `year`: 本年
- `metric` (string): 排行指標
  - `completed`: 完成任務數 (預設)
  - `completion_rate`: 完成率
  - `avg_days`: 平均完成天數
- `limit` (int): 返回前幾名（預設 10）

**返回範例**:
```json
{
  "period": "month",
  "metric": "completed",
  "ranking": [
    {
      "user_id": 1,
      "user_name": "張三",
      "department": "研發部",
      "unit": "第一廠",
      "role": "工程師",
      "total_tasks": 50,
      "completed_tasks": 45,
      "completion_rate": 90.0,
      "avg_days": 3.5
    }
  ]
}
```

---

## 📋 Meeting Task 報告 API

### 5. 獲取會議任務概覽

**端點**: `GET /api/reports/meeting-tasks/overview`

**描述**: 獲取會議任務的統計概覽。

**權限**: 需要登入

**參數**: 無

**返回範例**:
```json
{
  "week": {
    "total": 8,
    "completed": 5,
    "completion_rate": 62.5,
    "overdue": 1
  },
  "month": {
    "total": 35,
    "completed": 25,
    "completion_rate": 71.4,
    "overdue": 3
  },
  "year": {
    "total": 120,
    "completed": 90,
    "completion_rate": 75.0,
    "overdue": 10
  },
  "all": {
    "total": 150,
    "completed": 100,
    "in_progress": 30,
    "unassigned": 10,
    "overdue": 15
  }
}
```

---

### 6. 獲取會議任務列表

**端點**: `GET /api/reports/meeting-tasks/list`

**描述**: 獲取會議任務詳細列表。

**權限**: 需要登入，管理層可查看所有使用者

**查詢參數**:
- `period` (string): 時間範圍（week/month/year，預設 month）
- `task_type` (string): 任務類型
  - `tracking`: 追蹤項目
  - `resolution`: 決議項目
- `status` (string): 任務狀態
- `user_id` (int): 負責人 ID（可選）
- `page` (int): 頁碼（預設 1）
- `per_page` (int): 每頁筆數（預設 50）

**返回範例**:
```json
{
  "total": 35,
  "page": 1,
  "per_page": 50,
  "total_pages": 1,
  "tasks": [
    {
      "id": 789,
      "meeting_id": 123,
      "meeting_subject": "月度檢討會議",
      "meeting_date": "2025-09-15",
      "task_type": "tracking",
      "task_description": "追蹤上月遺留問題",
      "status": "completed",
      "assigned_to_name": "王五",
      "assigned_by_name": "張三",
      "expected_completion_date": "2025-10-01",
      "actual_completion_date": "2025-09-30",
      "is_overdue": false,
      "uncompleted_reason": null
    }
  ],
  "stats": {
    "completed": 25,
    "in_progress": 8,
    "unassigned": 2,
    "overdue": 3,
    "completion_rate": 71.4
  }
}
```

---

### 7. 獲取逾期會議任務

**端點**: `GET /api/reports/meeting-tasks/overdue`

**描述**: 獲取所有逾期的會議任務。

**權限**: 需要登入，管理層可查看所有使用者

**參數**: 無

**返回範例**:
```json
{
  "total": 5,
  "tasks": [
    {
      "id": 999,
      "meeting_id": 150,
      "meeting_subject": "緊急會議",
      "meeting_date": "2025-09-01",
      "task_description": "提交改善方案",
      "task_type": "resolution",
      "status": "in_progress_todo",
      "assigned_to_name": "趙六",
      "assigned_by_name": "錢七",
      "expected_completion_date": "2025-09-20",
      "overdue_days": 12,
      "uncompleted_reason": "等待供應商回覆"
    }
  ]
}
```

---

## 🔧 錯誤處理

所有 API 在發生錯誤時會返回以下格式：

```json
{
  "error": "錯誤訊息描述"
}
```

**常見 HTTP 狀態碼**:
- `200`: 成功
- `401`: 未授權（未登入）
- `403`: 禁止訪問（權限不足）
- `404`: 找不到資源
- `500`: 伺服器內部錯誤

---

## 📝 使用範例

### JavaScript Fetch 範例

```javascript
// 獲取 Todo 概覽
async function getTodoOverview() {
    const response = await fetch('/api/reports/todo/overview');
    const data = await response.json();
    console.log(data);
}

// 獲取歷史任務（本月）
async function getHistoricalTasks() {
    const response = await fetch('/api/reports/todo/historical?period=month&page=1');
    const data = await response.json();
    console.log(data.tasks);
}

// 獲取排行榜（本月完成數）
async function getRanking() {
    const response = await fetch('/api/reports/todo/ranking?period=month&metric=completed&limit=10');
    const data = await response.json();
    console.log(data.ranking);
}

// 獲取逾期會議任務
async function getOverdueMeetingTasks() {
    const response = await fetch('/api/reports/meeting-tasks/overdue');
    const data = await response.json();
    console.log(data.tasks);
}
```

### Python 範例

```python
import requests

# 假設已登入並有 session
session = requests.Session()

# 獲取 Todo 概覽
response = session.get('http://192.168.6.119:5001/api/reports/todo/overview')
data = response.json()
print(data)

# 獲取當前任務（只顯示逾期）
response = session.get(
    'http://192.168.6.119:5001/api/reports/todo/current',
    params={'overdue_only': 'true'}
)
data = response.json()
print(data['tasks'])
```

---

## 🎯 後續擴展計畫

### 計畫中的 API（Phase 1 剩餘）
- `/api/reports/todo/department-stats` - 部門統計
- `/api/reports/todo/trends` - 趨勢數據
- `/api/reports/meeting-tasks/ranking` - 會議任務排行
- `/api/reports/meeting-tasks/efficiency` - 會議效率分析

### 未來可能的擴展
- 導出功能（Excel/PDF）
- 即時統計（WebSocket）
- 自定義時間範圍查詢
- 更多統計維度

---

*最後更新: 2025-10-03*  
*版本: 1.0*  
*狀態: Phase 1 完成 80%*
