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
    # 第一廠
    '裝一課': '第一廠', 
    '裝二課': '第一廠', 
    '組件課': '第一廠',
    # 第三廠
    '裝三課': '第三廠',
    '加工課': '第三廠',
    # 採購物流部
    '資材成本課': '採購物流部', 
    '資材管理課': '採購物流部',
    # 品保部
    '品管課': '品保部'
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

class MeetingTaskStatus(str, Enum):
    UNASSIGNED = "unassigned" # 追蹤項目初始狀態，待指派到 Todo
    ASSIGNED = "assigned"     # 追蹤項目已指派到 Todo
    IN_PROGRESS_TODO = "in_progress_todo" # 追蹤項目關聯的 Todo 任務進行中
    UNCOMPLETED_TODO = "uncompleted_todo" # 追蹤項目關聯的 Todo 任務未完成
    COMPLETED = "completed"   # 會議任務已完成 (Todo 完成後回填)
    RESOLUTION_ITEM = "resolution-item"
    RESOLVED_EXECUTING = "resolved_executing" # 決議通過執行，不指派到 Todo
    AGREED_FINALIZED = "agreed_finalized" # 決議已同意並最終確定
    CANCELLED = "cancelled" # 新增已取消狀態

class MeetingTaskType(str, Enum):
    TRACKING = "tracking"
    RESOLUTION = "resolution"

MEETING_TASK_STATUS_CHINESE = {
    MeetingTaskStatus.UNASSIGNED.value: "未指派",
    MeetingTaskStatus.ASSIGNED.value: "已指派",
    MeetingTaskStatus.IN_PROGRESS_TODO.value: "進行中(主任務)",
    MeetingTaskStatus.COMPLETED.value: "已完成",
    MeetingTaskStatus.UNCOMPLETED_TODO.value: "未完成(主任務)",
    MeetingTaskStatus.RESOLVED_EXECUTING.value: "決議執行中",
    MeetingTaskStatus.AGREED_FINALIZED.value: "已同意並最終確定",
    MeetingTaskStatus.CANCELLED.value: "已取消"
}

# Mail Service API URL
MAIL_API_URL = "http://192.168.1.231/HFSRAPITS/SendMail/APISend"