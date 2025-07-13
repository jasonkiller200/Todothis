from enum import Enum, auto

# 定義組織階層的順序，用於排序
LEVEL_ORDER = {
    'admin': 10,            # 系統管理員
    'executive-manager': 9, # 製造中心-協理 (第一階)
    'plant-manager': 8,     # 廠長 (第二階)
    'manager': 7,           # 經理 (第二階)
    'assistant-manager': 6, # 副理 (第二階)
    'section-chief': 5,     # 課長 (第三階)
    'deputy-section-chief': 4, # 副課長 (第三階)
    'team-leader': 3,       # 組長 (第四階)
    'staff': 0              # 作業員
}

# 定義新的組織結構，以四大部門為基礎
DEPARTMENT_STRUCTURE = {
    '第一廠': {'management_team': [], 'units': {}},
    '第三廠': {'management_team': [], 'units': {}},
    '採購物流部': {'management_team': [], 'units': {}},
    '品保部': {'management_team': [], 'units': {}}
}

# 輔助對應表：將資料庫中的單位(課)對應到四大部門
UNIT_TO_MAIN_DEPT_MAP = {
    '裝一課': '第一廠', '裝二課': '第一廠', '裝三課': '第一廠',
    '品管課': '第三廠', '資材成本課': '第三廠', '資材管理課': '第三廠',
    '組件課': '第一廠'
}

# 登入與帳戶鎖定配置
LOGIN_ATTEMPTS_LIMIT = 3
ACCOUNT_LOCK_MINUTES = 30

class UserLevel(str, Enum):
    ADMIN = "admin"
    EXECUTIVE_MANAGER = "executive-manager"
    PLANT_MANAGER = "plant-manager"
    MANAGER = "manager"
    ASSISTANT_MANAGER = "assistant-manager"
    SECTION_CHIEF = "section-chief"
    DEPUTY_SECTION_CHIEF = "deputy-section-chief"
    TEAM_LEADER = "team-leader"
    STAFF = "staff"

class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    UNCOMPLETED = "uncompleted"

class TodoType(str, Enum):
    CURRENT = "current"
    NEXT = "next"