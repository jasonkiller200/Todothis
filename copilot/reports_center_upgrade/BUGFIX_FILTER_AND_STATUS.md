# Bug 修復計劃：報告中心篩選功能問題

## 📋 問題描述

### 問題 1：負責人篩選功能無效
**位置：** Todo 任務報告 - 當前未完成任務頁籤

**現象：**
- 選擇不同負責人進行篩選時，仍然顯示全部人員的任務
- `applyFilters()` 函數僅對歷史記錄頁籤有效，未對當前未完成任務應用篩選

**原因分析：**
1. `applyFilters()` 函數只處理歷史紀錄：
```javascript
function applyFilters() {
    if (currentTab === 'historical') {
        loadHistoricalData(1);
    }
}
```

2. 當前未完成任務頁籤沒有調用 `filterTableRows()` 進行客戶端篩選

**影響範圍：**
- templates/reports_todo.html - 當前未完成任務頁籤

---

### 問題 2：歷史紀錄顯示狀態篩選
**位置：** Todo 任務報告 - 歷史任務頁籤

**現象：**
- 歷史紀錄中仍顯示「狀態」篩選下拉選單
- 但歷史記錄都是已完成項目，不需要狀態篩選

**原因分析：**
篩選區塊對所有頁籤都顯示相同的篩選選項，未依據不同頁籤調整

**影響範圍：**
- templates/reports_todo.html - 篩選區塊

---

## 🎯 修復目標

### 目標 1：修復負責人篩選功能
✅ 在當前未完成任務頁籤中，選擇負責人後能正確篩選顯示該負責人的任務

### 目標 2：隱藏歷史紀錄的狀態篩選
✅ 歷史任務頁籤不顯示狀態篩選選項（因為都是已完成）

---

## 🔧 修復方案

### 方案 1：增強 applyFilters() 函數

**修改位置：** templates/reports_todo.html - applyFilters() 函數

**修改前：**
```javascript
function applyFilters() {
    if (currentTab === 'historical') {
        loadHistoricalData(1);
    }
}
```

**修改後：**
```javascript
function applyFilters() {
    if (currentTab === 'historical') {
        loadHistoricalData(1);
    } else if (currentTab === 'current') {
        // 對當前未完成任務應用客戶端篩選
        filterTableRows();
    }
}
```

---

### 方案 2：根據頁籤動態顯示/隱藏篩選選項

**修改位置：** templates/reports_todo.html - switchTab() 函數

**新增邏輯：**
```javascript
// 在 switchTab() 函數中添加
function switchTab(tabName) {
    currentTab = tabName;
    
    // ... 現有代碼 ...
    
    // 根據頁籤顯示/隱藏篩選選項
    const filterStatus = document.getElementById('filterStatus');
    const filterStatusContainer = filterStatus?.parentElement;
    
    if (tabName === 'historical') {
        // 歷史記錄不顯示狀態篩選
        if (filterStatusContainer) {
            filterStatusContainer.style.display = 'none';
        }
    } else if (tabName === 'current') {
        // 當前未完成顯示狀態篩選
        if (filterStatusContainer) {
            filterStatusContainer.style.display = 'block';
        }
    }
    
    // ... 現有代碼 ...
}
```

---

### 方案 3：改進 filterTableRows() 函數

**修改位置：** templates/reports_todo.html - filterTableRows() 函數

**確保此函數能正確處理當前未完成任務的篩選**

**現有代碼檢查：**
```javascript
function filterTableRows() {
    const filterUser = document.getElementById('filterUser');
    if (!filterUser) return;
    
    const selectedUser = filterUser.value;
    const tables = document.querySelectorAll('.data-table tbody');
    
    tables.forEach(tbody => {
        const rows = tbody.getElementsByTagName('tr');
        for (let row of rows) {
            if (!selectedUser || row.dataset.user === selectedUser) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        }
    });
}
```

**問題：** 需要確保當前未完成任務的表格行也有 `data-user` 屬性

---

## 📝 實施步驟

### Step 1: 檢查當前未完成任務表格的 data-user 屬性
- [x] 查看 `loadCurrentData()` 函數
- [x] 確認表格行包含 `data-user` 屬性（第 826 行）

### Step 2: 修改 applyFilters() 函數
- [x] 添加對 'current' 頁籤的處理
- [x] 調用 filterTableRows() 進行客戶端篩選

### Step 3: 修改 switchTab() 函數
- [x] 添加根據頁籤顯示/隱藏狀態篩選的邏輯
- [x] 當前未完成頁籤顯示篩選區塊
- [x] 歷史任務頁籤隱藏狀態篩選
- [x] 測試各頁籤切換時篩選選項的顯示

### Step 4: 測試驗證
- [ ] 測試歷史任務頁籤 - 確認無狀態篩選
- [ ] 測試當前未完成頁籤 - 確認負責人篩選有效
- [ ] 測試篩選選項的動態顯示/隱藏

---

## ✅ 測試檢查清單

### 功能測試
- [ ] 歷史任務頁籤不顯示狀態篩選
- [ ] 當前未完成頁籤顯示狀態篩選
- [ ] 當前未完成頁籤 - 選擇負責人後正確篩選
- [ ] 當前未完成頁籤 - 選擇「全部」顯示所有任務
- [ ] 頁籤切換時篩選選項正確顯示/隱藏

### 回歸測試
- [ ] 歷史任務的負責人篩選仍然正常
- [ ] 歷史任務的時間範圍篩選仍然正常
- [ ] 排序功能不受影響
- [ ] 其他頁籤功能正常

---

## 📊 影響評估

### 影響的檔案
- templates/reports_todo.html

### 影響的函數
- `applyFilters()`
- `switchTab()`
- `filterTableRows()`

### 風險評估
- **風險等級：** 低
- **理由：** 僅修改前端 JavaScript 代碼，不涉及後端 API 和資料庫
- **回滾方案：** 從備份恢復 templates/reports_todo.html

---

## 📅 時程規劃

- **預計修復時間：** 30 分鐘
- **測試時間：** 15 分鐘
- **總計：** 45 分鐘

---

## 📌 備註

此次修復專注於前端 JavaScript 邏輯，不需要修改後端 Python 代碼或資料庫結構。

---

**建立日期：** 2025-10-03
**最後更新：** 2025-10-03 13:15
**狀態：** 已實施，待測試
