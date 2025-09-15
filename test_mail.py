import os
import sys
from datetime import datetime, timedelta # Import timedelta
from pytz import timezone, utc

# 將專案根目錄添加到 Python 路徑中，以便導入 mail_service
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from mail_service import send_mail

# 假設的任務數據，用於構建郵件內容
class MockUser:
    def __init__(self, name, email):
        self.name = name
        self.email = email

class MockTask:
    def __init__(self, id, title, description, due_date, assigned_by=None):
        self.id = id
        self.title = title
        self.description = description
        self.due_date = due_date
        self.assigned_by = assigned_by

class MockAssigner:
    def __init__(self, name, email):
        self.name = name
        self.email = email

def run_test_mail():
    print("--- 測試純文字 URL 郵件發送 ---")

    # 請替換為實際可用的收件人郵箱
    test_recipient_email = "ralf@hartford.com.tw" 
    
    # 測試純文字 URL
    subject_plain = "[測試] 純文字 URL 郵件"
    body_plain = (
        f"您好，\n\n"
        f"這是一封測試純文字 URL 郵件。\n\n"
        f"請登入系統查看：\nhttp://192.168.6.119:5001\n\n" # URL on its own line
        f"此致，\n"
        f"測試系統"
    )
    success_plain, msg_plain = send_mail(
        subject=subject_plain,
        body=body_plain,
        mail_to=test_recipient_email
    )
    print(f"Plain Text URL Mail Success: {success_plain}, Message: {msg_plain}\n")

    # 測試排程器中的「今天到期」通知
    print("--- 測試排程器「今天到期」通知 (模擬) ---")
    user_due = MockUser("測試用戶A", test_recipient_email)
    task_due = MockTask(101, "完成報告", "提交月度進度報告", datetime.now(timezone('Asia/Taipei')) + timedelta(days=0))
    assigner_due = MockAssigner("指派人X", "assigner.x@example.com")
    task_due.assigned_by = assigner_due

    subject_due = f"[今天到期] {task_due.title}"
    body_due = (
        f"您好 {user_due.name}，\n\n"
        f"這是一則提醒，您的任務「{task_due.title}」即將在今天到期。\n\n"
        f"任務描述:\n{task_due.description}\n\n"
        f"預計完成日期: {task_due.due_date.strftime('%Y-%m-%d')}\n"
        f"指派人: {task_due.assigned_by.name if task_due.assigned_by else '自己'}\n\n"
        f"請登入系統查看：\nhttp://192.168.6.119:5001" # URL on its own line
    )
    success_due, msg_due = send_mail(subject_due, body_due, user_due.email)
    print(f"Due Today Mail Success: {success_due}, Message: {msg_due}\n")

    # 測試排程器中的「任務延誤」通知
    print("--- 測試排程器「任務延誤」通知 (模擬) ---")
    user_overdue = MockUser("測試用戶B", test_recipient_email)
    task_overdue = MockTask(102, "專案規劃", "完成新專案的初步規劃", datetime.now(timezone('Asia/Taipei')) - timedelta(days=1))
    assigner_overdue = MockAssigner("指派人Y", "assigner.y@example.com")
    task_overdue.assigned_by = assigner_overdue

    subject_overdue = f"[任務延誤] {task_overdue.title}"
    body_overdue = (
        f"您好，\n\n"
        f"任務「{task_overdue.title}」已超過預計完成日期。\n\n"
        f"任務負責人: {user_overdue.name}\n"
        f"任務描述:\n{task_overdue.description}\n\n"
        f"預計完成日期: {task_overdue.due_date.strftime('%Y-%m-%d')}\n\n"
        f"請登入系統查看：\nhttp://192.168.6.119:5001" # URL on its own line
    )
    success_overdue, msg_overdue = send_mail(subject_overdue, body_overdue, user_overdue.email)
    print(f"Overdue Mail Success: {success_overdue}, Message: {msg_overdue}\n")

    # 測試 app.py 中的「新任務指派」通知
    print("--- 測試 App「新任務指派」通知 (模擬) ---")
    target_user_assign = MockUser("被指派人C", test_recipient_email)
    current_user_assign = MockUser("指派人Z", "assigner.z@example.com")
    todo_assign = MockTask(201, "新功能開發", "開發使用者管理模組", datetime.now(timezone('Asia/Taipei')) + timedelta(days=5))

    subject_assign = f"[新任務指派] {todo_assign.title}"
    body_assign = (
        f"您好 {target_user_assign.name}，\n\n"
        f"您被 {current_user_assign.name} 指派了一項新任務。\n\n"
        f"任務標題: {todo_assign.title}\n"
        f"任務描述:\n{todo_assign.description}\n\n"
        f"預計完成日期: {todo_assign.due_date.strftime('%Y-%m-%d')}\n\n"
        f"請登入系統查看：\nhttp://192.168.6.119:5001" # URL on its own line
    )
    success_assign, msg_assign = send_mail(subject_assign, body_assign, target_user_assign.email)
    print(f"New Task Assign Mail Success: {success_assign}, Message: {msg_assign}\n")

    # 測試 app.py 中的「任務完成」通知
    print("--- 測試 App「任務完成」通知 (模擬) ---")
    assigner_complete = MockUser("指派人W", test_recipient_email)
    todo_complete_user = MockUser("完成人D", "completer.d@example.com")
    todo_complete = MockTask(301, "文件審核", "審核專案需求文件", datetime.now(timezone('Asia/Taipei')) - timedelta(days=2), assigned_by=assigner_complete)
    todo_complete.user = todo_complete_user # 模擬 todo.user

    subject_complete = f"[任務完成] {todo_complete.title}"
    body_complete = (
        f"您好 {assigner_complete.name}，\n\n"
        f"由您指派給 {todo_complete.user.name} 的任務已完成。\n\n"
        f"任務標題: {todo_complete.title}\n"
        f"任務描述:\n{todo_complete.description}\n\n"
        f"完成日期: {datetime.now(timezone('Asia/Taipei')).strftime('%Y-%m-%d')}\n\n"
        f"請登入系統查看：\nhttp://192.168.6.119:5001" # URL on its own line
    )
    success_complete, msg_complete = send_mail(subject_complete, body_complete, assigner_complete.email)
    print(f"Task Complete Mail Success: {success_complete}, Message: {msg_complete}\n")

    # 測試 app.py 中的「會議任務指派到 Todo」通知
    print("--- 測試 App「會議任務指派到 Todo」通知 (模擬) ---")
    assigned_to_meeting_user = MockUser("會議任務負責人E", test_recipient_email)
    assigner_meeting_user = MockUser("會議任務指派人F", "meeting.assigner.f@example.com")
    mock_meeting = type('MockMeeting', (object,), {'subject': '週會', 'meeting_date': datetime.now(timezone('Asia/Taipei'))})()
    new_todo_meeting = MockTask(401, f"【會議追蹤】{mock_meeting.subject} ({mock_meeting.meeting_date.strftime('%Y-%m-%d')})", "追蹤新產品開發進度", datetime.now(timezone('Asia/Taipei')) + timedelta(days=10))
    new_todo_meeting.user = assigned_to_meeting_user # 模擬 new_todo.user

    subject_meeting = f"會議任務指派：{new_todo_meeting.title}"
    body_meeting = (
        f"您好 {assigned_to_meeting_user.name}，\n\n"
        f"您有一個新的會議任務已指派給您：\n\n"
        f"任務標題： {new_todo_meeting.title}\n"
        f"任務描述： {new_todo_meeting.description}\n"
        f"預計完成日期： {new_todo_meeting.due_date.astimezone(timezone('Asia/Taipei')).strftime('%Y-%m-%d')}\n"
        f"指派人： {assigner_meeting_user.name}\n\n"
        f"請登入系統查看：\nhttp://192.168.6.119:5001" # URL on its own line
    )
    success_meeting, msg_meeting = send_mail(subject_meeting, body_meeting, assigned_to_meeting_user.email)
    print(f"Meeting Task Assign Mail Success: {success_meeting}, Message: {msg_meeting}\n")

    # 測試 app.py 中的「決議已同意」通知
    print("--- 測試 App「決議已同意」通知 (模擬) ---")
    controller_agree_user = MockUser("管制者G", test_recipient_email)
    current_agree_user = MockUser("同意人H", "agree.user.h@example.com")
    mock_meeting_agree = type('MockMeeting', (object,), {'subject': '月度檢討會'})()
    mock_meeting_task_agree = type('MockMeetingTask', (object,), {'meeting': mock_meeting_agree, 'task_description': '優化生產流程'})()

    subject_agree = f"決議已同意：{mock_meeting_task_agree.meeting.subject}"
    body_agree = (
        f"您好 {controller_agree_user.name}，\n\n"
        f"會議決議 {mock_meeting_task_agree.meeting.subject} 中的任務 {mock_meeting_task_agree.task_description} 已由 {current_agree_user.name} 同意並最終確定。\n\n"
        f"請登入系統查看：\nhttp://192.168.6.119:5001" # URL on its own line
    )
    success_agree, msg_agree = send_mail(subject_agree, body_agree, controller_agree_user.email)
    print(f"Agree Meeting Task Mail Success: {success_agree}, Message: {msg_agree}\n")


if __name__ == '__main__':
    run_test_mail()
