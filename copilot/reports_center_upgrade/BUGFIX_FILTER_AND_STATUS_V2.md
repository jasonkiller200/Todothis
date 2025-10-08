# 報告中心篩選器與狀態顯示修正 V2

## 問題描述

### 1. 路由衝突問題（已修復）
- **問題**: `get_meeting_tasks_list_page()` 函數名稱與另一個endpoint衝突
- **狀態**: ✅ 已修復
- **解決方案**: 將函數名改為 `get_meeting_tasks_list()`

### 2. 當前未完成任務頁面 - 狀態篩選器問題
- **問題**: 當前未完成任務頁面顯示狀態篩選器，但該頁面本身就是只顯示未完成項目
- **狀態**: ⏳ 待修復
- **解決方案**: 移除當前未完成任務頁面的狀態篩選器

### 3. 歷史任務頁面 - 狀態篩選器問題
- **問題**: 歷史任務頁面顯示狀態篩選器，但歷史記錄都是已歸檔（完成/未完成）的項目
- **狀態**: ⏳ 待修復
- **解決方案**: 移除歷史任務頁面的狀態篩選器

### 4. 人員篩選器邏輯問題
- **問題**: 
  - 歷史任務頁面：人員篩選應該依照時間篩選結果列出人員清單，然後再點擊人員後篩選
  - 當前未完成任務頁面：人員篩選功能不正常，選擇不同負責人後還是顯示全部的人
- **狀態**: ⏳ 待修復
- **解決方案**: 
  - 歷史任務：根據選定時間範圍內的任務動態生成人員清單
  - 當前未完成：根據當前未完成任務動態生成人員清單，並正確套用人員篩選

## 實作計畫

### 階段1: 修改前端 JavaScript（reports_todo.html）

#### 1.1 調整篩選器顯示邏輯
```javascript
// 在 switchTab() 函數中根據當前分頁決定顯示哪些篩選器
function switchTab(tabName) {
    currentTab = tabName;
    
    // 切換分頁顯示
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');
    
    // 根據分頁調整篩選器顯示
    const filters = document.getElementById('filters');
    const statusFilter = document.getElementById('filterStatus').parentElement;
    
    if (tabName === 'historical') {
        // 歷史任務：顯示篩選器，但隱藏狀態篩選
        filters.style.display = 'flex';
        statusFilter.style.display = 'none';
    } else if (tabName === 'current') {
        // 當前未完成：顯示篩選器，但隱藏狀態篩選
        filters.style.display = 'flex';
        statusFilter.style.display = 'none';
    } else {
        // 其他分頁：隱藏篩選器
        filters.style.display = 'none';
    }
    
    // 載入對應數據
    loadTabData(tabName);
}
```

#### 1.2 動態載入人員清單
```javascript
// 根據當前分頁和篩選條件動態載入人員清單
async function updateUserFilter(tabName) {
    const filterUser = document.getElementById('filterUser');
    
    try {
        let endpoint = '';
        let params = new URLSearchParams();
        
        if (tabName === 'historical') {
            endpoint = '/api/reports/todo/historical';
            params.append('period', currentPeriod);
            params.append('per_page', '1000'); // 獲取所有記錄以提取人員列表
        } else if (tabName === 'current') {
            endpoint = '/api/reports/todo/current';
        }
        
        const response = await fetch(`${endpoint}?${params}`);
        const data = await response.json();
        
        // 提取唯一的人員列表
        const users = new Map();
        data.tasks.forEach(task => {
            if (task.user_id && task.user_name) {
                users.set(task.user_id, task.user_name);
            }
        });
        
        // 更新下拉選單
        filterUser.innerHTML = '<option value="">全部</option>';
        users.forEach((name, id) => {
            filterUser.innerHTML += `<option value="${id}">${name}</option>`;
        });
        
    } catch (error) {
        console.error('Error updating user filter:', error);
    }
}
```

#### 1.3 修改 applyFilters() 函數
```javascript
function applyFilters() {
    const period = document.getElementById('filterPeriod').value;
    const userId = document.getElementById('filterUser').value;
    
    currentPeriod = period;
    currentPage = 1;
    
    // 根據當前分頁載入數據
    if (currentTab === 'historical') {
        loadHistoricalData(1, userId);
    } else if (currentTab === 'current') {
        loadCurrentData(userId);
    }
}
```

### 階段2: 修改後端 API（app.py）

#### 2.1 修改歷史任務API - 支援人員篩選
在 `get_todo_historical()` 函數中已經支援 `user_id` 參數，不需要修改。

#### 2.2 修改當前未完成任務API - 支援人員篩選
在 `get_todo_current()` 函數中已經支援 `user_id` 參數，不需要修改。

#### 2.3 確認篩選邏輯正確
檢查 `_get_todo_statistics()` 函數確保人員篩選正確執行。

### 階段3: 測試計畫

1. **測試路由衝突修復**
   - 啟動應用，確認無 AssertionError
   
2. **測試當前未完成任務頁面**
   - 切換到「當前未完成」分頁
   - 確認沒有狀態篩選器顯示
   - 確認有人員篩選器
   - 測試人員篩選功能：選擇不同人員，確認只顯示該人員的任務

3. **測試歷史任務頁面**
   - 切換到「歷史任務」分頁
   - 確認沒有狀態篩選器顯示
   - 選擇不同時間範圍（本月、上個月、本季等）
   - 確認人員篩選器只顯示該時間範圍內有任務的人員
   - 測試人員篩選功能：選擇不同人員，確認只顯示該人員的任務

4. **測試概覽統計頁面**
   - 切換到「概覽統計」分頁
   - 確認篩選器區塊隱藏

5. **測試個人排行頁面**
   - 切換到「個人排行」分頁
   - 確認篩選器區塊隱藏

## 文件修改清單

- ✅ `app.py` - 修正路由衝突（第 3426 行）
- ⏳ `templates/reports_todo.html` - 調整篩選器顯示邏輯和人員篩選功能

## 備註

- 狀態篩選在歷史任務和當前未完成任務頁面確實不需要，因為：
  - 歷史任務：都是已歸檔的任務（已完成或未完成）
  - 當前未完成：定義就是排除已完成和未完成狀態的任務
  
- 人員篩選需要動態載入，避免顯示不相關的人員

## 日期
2025-10-03
