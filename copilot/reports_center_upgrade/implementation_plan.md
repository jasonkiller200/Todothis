# 報告中心升級實施計畫

## 專案概述
優化報告中心功能，分離 Todo 任務和 Meeting Task 報告，增加統計分析、歷史查詢、排行榜等功能。

## 已完成的工作

### 1. 修復程式錯誤
- ✅ 修復 `/api/meeting_tasks_list` endpoint 重複定義問題
  - 將第二個 `get_meeting_tasks_list()` 函數重命名為 `get_meeting_tasks_list_page()`
  
- ✅ 修復日期時間比較錯誤
  - 問題：`can't compare offset-naive and offset-aware datetimes`
  - 解決方案：在 `_get_todo_statistics()` 函數中統一處理 naive 和 aware datetime
  - 位置：app.py 第 1354-1368 行

### 2. 創建新模板
- ✅ 創建 `templates/reports_meeting_tasks.html`
  - 基礎結構與 reports_todo.html 相似
  - 包含概覽統計、任務列表、逾期任務三個分頁
  - 統計卡片顯示總任務數、已完成、進行中、逾期任務

### 3. 優化 Todo 報告功能

#### 3.1 增加時間範圍篩選選項
✅ 在 `templates/reports_todo.html` 中增加：
- 上個月 (last_month)
- 上一季 (last_quarter)
- 上半年 (first_half)
- 下半年 (second_half)

✅ 在 `app.py` 的 `get_todo_historical()` API 中實現相應邏輯

#### 3.2 增加負責人篩選
✅ 在篩選器中增加負責人下拉選單
- 自動從任務數據中提取所有負責人
- 支持按負責人篩選任務

#### 3.3 增加表格排序功能
✅ 實現可點擊排序的表頭
- 預計完成日期排序
- 負責人排序
- 使用 ⇅ 符號標示可排序欄位
- 支持升序/降序切換

#### 3.4 任務內容顯示優化
✅ 已在前一次更新中完成：
- 長文本使用 tooltip 顯示完整內容
- 預計完成日期只顯示日期不顯示時間
- 任務描述支持多行顯示

## 待完成的工作

### 1. 逾期任務重設預計完成日期功能

#### 1.1 前端修改
- [ ] 在 Todo 任務管理介面增加「重設預計完成日期」欄位
  - 位置：變更狀態為「未完成」時
  - 需要同時填寫未完成原因和新的預計完成日期

#### 1.2 後端 API 修改
- [ ] 修改更新任務狀態的 API
  - 支持同時更新狀態、未完成原因和新預計完成日期
  - 將日期變更記錄到履歷 (history_log)

#### 1.3 履歷記錄格式
```json
{
  "event_type": "reschedule_due_date",
  "timestamp": "2025-10-03T12:00:00Z",
  "actor": {"name": "使用者名稱", "user_key": "user_key"},
  "details": {
    "old_due_date": "2025-10-01",
    "new_due_date": "2025-10-10",
    "reason": "未完成原因說明"
  }
}
```

#### 1.4 郵件通知優化
✅ 已完成 - 在 `scheduler.py` 的 `check_overdue_tasks()` 函數中增加提示文字：
```python
body_parts.append("<b>💡 小提示：</b>")
body_parts.append("如任務無法在原定期限完成，您可以在系統中將任務狀態設為「未完成」，")
body_parts.append("填寫未完成原因後，同時重新設定新的預計完成日期。")
```

### 2. 報告中心功能完善

#### 2.1 Todo 任務報告
- [x] 當前未完成任務列表
  - 顯示所有未完成的任務
  - 標示逾期任務
- [x] 歷史任務列表
  - 已歸檔任務查詢
  - 多種時間範圍篩選
- [x] 個人排行榜
  - 按完成任務數排序
  - 顯示完成率
- [ ] 任務統計圖表
  - 完成率趨勢圖
  - 任務狀態分布圖

#### 2.2 Meeting Task 報告 ✅ 已完成
- [x] 基本架構建立
- [x] 當前未完成會議任務（概覽統計）
- [x] 歷史會議任務查詢（任務列表功能）
- [x] 會議任務統計分析（多時間維度統計）
- [x] 逾期任務追蹤（逾期任務列表）
- [x] 個人排行榜（完成數、完成率）
- [x] 決議事項追蹤（包含在任務列表中）

