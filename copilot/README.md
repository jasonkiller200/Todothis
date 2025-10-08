# 📁 Copilot 文檔資料夾

此資料夾包含所有由 GitHub Copilot CLI 協助產生的計畫文檔和實施記錄。

## 📂 資料夾結構

```
copilot/
├── README.md                              (本檔案)
├── overdue_task_reschedule/               (逾期任務重設完成日期功能)
│   ├── UPGRADE_PLAN.md
│   ├── IMPLEMENTATION_SUMMARY.md
│   ├── CHANGES_SUMMARY.md
│   ├── DEPLOYMENT_CHECKLIST.md
│   ├── README_NEW_FEATURE.md
│   └── test_new_feature.py
│
├── reports_center_upgrade/                (報告中心優化升級)
│   ├── REPORTS_CENTER_UPGRADE_PLAN.md
│   └── BACKUP_SUMMARY.md
│
└── other_features/                        (其他功能計畫)
    ├── notification_feature_plan.md
    └── task_king_feature_plan.md
```

## 📋 各計畫說明

### 1️⃣ 逾期任務重設完成日期功能 (overdue_task_reschedule)
**狀態**: ✅ 已完成並部署

**功能概述**:
- 允許使用者在標記任務為「未完成」時重新設定預計完成日期
- 所有變更記錄到履歷中
- 與 MeetingTask 同步
- 郵件提醒包含使用提示

**文檔**:
- UPGRADE_PLAN.md - 完整的升級計畫
- IMPLEMENTATION_SUMMARY.md - 實施總結和技術細節
- CHANGES_SUMMARY.md - 簡要變更摘要
- DEPLOYMENT_CHECKLIST.md - 部署檢查清單
- README_NEW_FEATURE.md - 功能使用指南
- 	est_new_feature.py - 單元測試腳本

### 2️⃣ 報告中心優化升級 (reports_center_upgrade)
**狀態**: 🚧 準備中（已備份）

**功能概述**:
- 建立獨立的 Todo 任務報告頁面
- 建立獨立的 MeetingTask 報告頁面
- 提供豐富的統計分析和視覺化
- 個人排行榜和部門統計

**文檔**:
- REPORTS_CENTER_UPGRADE_PLAN.md - 完整的優化計畫
- BACKUP_SUMMARY.md - 備份記錄

### 3️⃣ 其他功能計畫 (other_features)
**說明**: 其他功能的規劃文檔

**文檔**:
- 
otification_feature_plan.md - 通知功能計畫
- 	ask_king_feature_plan.md - Task King 功能計畫

## 📝 命名規範

各計畫資料夾使用以下命名規範：
- 使用小寫字母和底線分隔
- 使用英文名稱，簡潔明瞭
- 範例: eature_name_project

## 🔍 如何查找文檔

1. **按功能查找**: 進入對應的計畫資料夾
2. **查看升級計畫**: 尋找 *_PLAN.md 或 UPGRADE_PLAN.md
3. **查看實施細節**: 尋找 IMPLEMENTATION_SUMMARY.md
4. **部署指南**: 尋找 DEPLOYMENT_CHECKLIST.md

## 📅 文檔更新記錄

- **2025-10-02**: 初始建立，整理現有文檔
  - 移入逾期任務重設功能相關文檔（6個文件）
  - 移入報告中心升級相關文檔（2個文件）
  - 移入其他功能計畫文檔（2個文件）

## 💡 注意事項

1. 所有 Copilot 產生的文檔都應該存放在此資料夾
2. 每個新計畫都應建立獨立的子資料夾
3. 保持資料夾結構清晰，方便查找
4. 定期更新 README.md，記錄新增的計畫

---

*最後更新: 2025-10-02*  
*維護者: GitHub Copilot CLI + 專案團隊*
