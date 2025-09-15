import logging
from datetime import datetime, timedelta
from pytz import timezone, utc
import time
import atexit
import json
from apscheduler.schedulers.background import BackgroundScheduler
from mail_service import send_mail
from config import TodoStatus, TodoType, MeetingTaskStatus, MeetingTaskType
from report_service import generate_and_send_weekly_report # 導入新的服務函式

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
TAIPEI_TZ = timezone('Asia/Taipei')

def check_due_today_tasks(app, db, User, Todo):
    """
    Checks for tasks due today and sends notifications.
    """
    with app.app_context():
        logging.info("Running check_due_today_tasks...")
        taiwan_tz = timezone('Asia/Taipei')
        today_start_taipei = datetime.now(taiwan_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end_taipei = today_start_taipei + timedelta(days=1) - timedelta(microseconds=1)

        # Convert to UTC for database query
        today_start_utc = today_start_taipei.astimezone(utc)
        today_end_utc = today_end_taipei.astimezone(utc)

        # Find users with tasks due today that are not completed
        users_to_notify = db.session.query(User).join(Todo, User.id == Todo.user_id).filter(
            Todo.due_date >= today_start_utc,
            Todo.due_date <= today_end_utc,
            Todo.status != TodoStatus.COMPLETED.value,
            User.notification_enabled == True
        ).distinct().all()

        for user in users_to_notify:
            user_due_today_tasks = Todo.query.filter(
                Todo.user_id == user.id,
                Todo.due_date >= today_start_utc,
                Todo.due_date <= today_end_utc,
                Todo.status != TodoStatus.COMPLETED.value
            ).order_by(Todo.due_date).all()

            if user_due_today_tasks:
                subject = f"【今日任務提醒】您有 {len(user_due_today_tasks)} 項任務今日到期！"
                body_parts = [f"您好 {user.name}，", "", "以下是您今日到期的任務：", ""]
                for task in user_due_today_tasks:
                    due_date_str = task.due_date.astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M')
                    body_parts.append(f"    標題: {task.title}")
                    body_parts.append(f"    描述: {task.description}")
                    body_parts.append(f"    預計完成日期: {due_date_str}")
                    body_parts.append("")
                body_parts.append("請登入系統查看並完成您的任務：")
                body_parts.append("http://192.168.6.119:5001") # Assuming this is the correct URL
                body = "\n".join(body_parts)

                try:
                    send_mail(subject, body, user.email)
                    logging.info(f"Sent 'due today' notification to {user.email} for {len(user_due_today_tasks)} tasks.")
                except Exception as e:
                    logging.error(f"Failed to send 'due today' notification to {user.email}: {e}")

def check_overdue_tasks(app, db, User, Todo):
    """
    Checks for overdue tasks and sends notifications.
    """
    with app.app_context():
        logging.info("Running check_overdue_tasks...")
        taiwan_tz = timezone('Asia/Taipei')
        today_start_taipei = datetime.now(taiwan_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = today_start_taipei.astimezone(utc)

        # Find users with overdue tasks that are not completed
        users_to_notify = db.session.query(User).join(Todo, User.id == Todo.user_id).filter(
            Todo.due_date < today_start_utc, # Tasks due before today
            Todo.status != TodoStatus.COMPLETED.value,
            User.notification_enabled == True
        ).distinct().all()

        for user in users_to_notify:
            user_overdue_tasks = Todo.query.filter(
                Todo.user_id == user.id,
                Todo.due_date < today_start_utc,
                Todo.status != TodoStatus.COMPLETED.value
            ).order_by(Todo.due_date).all()

            if user_overdue_tasks:
                subject = f"【逾期任務提醒】您有 {len(user_overdue_tasks)} 項任務已逾期！"
                body_parts = [f"您好 {user.name}，", "", "以下是您已逾期的任務：", ""]
                for task in user_overdue_tasks:
                    due_date_str = task.due_date.astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M')
                    body_parts.append(f"    標題: {task.title}")
                    body_parts.append(f"    描述: {task.description}")
                    body_parts.append(f"    預計完成日期: {due_date_str}")
                    body_parts.append("")
                body_parts.append("請登入系統查看並盡快處理您的逾期任務：")
                body_parts.append("http://192.168.6.119:5001") # Assuming this is the correct URL
                body = "\n".join(body_parts)

                try:
                    send_mail(subject, body, user.email)
                    logging.info(f"Sent 'overdue' notification to {user.email} for {len(user_overdue_tasks)} tasks.")
                except Exception as e:
                    logging.error(f"Failed to send 'overdue' notification to {user.email}: {e}")


def check_unassigned_meeting_tasks(app, db, User, MeetingTask, Meeting):
    """
    Checks for unassigned meeting tasks and sends notifications.
    """
    with app.app_context():
        logging.info("Running check_unassigned_meeting_tasks...")
        taiwan_tz = timezone('Asia/Taipei')
        now_taipei = datetime.now(taiwan_tz)
        now_utc = now_taipei.astimezone(utc)

        # Find tracking meeting tasks that are still unassigned and whose meeting date has passed
        unassigned_tasks = db.session.query(MeetingTask).join(Meeting).filter(
            MeetingTask.task_type == MeetingTaskType.TRACKING.value,
            MeetingTask.status == MeetingTaskStatus.UNASSIGNED.value,
            Meeting.meeting_date < now_utc # Meeting date has passed
        ).all()

        for task in unassigned_tasks:
            chairman = db.session.get(User, task.meeting.chairman_user_id)
            assigned_by_user = db.session.get(User, task.assigned_by_user_id)
            controller_user = db.session.get(User, task.controller_user_id) if task.controller_user_id else None

            recipients = set()
            if chairman and chairman.notification_enabled:
                recipients.add(chairman.email)
            if assigned_by_user and assigned_by_user.notification_enabled:
                recipients.add(assigned_by_user.email)

            cc_recipients = set()
            if controller_user and controller_user.notification_enabled:
                cc_recipients.add(controller_user.email)

            if recipients:
                subject = f"【未指派會議任務提醒】會議：{task.meeting.subject} - 任務：{task.task_description}"
                body_parts = [f"您好，", "", f"會議「{task.meeting.subject}」中有一項追蹤任務尚未指派：", ""]
                body_parts.append(f"  - 任務描述: {task.task_description}")
                body_parts.append(f"  - 會議日期: {task.meeting.meeting_date.astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M')}")
                body_parts.append(f"  - 主席: {chairman.name if chairman else 'N/A'}")
                body_parts.append(f"  - 創建者: {assigned_by_user.name if assigned_by_user else 'N/A'}")
                body_parts.append("")
                body_parts.append("請盡快登入系統指派此任務：")
                body_parts.append("http://192.168.6.119:5001/meeting_tasks") # Link directly to meeting tasks page
                body = "\n".join(body_parts)

                try:
                    send_mail(subject, body, list(recipients), cc_recipients=list(cc_recipients))
                    logging.info(f"Sent 'unassigned meeting task' notification for task {task.id} to {recipients}.")
                except Exception as e:
                    logging.error(f"Failed to send 'unassigned meeting task' notification for task {task.id}: {e}")


def check_unagreed_resolution_items(app, db, User, MeetingTask, Meeting):
    """
    Checks for unagreed resolution items and sends notifications.
    """
    with app.app_context():
        logging.info("Running check_unagreed_resolution_items...")
        taiwan_tz = timezone('Asia/Taipei')
        now_taipei = datetime.now(taiwan_tz)
        now_utc = now_taipei.astimezone(utc)

        # Find resolution meeting tasks that are not yet agreed/finalized
        unagreed_resolution_items = db.session.query(MeetingTask).join(Meeting).filter(
            MeetingTask.task_type == MeetingTaskType.RESOLUTION.value,
            MeetingTask.status != MeetingTaskStatus.AGREED_FINALIZED.value,
            MeetingTask.expected_completion_date < now_utc # Expected completion date has passed
        ).all()

        for item in unagreed_resolution_items:
            assigned_to_user = db.session.get(User, item.assigned_to_user_id)
            chairman = db.session.get(User, item.meeting.chairman_user_id)
            controller_user = db.session.get(User, item.controller_user_id) if item.controller_user_id else None

            recipients = set()
            if assigned_to_user and assigned_to_user.notification_enabled:
                recipients.add(assigned_to_user.email)
            if chairman and chairman.notification_enabled:
                recipients.add(chairman.email)

            cc_recipients = set()
            if controller_user and controller_user.notification_enabled:
                cc_recipients.add(controller_user.email)

            if recipients:
                subject = f"【未同意決議提醒】會議：{item.meeting.subject} - 決議：{item.task_description}"
                body_parts = [f"您好", "", f"會議「{item.meeting.subject}」中有一項決議尚未同意並最終確定：", ""]
                body_parts.append(f"  - 決議事項: {item.task_description}")
                body_parts.append(f"  - 負責人員: {assigned_to_user.name if assigned_to_user else 'N/A'}")
                body_parts.append(f"  - 預計完成日期: {item.expected_completion_date.astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M')}")
                body_parts.append("")
                body_parts.append("請盡快登入系統處理此決議：")
                body_parts.append("http://192.168.6.119:5001/meeting_tasks") # Link directly to meeting tasks page
                body = "\n".join(body_parts)

                try:
                    send_mail(subject, body, list(recipients), cc_recipients=list(cc_recipients))
                    logging.info(f"Sent 'unagreed resolution item' notification for item {item.id} to {recipients}.")
                except Exception as e:
                    logging.error(f"Failed to send 'unagreed resolution item' notification for item {item.id}: {e}")


def transfer_and_archive_todos(app, db, Todo, ArchivedTodo):
    """每週任務轉移和歸檔的排程任務"""
    with app.app_context():
        logging.info(f"Running weekly todo transfer and archive job...")
        
        # 使用台灣時區來確定當前日期
        taiwan_tz = timezone('Asia/Taipei')
        today_dt_tw = datetime.now(taiwan_tz)

        # 計算本週的開始日期 (週一) 和結束日期 (週日)
        start_of_week_date = today_dt_tw.date() - timedelta(days=today_dt_tw.weekday())
        end_of_week_date = start_of_week_date + timedelta(days=6)

        # 將日期轉換為時區感知的 datetime 物件，用於資料庫查詢
        start_of_week_dt = taiwan_tz.localize(datetime.combine(start_of_week_date, datetime.min.time()))
        end_of_week_dt = taiwan_tz.localize(datetime.combine(end_of_week_date, datetime.max.time()))

        # 1. 根據 due_date 轉移未來計畫到本週進度
        # 查找所有 todo_type 為 NEXT 且 due_date 在本週範圍內的任務
        todos_to_transfer = Todo.query.filter(
            Todo.todo_type == TodoType.NEXT.value,
            Todo.due_date >= start_of_week_dt.astimezone(utc), # 轉換為 UTC 進行比較
            Todo.due_date <= end_of_week_dt.astimezone(utc)   # 轉換為 UTC 進行比較
        ).all()

        for todo in todos_to_transfer:
            todo.todo_type = TodoType.CURRENT.value
            # 記錄自動轉移事件
            history = json.loads(todo.history_log or '[]')
            history.append({
                'event_type': 'auto_transfer',
                'timestamp': datetime.now(utc).isoformat(),
                'actor': {'name': 'System', 'user_key': 'system'},
                'details': {'from_type': 'next', 'to_type': 'current', 'due_date': todo.due_date.isoformat()}
            })
            todo.history_log = json.dumps(history)
            db.session.add(todo)
        db.session.commit()
        logging.info(f"Transferred {len(todos_to_transfer)} future todos to current based on due_date.")

        # 2. 歸檔或刪除已完成的本週進度
        completed_current_todos = Todo.query.filter_by(todo_type=TodoType.CURRENT.value, status=TodoStatus.COMPLETED.value).all()
        archived_count = 0
        deleted_count = 0

        for todo in completed_current_todos:
            # 如果是從會議任務來的，直接刪除，因為資訊已回填
            if todo.meeting_task_id:
                db.session.delete(todo)
                deleted_count += 1
            # 如果是一般任務，則歸檔
            else:
                history = json.loads(todo.history_log or '[]')
                history.append({
                    'event_type': 'archived',
                    'timestamp': datetime.now(utc).isoformat(),
                    'actor': {'name': 'System', 'user_key': 'system'},
                    'details': {}
                })
                todo.history_log = json.dumps(history)

                archived_todo = ArchivedTodo(
                    original_todo_id=todo.id,
                    title=todo.title,
                    description=todo.description,
                    status=todo.status,
                    todo_type=todo.todo_type,
                    user_id=todo.user_id,
                    assigned_by_user_id=todo.assigned_by_user_id,
                    history_log=todo.history_log,
                    created_at=todo.created_at,
                    updated_at=todo.updated_at,
                    archived_at=datetime.now(utc),
                    due_date=todo.due_date
                )
                db.session.add(archived_todo)
                db.session.delete(todo)
                archived_count += 1
        
        db.session.commit()
        logging.info(f"Archived {archived_count} general completed todos.")
        logging.info(f"Deleted {deleted_count} completed todos from meeting tasks.")
        logging.info(f"Weekly todo job finished.")

def check_and_trigger_reports(app, db, User, Todo, ReportSchedule):
    """
    Checks for scheduled weekly reports and triggers them if conditions are met.
    This function runs at a set interval.
    """
    with app.app_context():
        logging.info("Running 'check_and_trigger_reports'...")
        now_taipei = datetime.now(TAIPEI_TZ)
        
        active_schedules = ReportSchedule.query.filter_by(is_active=True).all()

        if not active_schedules:
            # This log is not an error, just informational.
            # logging.info("No active report schedules found.")
            return

        for schedule in active_schedules:
            is_right_day = now_taipei.weekday() == schedule.schedule_day
            is_right_time = now_taipei.time() >= schedule.schedule_time

            if not (is_right_day and is_right_time):
                continue

            if schedule.last_sent_at and (now_taipei - schedule.last_sent_at.astimezone(TAIPEI_TZ)) < timedelta(hours=23):
                continue

            logging.info(f"Schedule {schedule.id} for department '{schedule.department}' is due. Performing validation...")

            users_in_dept = User.query.filter(User.unit == schedule.department, User.is_active == True).all()
            if not users_in_dept:
                logging.warning(f"No active users found in unit '{schedule.department}' for schedule {schedule.id}. Skipping.")
                continue
            
            user_ids_in_dept = [user.id for user in users_in_dept]

            start_of_this_week = now_taipei.date() - timedelta(days=now_taipei.weekday())
            overdue_tasks_exist = db.session.query(Todo).filter(
                Todo.user_id.in_(user_ids_in_dept),
                db.func.date(Todo.due_date) < start_of_this_week,
                Todo.status != TodoStatus.COMPLETED.value
            ).first()

            if overdue_tasks_exist:
                logging.warning(f"Validation failed for schedule {schedule.id}: Found overdue tasks from before this week for department '{schedule.department}'.")
                continue

            start_of_next_week = start_of_this_week + timedelta(days=7)
            end_of_next_week = start_of_next_week + timedelta(days=6)
            # Only apply 'require_next_week_tasks' validation if the schedule explicitly requires it
            if schedule.require_next_week_tasks:
                next_week_task_exists = db.session.query(Todo).filter(
                    Todo.user_id.in_(user_ids_in_dept),
                    db.func.date(Todo.due_date) >= start_of_next_week,
                    db.func.date(Todo.due_date) <= end_of_next_week
                ).first()

                if not next_week_task_exists:
                    logging.warning(f"Validation failed for schedule {schedule.id}: No tasks planned for next week for department '{schedule.department}'.")
                    continue
            
            logging.info(f"Validation passed for schedule {schedule.id}. Triggering report generation.")
            try:
                # 呼叫新的服務函式
                generate_and_send_weekly_report(app, db, User, Todo, ReportSchedule, schedule.id)
            except Exception as e:
                logging.error(f"An error occurred while generating report for schedule {schedule.id}: {e}")

def check_scheduled_notifications(app, db, User, ScheduledNotification):
    """
    Checks for user-defined scheduled notifications and sends them.
    """
    with app.app_context():
        logging.info("Running check_scheduled_notifications...")
        now_taipei = datetime.now(TAIPEI_TZ)
        
        active_notifications = ScheduledNotification.query.filter_by(is_active=True).all()

        for notification in active_notifications:
            should_send = False
            
            # Convert specific_time (naive time object) to a datetime object in Taipei timezone for comparison
            scheduled_time_taipei = TAIPEI_TZ.localize(datetime.combine(now_taipei.date(), notification.specific_time))

            if notification.schedule_type == 'one_time':
                # For one-time notifications, check if the specific date matches today and the time has passed
                if notification.specific_date == now_taipei.date():
                    # Check if the scheduled time is within the last 5 minutes (to account for scheduler interval)
                    # and has not been sent recently
                    if now_taipei >= scheduled_time_taipei and \
                       now_taipei < scheduled_time_taipei + timedelta(minutes=5):
                        if not notification.last_sent_at or \
                           (now_taipei - notification.last_sent_at.astimezone(TAIPEI_TZ)) >= timedelta(hours=23):
                            should_send = True
                            logging.info(f"One-time notification {notification.id} is due.")

            elif notification.schedule_type == 'weekly':
                # For weekly notifications, check if the day of the week matches and the time has passed
                if notification.weekly_day == now_taipei.weekday(): # Monday is 0, Sunday is 6
                    if now_taipei >= scheduled_time_taipei and \
                       now_taipei < scheduled_time_taipei + timedelta(minutes=5):
                        if not notification.last_sent_at or \
                           (now_taipei - notification.last_sent_at.astimezone(TAIPEI_TZ)) >= timedelta(hours=23):
                            should_send = True
                            logging.info(f"Weekly notification {notification.id} is due.")

            if should_send:
                recipient_ids = [int(uid) for uid in notification.recipient_user_ids.split(',') if uid.strip()]
                recipients_to_email = []
                for user_id in recipient_ids:
                    user = db.session.get(User, user_id)
                    if user and user.email and user.notification_enabled:
                        recipients_to_email.append(user.email)
                
                if recipients_to_email:
                    # Convert list of emails to a semicolon-separated string
                    recipients_to_email_str = ";".join(recipients_to_email)

                    subject = f"【任務系統定時通知】{notification.title}"
                    # Convert plain text body to HTML for the mail service
                    html_body_content = notification.body.replace('\n', '<br>')
                    body = f"""
<!DOCTYPE html>
<html>
<head>
    <title>任務系統定時通知</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Noto Sans TC', sans-serif; line-height: 1.6; color: #333; }}
        .container {{ width: 80%; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
        .header {{ background-color: #f4f4f4; padding: 10px; border-bottom: 1px solid #ddd; }}
        .content {{ padding: 20px 0; }}
        .footer {{ margin-top: 20px; font-size: 0.8em; color: #777; border-top: 1px solid #ddd; padding-top: 10px; }}
        a {{ color: #007bff; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>任務系統定時通知</h2>
        </div>
        <div class="content">
            <p>您好，</p>
            <p>這是一則定時通知：</p>
            <p><strong>標題:</strong> {notification.title}</p>
            <p><strong>內容:</strong></p>
            <p>{html_body_content}</p>
            <p>請登入系統查看：<br><a href="http://192.168.6.119:5001">http://192.168.6.119:5001</a></p>
        </div>
        <div class="footer">
            <p>此為系統自動發送郵件，請勿直接回覆。</p>
        </div>
    </div>
</body>
</html>
"""
                    try:
                        send_mail(subject, body, recipients_to_email_str)
                        notification.last_sent_at = datetime.now(utc) # Update last sent time in UTC
                        db.session.commit()
                        logging.info(f"Sent scheduled notification {notification.id} to {recipients_to_email_str}.")
                    except Exception as e:
                        db.session.rollback()
                        logging.error(f"Failed to send scheduled notification {notification.id} to {recipients_to_email_str}: {e}")
                else:
                    logging.warning(f"Scheduled notification {notification.id} has no active or email-enabled recipients.")


def init_app_scheduler(app, db, User, Todo, ArchivedTodo, MeetingTask, Meeting, ScheduledNotification, ReportSchedule):
    """
    Initializes and starts the background scheduler for the Flask app.
    """
    scheduler = BackgroundScheduler()
    taiwan_tz = timezone('Asia/Taipei')

    # ... (現有 cron jobs 維持不變) ...
    scheduler.add_job(transfer_and_archive_todos, 'cron', day_of_week='mon', hour=0, minute=1, timezone=taiwan_tz, misfire_grace_time=60, args=[app, db, Todo, ArchivedTodo])
    scheduler.add_job(check_due_today_tasks, 'cron', day_of_week='mon-fri', hour=7, minute=30, timezone=taiwan_tz, misfire_grace_time=60, args=[app, db, User, Todo])
    scheduler.add_job(check_overdue_tasks, 'cron', day_of_week='mon-fri', hour=7, minute=25, timezone=taiwan_tz, misfire_grace_time=60, args=[app, db, User, Todo])
    scheduler.add_job(check_unassigned_meeting_tasks, 'cron', day_of_week='mon-fri', hour=7, minute=35, timezone=taiwan_tz, misfire_grace_time=60, args=[app, db, User, MeetingTask, Meeting])
    scheduler.add_job(check_unagreed_resolution_items, 'cron', day_of_week='mon-fri', hour=7, minute=40, timezone=taiwan_tz, misfire_grace_time=60, args=[app, db, User, MeetingTask, Meeting])
    
    # Add the new ticker job for weekly reports
    scheduler.add_job(check_and_trigger_reports, 'interval', minutes=5, timezone=taiwan_tz, misfire_grace_time=60, args=[app, db, User, Todo, ReportSchedule])

    # New job to check and send user-defined scheduled notifications
    scheduler.add_job(check_scheduled_notifications, 'interval', minutes=1, timezone=taiwan_tz, misfire_grace_time=60, args=[app, db, User, ScheduledNotification])

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