**最新更新 (2025-10-03)**：
- ✅ 完成前端介面優化
  - 新增篩選器（時間範圍、任務類型、狀態、負責人）
  - 新增個人排行榜分頁
  - 優化表格顯示樣式
  - 完善逾期任務顯示（逾期天數、高亮顯示）
  
- ✅ 完成後端 API 實作
  - 新增 `/api/reports/meeting-tasks/ranking` 排行榜 API
  - 優化逾期任務 API（增加管制者欄位）
  - 支援多維度篩選功能
  - 權限控制（管理員可看全部，一般使用者只看自己）
  
- ✅ 功能特色
  - 📊 多時間維度統計（本週、本月、本年、全部）
  - 📋 完整任務列表（支援篩選和排序）
  - 🔴 逾期任務監控（顯示逾期天數）
  - 🏆 個人排行榜（完成數排行和完成率排行）
  - 🎨 美觀的介面設計（與 Todo 報告風格一致）

### 3. 資料備份
- [ ] 備份預計修改的檔案：
  - app.py (主要修改任務更新 API)
  - scheduler.py (已修改，需確認備份)
  - templates/index.html (可能需要修改任務編輯表單)
  - templates/reports_todo.html (已修改)

## 技術實現細節

### API 端點總覽

#### Todo 任務報告 API
- `GET /api/reports/todo/overview` - 概覽統計
- `GET /api/reports/todo/historical` - 歷史任務列表
- `GET /api/reports/todo/current` - 當前未完成任務
- `GET /api/reports/todo/ranking` - 個人排行榜

#### Meeting Task 報告 API
- `GET /api/reports/meeting-tasks/overview` - 概覽統計
- `GET /api/reports/meeting-tasks/list` - 任務列表
- `GET /api/reports/meeting-tasks/overdue` - 逾期任務

### 資料庫結構
當前使用的表：
- `Todo` - Todo 任務表
- `ArchivedTodo` - 已歸檔的 Todo 任務
- `MeetingTask` - 會議任務表
- `User` - 使用者表

每個任務都有 `history_log` 欄位（JSON 格式）用於記錄所有變更歷史。

## 測試計畫

### 功能測試
1. [ ] 測試時間範圍篩選（上個月、上一季等）
2. [ ] 測試排序功能（預計完成日期、負責人）
3. [ ] 測試負責人篩選
4. [ ] 測試任務內容 tooltip 顯示
5. [ ] 測試逾期任務重設日期功能
6. [ ] 測試履歷記錄是否正確

### API 測試
1. [ ] 測試 `/api/reports/todo/overview` 返回正確統計
2. [ ] 測試 `/api/reports/todo/historical` 各種篩選條件
3. [ ] 測試 `/api/reports/todo/current` 未完成任務列表
4. [ ] 測試 `/api/reports/todo/ranking` 排行榜

### 郵件測試
1. [ ] 測試逾期任務郵件是否包含重設日期提示
2. [ ] 驗證郵件格式和內容

## 部署注意事項

1. **資料庫遷移**
   - 如果修改了資料庫結構，需要運行 migration
   - `flask db migrate -m "description"`
   - `flask db upgrade`

2. **環境變數檢查**
   - 確認 `.env` 檔案中的配置正確
   - 郵件服務配置
   - 資料庫連接配置

3. **服務重啟**
   - 使用 `run_waitress.ps1` 重啟服務
   - 檢查日誌確認無錯誤

## 當前狀態
- ✅ 應用已成功啟動運行
- ✅ 基本報告中心架構完成
- ✅ Todo 報告功能大部分完成
- ✅ Meeting Task 報告功能已完成 🎉
- ⏳ 逾期任務重設日期功能已完成（待測試）
- ⏳ 資料視覺化圖表待實現

## 下一步行動
1. ✅ 完成逾期任務重設預計完成日期功能
2. ✅ 完善 Meeting Task 報告功能
3. ⏳ 測試所有新增功能
4. ⏳ 增加資料視覺化圖表（Todo 任務趨勢圖）

---
最後更新：2025-10-03 15:15
