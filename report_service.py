import logging
from datetime import datetime, timedelta
from pytz import timezone, utc
from mail_service import send_mail
from config import TodoStatus

TAIPEI_TZ = timezone('Asia/Taipei')

def generate_and_send_weekly_report(app, db, User, Todo, ReportSchedule, schedule_id, is_manual_send=False):
    """
    Generates and sends a single weekly report based on a schedule ID.
    If is_manual_send is True, it will not update the last_sent_at timestamp.
    """
    with app.app_context():
        schedule = db.session.get(ReportSchedule, schedule_id)
        if not schedule:
            logging.error(f"Could not find ReportSchedule with id {schedule_id}.")
            return

        manager = schedule.manager
        department_name = schedule.department

        logging.info(f"Generating weekly report for '{department_name}' to be sent to {manager.name} ({manager.email}).")

        users_in_dept = User.query.filter(User.unit == department_name, User.is_active == True).all()
        if not users_in_dept:
            logging.warning(f"No active users found in unit '{department_name}' for schedule {schedule.id}. Skipping report.")
            # Optionally, still send a report saying no users were found or tasks.
            return
            
        user_ids_in_dept = [user.id for user in users_in_dept]

        today = datetime.now(TAIPEI_TZ).date()
        start_of_this_week = today - timedelta(days=today.weekday())
        end_of_this_week = start_of_this_week + timedelta(days=6)
        start_of_next_week = start_of_this_week + timedelta(days=7)
        end_of_next_week = start_of_next_week + timedelta(days=6)

        completed_this_week = Todo.query.filter(
            Todo.user_id.in_(user_ids_in_dept),
            Todo.status == TodoStatus.COMPLETED.value,
            db.func.date(Todo.updated_at) >= start_of_this_week,
            db.func.date(Todo.updated_at) <= end_of_this_week
        ).order_by(Todo.user_id, Todo.due_date).all()

        uncompleted_this_week = Todo.query.filter(
            Todo.user_id.in_(user_ids_in_dept),
            Todo.status != TodoStatus.COMPLETED.value,
            db.func.date(Todo.due_date) <= end_of_this_week
        ).order_by(Todo.user_id, Todo.due_date).all()

        planned_next_week = Todo.query.filter(
            Todo.user_id.in_(user_ids_in_dept),
            db.func.date(Todo.due_date) >= start_of_next_week,
            db.func.date(Todo.due_date) <= end_of_next_week
        ).order_by(Todo.user_id, Todo.due_date).all()

        body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                h3, h4 {{ color: #333; }}
                ul {{ list-style-type: none; padding-left: 0; }}
                li {{ margin-bottom: 5px; padding: 5px; border-left: 3px solid #4285F4; }}
                .footer {{ font-size: 0.8em; color: #777; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <h3>{department_name} - 本週工作報告 ({start_of_this_week.strftime('%Y-%m-%d')} to {end_of_this_week.strftime('%Y-%m-%d')})</h3>
            
            <h4>本週完成項目 ({len(completed_this_week)}):</h4>
            <ul>
                {'' .join(f'<li>{task.title} (<b>完成者:</b> {task.user.name})</li>' for task in completed_this_week) or '<li>無</li>'}
            </ul>

            <h4>本週未完成項目 ({len(uncompleted_this_week)}):</h4>
            <ul>
                {'' .join(f'<li>{task.title} (<b>負責人:</b> {task.user.name}, <b>到期日:</b> {task.due_date.strftime('%Y-%m-%d')})</li>' for task in uncompleted_this_week) or '<li>無</li>'}
            </ul>

            <h4>下週計畫項目 ({len(planned_next_week)}):</h4>
            <ul>
                {'' .join(f'<li>{task.title} (<b>負責人:</b> {task.user.name}, <b>到期日:</b> {task.due_date.strftime('%Y-%m-%d')})</li>' for task in planned_next_week) or '<li>無</li>'}
            </ul>
            <br>
            <p class="footer">此為系統自動發送的郵件。</p>
        </body>
        </html>
        """

        subject = f"[{department_name}] 自動週報 ({start_of_this_week.strftime('%Y-%m-%d')})"
        
        send_mail(subject, body, manager.email, IsBodyHtml="H")
        logging.info(f"Successfully sent weekly report for '{department_name}' to {manager.email}.")

        if not is_manual_send:
            schedule.last_sent_at = datetime.now(utc)
            db.session.commit()
