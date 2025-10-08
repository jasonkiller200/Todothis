from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta, time as dt_time
import os
import secrets
import json
import copy
import logging
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from pytz import timezone, utc
from dotenv import load_dotenv
from dateutil.parser import isoparse # 新增導入
from config import LEVEL_ORDER, DEPARTMENT_STRUCTURE, UNIT_TO_MAIN_DEPT_MAP, UserLevel, TodoStatus, TodoType, MeetingTaskStatus, MeetingTaskType, LOGIN_ATTEMPTS_LIMIT, ACCOUNT_LOCK_MINUTES
from sqlalchemy import func, MetaData # 新增導入 func, MetaData
from mail_service import send_mail # 匯入郵件服務
from scheduler import init_app_scheduler # 導入排程器初始化函數
from report_service import generate_and_send_weekly_report # 導入報告服務

# ReportLab 相關導入
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image # 新增 Image 導入
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas # 新增 canvas 導入
from io import BytesIO
from reportlab.lib.utils import ImageReader # 新增 ImageReader 導入

load_dotenv() # 加載 .env 文件中的環境變數

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') # 從環境變數中獲取 SECRET_KEY
# 建立資料庫的絕對路徑
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'todo_system.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

# 配置日誌記錄
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Naming convention for constraints
naming_convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
db = SQLAlchemy(app, metadata=MetaData(naming_convention=naming_convention))
migrate = Migrate(app, db, render_as_batch=True) # 初始化 Flask-Migrate

# 註冊中文字體
pdfmetrics.registerFont(TTFont('NotoSansCJKtc', 'NotoSansTC-Regular.ttf')) # 假設字體檔案在專案根目錄
# 獲取樣式表並設定字體
styles = getSampleStyleSheet()
styles['Normal'].fontName = 'NotoSansCJKtc'
styles['h1'].fontName = 'NotoSansCJKtc'
styles['h2'].fontName = 'NotoSansCJKtc'
styles['h3'].fontName = 'NotoSansCJKtc'
# 移除標題和一般文字的左側縮排，使其與表格對齊
styles['h3'].leftIndent = 0
styles['Normal'].leftIndent = 0

# 狀態翻譯字典
STATUS_TRANSLATIONS = {
    "pending": "待開始",
    "in_progress": "進行中",
    "completed": "已完成",
    "uncompleted": "未完成",
    "unassigned": "待指派",
    "assigned": "已指派",
    "in_progress_todo": "進行中 ",
    "uncompleted_todo": "未完成 ",
    "agreed_finalized": "已同意並最終確定",
    "resolved_executing": "決議執行中"
}

# 定義頁首頁尾函數
def _header_footer_template(canvas, doc, meeting_topic=None, meeting_date_str=None, title="會議記錄"):
    canvas.saveState()
    
    # 頁面尺寸
    page_width, page_height = letter

    # 頁首固定高度
    header_height = 1.2 * inch
    
    # --- 繪製頁首 ---
    # LOGO
    logo_path = os.path.join(os.path.dirname(__file__), 'hartfordlogo-01.png')
    if os.path.exists(logo_path):
        try:
            logo_width = 0.8 * inch
            logo_height = 0.43 * inch # 高度增加 30%
            logo_x = 0.5 * inch # 向左移動 LOGO
            logo_y = page_height - doc.topMargin + header_height - logo_height - (0.1 * inch) # 從頂部向下定位
            canvas.drawImage(logo_path, logo_x, logo_y, width=logo_width, height=logo_height, mask='auto')
        except Exception as e:
            logging.error(f"繪製 LOGO 時出錯: {e}")

    # 公司名稱
    company_name = "協鴻工業股份有限公司"
    target_width = page_width * 0.68 # 調整目標寬度為頁面寬度的 68%

    # 動態計算字體大小以符合目標寬度
    # 先用一個基準大小來測量寬度
    base_font_size = 10
    base_width = canvas.stringWidth(company_name, 'NotoSansCJKtc', base_font_size)
    
    # 根據比例計算理想的字體大小
    if base_width > 0:
        dynamic_font_size = (target_width / base_width) * base_font_size
    else:
        dynamic_font_size = 24 # 如果計算失敗，使用一個較大的預設值

    canvas.setFont('NotoSansCJKtc', dynamic_font_size)
    
    # 使用計算出的字體大小重新計算寬度和位置
    company_name_width = canvas.stringWidth(company_name, 'NotoSansCJKtc', dynamic_font_size)
    company_name_x = (page_width - company_name_width) / 2
    company_name_y = page_height - doc.topMargin + header_height - (0.5 * inch) # 稍微調整Y軸位置
    canvas.drawString(company_name_x, company_name_y, company_name)

    # 會議記錄標題
    record_text = title # 使用傳入的 title 參數
    canvas.setFont('NotoSansCJKtc', 18) # 字體加大 30%
    record_text_width = canvas.stringWidth(record_text, 'NotoSansCJKtc', 18)
    record_text_x = (page_width - record_text_width) / 2 # 置中
    record_text_y = company_name_y - 0.35 * inch # 與公司名稱保持固定間距，微調Y軸位置
    canvas.drawString(record_text_x, record_text_y, record_text)

    canvas.restoreState()

# 資料庫模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_key = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(100), nullable=True) # 新增單位欄位
    level = db.Column(db.String(50), nullable=False)
    avatar = db.Column(db.String(10), nullable=False)
    
    # 認證相關欄位
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    failed_login_attempts = db.Column(db.Integer, default=0)
    account_locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    must_change_password = db.Column(db.Boolean, default=True) # 新增首次登入強制修改密碼的旗標
    notification_enabled = db.Column(db.Boolean, nullable=False, default=True) # 通知功能開關
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # 直屬主管ID
    
    todos = db.relationship('Todo', backref='user', lazy=True, cascade='all, delete-orphan', foreign_keys='Todo.user_id')
    
    def set_password(self, password):
        """設置密碼雜湊"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """驗證密碼"""
        return check_password_hash(self.password_hash, password)
    
    def is_account_locked(self):
        """檢查帳戶是否被鎖定"""
        if self.account_locked_until:
            # 確保 self.account_locked_until 是時區感知型 (UTC) 以進行比較
            # 如果它是時區天真型，則假設它是 UTC 並進行本地化
            locked_until_aware = self.account_locked_until
            if locked_until_aware.tzinfo is None:
                locked_until_aware = utc.localize(locked_until_aware)
            return datetime.now(utc) < locked_until_aware
        return False
    
    def lock_account(self, minutes=30):
        """鎖定帳戶"""
        self.account_locked_until = datetime.now(utc) + timedelta(minutes=minutes)
        db.session.commit()
    
    def unlock_account(self):
        """解鎖帳戶"""
        self.failed_login_attempts = 0
        self.account_locked_until = None
        db.session.commit()
    
    def can_access_user_data(self, target_user_key):
        """檢查是否可以存取其他使用者的資料"""
        # 自己的資料總是可以存取
        if self.user_key == target_user_key:
            return True
        
        target_user = User.query.filter_by(user_key=target_user_key).first()
        if not target_user:
            return False # 目標使用者不存在

        current_level_value = LEVEL_ORDER.get(self.level, 0)
        target_level_value = LEVEL_ORDER.get(target_user.level, 0)

        # 系統管理員 (Admin) 可以看所有人
        if self.level == UserLevel.ADMIN.value:
            return True

        # 製造中心-協理 (Executive Manager) 可以看自己部門及下級
        if self.level == UserLevel.EXECUTIVE_MANAGER.value:
            return (target_user.department == self.department) or \
                   (target_level_value < current_level_value)

        # 廠長、經理、副理 (Plant Manager, Manager, Assistant Manager) 只能看自己單位的人員
        if self.level in [UserLevel.PLANT_MANAGER.value, UserLevel.MANAGER.value, UserLevel.ASSISTANT_MANAGER.value]:
            return target_user.department == self.unit

        # 課長、副課長 (Section Chief, Deputy Section Chief) 只能看自己單位以下的人員
        if self.level in [UserLevel.SECTION_CHIEF.value, UserLevel.DEPUTY_SECTION_CHIEF.value]:
            return (target_user.department == self.department and target_user.unit == self.unit) and \
                   (target_level_value < current_level_value)
        
        # 其他層級 (組長、作業員) 只能看自己的資料 (已在開頭處理)
        return False
    
    def can_modify_todo(self, todo):
        """檢查是否可以修改待辦事項"""
        # 自己的待辦事項總是可以修改
        if todo.user_id == self.id:
            return True
        
        # 上級可以修改下級的待辦事項
        todo_owner = db.session.get(User, todo.user_id)
        if todo_owner:
            return self.can_access_user_data(todo_owner.user_key)
        
        return False

    def can_assign_to(self, target_user):
        """檢查當前使用者是否可以指派任務給目標使用者"""
        level_hierarchy = LEVEL_ORDER

        current_level_value = level_hierarchy.get(self.level, 0)
        target_level_value = level_hierarchy.get(target_user.level, 0)

        # 管理員可以指派給任何人 (除了其他管理員)
        if self.level == UserLevel.ADMIN.value:
            return target_user.level != UserLevel.ADMIN.value

        # 製造中心-協理可以指派給任何人 (除了管理員)
        if self.level == UserLevel.EXECUTIVE_MANAGER.value:
            return target_user.level != UserLevel.ADMIN.value

        # 廠長、經理、副理的指派邏輯
        if self.level in [UserLevel.PLANT_MANAGER.value, UserLevel.MANAGER.value, UserLevel.ASSISTANT_MANAGER.value]:
            # 必須是層級低於自己的
            if target_level_value >= current_level_value:
                return False
            # 不能指派給管理員或協理
            if target_user.level in [UserLevel.ADMIN.value, UserLevel.EXECUTIVE_MANAGER.value]:
                return False

            # 檢查目標使用者是否在當前使用者所管理的範圍內
            # 對於這些角色，self.unit 代表他們所管理的部門或廠區
            managed_scope = self.unit 
            
            # 目標使用者的部門必須與當前使用者所管理的範圍相符
            return target_user.department == managed_scope

        # 課長可以指派給自己單位內的下級 (副課長、組長、作業員)
        if self.level == UserLevel.SECTION_CHIEF.value:
            return (self.department == target_user.department and self.unit == target_user.unit) and \
                   target_level_value < current_level_value

        # 副課長可以指派給自己單位內的下級 (組長、作業員)
        if self.level == UserLevel.DEPUTY_SECTION_CHIEF.value:
            return (self.department == target_user.department and self.unit == target_user.unit) and \
                   target_level_value < current_level_value

        # 組長可以指派給自己
        if self.level == UserLevel.TEAM_LEADER.value and self.id == target_user.id:
            return True

        # 作業員沒有指派權限
        if self.level == UserLevel.STAFF.value:
            return False
        
        return False

    def get_main_department(self):
        """根據用戶的部門和單位，判斷其所屬的主要管理部門"""
        if self.department == '製造中心':
            if self.unit in ['第一廠', '第三廠', '採購物流部', '品保部']:
                return self.unit
            elif self.unit in UNIT_TO_MAIN_DEPT_MAP:
                return UNIT_TO_MAIN_DEPT_MAP[self.unit]
        elif self.department in ['第一廠', '第三廠', '採購物流部', '品保部']:
            return self.department
        return self.department # Fallback

class Meeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=True) # 會議地點
    meeting_date = db.Column(db.DateTime, nullable=False)
    chairman_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recorder_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # 新增紀錄人員
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chairman = db.relationship('User', foreign_keys=[chairman_user_id], backref='chaired_meetings', lazy=True)
    recorder = db.relationship('User', foreign_keys=[recorder_user_id], backref='recorded_meetings', lazy=True)
    attendees = db.relationship('MeetingAttendee', backref='meeting', lazy=True, cascade='all, delete-orphan')
    discussion_items = db.relationship('DiscussionItem', backref='meeting', lazy=True, cascade='all, delete-orphan')

class MeetingAttendee(db.Model):
    meeting_id = db.Column(db.Integer, db.ForeignKey('meeting.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    
    user = db.relationship('User', backref='meeting_attendances', lazy=True)

class DiscussionItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meeting.id'), nullable=False, unique=True)
    topic = db.Column(db.Text, nullable=False)
    reporter_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reporter = db.relationship('User', foreign_keys=[reporter_user_id], backref='reported_discussion_items', lazy=True)
    

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=TodoStatus.PENDING.value)
    todo_type = db.Column(db.String(20), nullable=False)  # 'current' or 'next'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # 指派人
    history_log = db.Column(db.Text, nullable=True) # JSON-encoded list of event dictionaries
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=False) # 新增預計完成日期，不允許空白
    meeting_task_id = db.Column(db.Integer, db.ForeignKey('meeting_task.id'), nullable=True) # 連結到會議任務

    assigned_by = db.relationship('User', foreign_keys=[assigned_by_user_id], backref='assigned_todos', lazy=True)

class ArchivedTodo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_todo_id = db.Column(db.Integer, nullable=False) # Original ID from Todo table
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False) # Should be 'completed' when archived
    todo_type = db.Column(db.String(20), nullable=False) # Should be 'current' when archived
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    history_log = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False) # Original creation time
    updated_at = db.Column(db.DateTime, nullable=False) # Original last update time
    archived_at = db.Column(db.DateTime, default=datetime.utcnow) # When it was archived
    due_date = db.Column(db.DateTime, nullable=True) # 新增預計完成日期

class MeetingTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meeting.id'), nullable=False) # 新增會議ID，直接關聯到會議
    task_type = db.Column(db.String(50), nullable=False) # 任務類型 (追蹤項目/決議項目)
    task_description = db.Column(db.Text, nullable=False) # 任務事項
    assigned_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # 指派人員 (創建此會議任務的人)
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # 負責人員 (主辦者)
    
    controller_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # 管制人員 (可選)
    expected_completion_date = db.Column(db.DateTime, nullable=True) # 預計完成日期 (追蹤項目可為空)
    actual_completion_date = db.Column(db.DateTime, nullable=True) # 實際完成日期 (Todo 完成後回填)
    uncompleted_reason_from_todo = db.Column(db.Text, nullable=True) # 新增未完成原因欄位
    status = db.Column(db.String(50), nullable=False, default=MeetingTaskStatus.UNASSIGNED.value) # 會議任務狀態
    is_assigned_to_todo = db.Column(db.Boolean, default=False) # 追蹤項目是否已指派到 Todo
    todo_id = db.Column(db.Integer, db.ForeignKey('todo.id'), unique=True, nullable=True) # 連結到 Todo 任務
    history_log = db.Column(db.Text, nullable=True) # JSON-encoded list of event dictionaries
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 關聯到 User 模型
    assigned_by_user = db.relationship('User', foreign_keys=[assigned_by_user_id], backref='assigned_meeting_tasks', lazy=True)
    assigned_to_user = db.relationship('User', foreign_keys=[assigned_to_user_id], backref='received_meeting_tasks', lazy=True)
    
    controller_user = db.relationship('User', foreign_keys=[controller_user_id], backref='controlled_meeting_tasks', lazy=True)
    meeting = db.relationship('Meeting', backref='meeting_tasks', lazy=True)
    
    # 關聯到 Todo 模型
    todo = db.relationship('Todo', foreign_keys=[todo_id], backref='meeting_task_link', uselist=False)

class ReportSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    department = db.Column(db.String(100), nullable=False) # 這裡指的是要報告的課別/單位
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    schedule_day = db.Column(db.Integer, nullable=False)  # 0-6 for Mon-Sun
    schedule_time = db.Column(db.Time, nullable=False)
    last_sent_at = db.Column(db.DateTime, nullable=True)
    require_next_week_tasks = db.Column(db.Boolean, default=False, nullable=False) # 新增欄位
    
    manager = db.relationship('User', foreign_keys=[manager_id], backref=db.backref('report_schedules', lazy=True))

class ScheduledNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Creator of the notification
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    recipient_user_ids = db.Column(db.String(500), nullable=False) # Comma-separated user IDs
    schedule_type = db.Column(db.String(20), nullable=False) # 'one_time', 'weekly'
    specific_date = db.Column(db.Date, nullable=True) # For one_time schedules
    specific_time = db.Column(db.Time, nullable=False) # For both schedule types
    weekly_day = db.Column(db.Integer, nullable=True) # 0-6 for Mon-Sun, for weekly schedules
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], backref='created_notifications', lazy=True)

init_app_scheduler(app, db, User, Todo, ArchivedTodo, MeetingTask, Meeting, ScheduledNotification, ReportSchedule) # Initialize scheduler after models are defined

# 認證裝飾器
def login_required(f):
    """要求登入的裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # 檢查使用者是否仍然存在且啟用
        user = db.session.get(User, session['user_id'])
        if not user or not user.is_active:
            session.clear()
            flash('您的帳戶已被停用，請聯繫管理員', 'error')
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """要求管理員權限的裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        user = db.session.get(User, session['user_id'])
        if not user or user.level not in [UserLevel.ADMIN.value, UserLevel.EXECUTIVE_MANAGER.value]:
            flash('您沒有權限執行此操作', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    """要求超級管理員權限的裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # For API endpoints, return JSON error instead of redirecting
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': '未經授權，請重新登入'}), 401
            return redirect(url_for('login'))
        
        user = db.session.get(User, session['user_id'])
        if not user or user.level != UserLevel.ADMIN.value:
            # For API endpoints, return JSON error instead of redirecting
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': '您沒有權限執行此操作'}), 403
            flash('您沒有權限執行此操作', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """取得當前登入使用者"""
    if 'user_id' in session:
        return db.session.get(User, session['user_id'])
    return None

# 路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('請輸入電子郵件和密碼', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('電子郵件或密碼錯誤', 'error')
            return render_template('login.html')
        
        # 檢查帳戶是否被鎖定
        if user.is_account_locked():
            flash('帳戶已被鎖定，請稍後再試或聯繫管理員', 'error')
            return render_template('login.html')
        
        # 檢查帳戶是否啟用
        if not user.is_active:
            flash('帳戶已被停用，請聯繫管理員', 'error')
            return render_template('login.html')
        
        # 驗證密碼
        if user.check_password(password):
            # 登入成功
            session['user_id'] = user.id
            session['user_key'] = user.user_key
            session['user_level'] = user.level
            
            # 重置失敗嘗試次數並更新最後登入時間
            user.failed_login_attempts = 0
            user.last_login = datetime.now(utc)
            db.session.commit()
            
            flash(f'歡迎回來，{user.name}！', 'success')
            
            # 檢查是否需要強制修改密碼
            if user.must_change_password:
                flash('您是首次登入或管理員要求，請先修改密碼。', 'info')
                return redirect(url_for('change_password'))

            # 如果是管理員，導向到管理員頁面
            if user.level == UserLevel.ADMIN.value:
                return redirect(url_for('admin_users'))
            else:
                return redirect(url_for('index'))
        else:
            # 登入失敗
            user.failed_login_attempts += 1
            
            # 如果失敗次數超過限制，鎖定帳戶
            if user.failed_login_attempts >= LOGIN_ATTEMPTS_LIMIT:
                user.lock_account(ACCOUNT_LOCK_MINUTES)  # 鎖定指定分鐘
                flash(f'登入失敗次數過多，帳戶已被鎖定{ACCOUNT_LOCK_MINUTES}分鐘', 'error')
            else:
                remaining_attempts = LOGIN_ATTEMPTS_LIMIT - user.failed_login_attempts
                flash(f'密碼錯誤，還有 {remaining_attempts} 次嘗試機會', 'error')
            
            db.session.commit()
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('您已成功登出', 'info')
    return redirect(url_for('login'))

@app.route('/user_settings', methods=['GET', 'POST'])
@login_required
def user_settings():
    current_user = get_current_user()
    if request.method == 'POST':
        # If checkbox is checked, 'notification_enabled' will be in request.form.
        # If unchecked, it will not be present.
        new_notification_status = 'notification_enabled' in request.form
        
        current_user.notification_enabled = new_notification_status # 處理通知開關
        try:
            db.session.commit()
            flash('您的通知設定已更新！', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'更新通知設定時發生錯誤: {str(e)}', 'error')
        return redirect(url_for('user_settings'))
    return render_template('user_settings.html', current_user=current_user)

@app.route('/report-settings', methods=['GET', 'POST'])
@login_required
def report_settings():
    current_user = get_current_user()
    
    # 修正：可管理的單位應該包含主管自己所在的單位，以及他所有下屬的單位
    units = set()
    
    # Always add the current user's unit
    if current_user.unit:
        units.add(current_user.unit)

    # If the current user is a Plant Manager or Manager, include all units under their main unit
    if current_user.level in [UserLevel.EXECUTIVE_MANAGER.value, UserLevel.PLANT_MANAGER.value, UserLevel.MANAGER.value]:
        # For Executive Manager, Plant Manager, Manager:
        # Include their own unit and all units that map to their unit in UNIT_TO_MAIN_DEPT_MAP
        main_unit_of_manager = current_user.unit # e.g., '第一廠', '採購物流部'
        if main_unit_of_manager:
            for unit_name, mapped_main_dept in UNIT_TO_MAIN_DEPT_MAP.items():
                if mapped_main_dept == main_unit_of_manager:
                    units.add(unit_name)
            # Also add the main department itself if it's a top-level department
            if main_unit_of_manager in DEPARTMENT_STRUCTURE:
                units.add(main_unit_of_manager)
    else:
        # For other roles, include units of direct subordinates
        subordinates = User.query.filter_by(manager_id=current_user.id).all()
        for s in subordinates:
            if s.unit:
                units.add(s.unit)
            
    manageable_units = sorted(list(units))

    if request.method == 'POST':
        department_unit = request.form.get('department_unit')
        schedule_day = request.form.get('schedule_day')
        schedule_time_str = request.form.get('schedule_time')

        if not all([department_unit, schedule_day, schedule_time_str]):
            flash('所有欄位都是必填的！', 'error')
        else:
            try:
                # 檢查是否已存在相同的排程
                existing_schedule = ReportSchedule.query.filter_by(
                    manager_id=current_user.id,
                    department=department_unit
                ).first()

                if existing_schedule:
                    flash(f'您已經為「{department_unit}」建立過排程了。', 'warning')
                else:
                    schedule_time = dt_time.fromisoformat(schedule_time_str)
                    require_next_week_tasks = 'require_next_week_tasks' in request.form # Check if checkbox is present
                    new_schedule = ReportSchedule(
                        manager_id=current_user.id,
                        department=department_unit,
                        is_active=True,
                        schedule_day=int(schedule_day),
                        schedule_time=schedule_time,
                        require_next_week_tasks=require_next_week_tasks # Save the new setting
                    )
                    db.session.add(new_schedule)
                    db.session.commit()
                    flash(f'已成功為「{department_unit}」新增週報排程！', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'新增排程時發生錯誤: {e}', 'error')
        
        return redirect(url_for('report_settings'))

    # GET 請求：顯示現有排程
    schedules = ReportSchedule.query.filter_by(manager_id=current_user.id).order_by(ReportSchedule.department).all()
    return render_template('report_settings.html', schedules=schedules, manageable_units=manageable_units)


@app.route('/report-settings/edit/<int:schedule_id>', methods=['GET', 'POST'])
@login_required
def edit_report_schedule(schedule_id):
    current_user = get_current_user()
    schedule_to_edit = db.session.get(ReportSchedule, schedule_id)

    if not schedule_to_edit:
        flash('找不到該排程！', 'error')
        return redirect(url_for('report_settings'))

    # Ensure the current user has permission to edit this schedule
    if schedule_to_edit.manager_id != current_user.id and current_user.level != UserLevel.ADMIN.value:
        flash('您沒有權限編輯此排程！', 'error')
        return redirect(url_for('report_settings'))

    # Re-calculate manageable units for the form
    units = set()
    if current_user.unit:
        units.add(current_user.unit)
    if current_user.level in [UserLevel.EXECUTIVE_MANAGER.value, UserLevel.PLANT_MANAGER.value, UserLevel.MANAGER.value]:
        main_unit_of_manager = current_user.unit
        if main_unit_of_manager:
            for unit_name, mapped_main_dept in UNIT_TO_MAIN_DEPT_MAP.items():
                if mapped_main_dept == main_unit_of_manager:
                    units.add(unit_name)
            if main_unit_of_manager in DEPARTMENT_STRUCTURE:
                units.add(main_unit_of_manager)
    else:
        subordinates = User.query.filter_by(manager_id=current_user.id).all()
        for s in subordinates:
            if s.unit:
                units.add(s.unit)
    manageable_units = sorted(list(units))

    if request.method == 'POST':
        department_unit = request.form.get('department_unit')
        schedule_day = request.form.get('schedule_day')
        schedule_time_str = request.form.get('schedule_time')
        require_next_week_tasks = 'require_next_week_tasks' in request.form

        if not all([department_unit, schedule_day, schedule_time_str]):
            flash('所有欄位都是必填的！', 'error')
        else:
            try:
                schedule_to_edit.department = department_unit
                schedule_to_edit.schedule_day = int(schedule_day)
                schedule_to_edit.schedule_time = dt_time.fromisoformat(schedule_time_str)
                schedule_to_edit.require_next_week_tasks = require_next_week_tasks
                
                db.session.commit()
                flash('排程已成功更新！', 'success')
                return redirect(url_for('report_settings'))
            except Exception as e:
                db.session.rollback()
                flash(f'更新排程時發生錯誤: {e}', 'error')
        
        # If there was an error, re-render the edit form with current data
        schedules = ReportSchedule.query.filter_by(manager_id=current_user.id).order_by(ReportSchedule.department).all()
        return render_template('report_settings.html', 
                               schedules=schedules, 
                               manageable_units=manageable_units, 
                               editing_schedule=schedule_to_edit, # Pass the schedule being edited
                               editing_schedule_id=schedule_id) # Indicate edit mode
    
    # GET request for edit mode
    schedules = ReportSchedule.query.filter_by(manager_id=current_user.id).order_by(ReportSchedule.department).all()
    return render_template('report_settings.html', 
                           schedules=schedules, 
                           manageable_units=manageable_units, 
                           editing_schedule=schedule_to_edit, # Pass the schedule being edited
                           editing_schedule_id=schedule_id) # Indicate edit mode


@app.route('/api/report_schedule/<int:schedule_id>', methods=['DELETE'])
@login_required
def delete_report_schedule(schedule_id):
    current_user = get_current_user()
    schedule = db.session.get(ReportSchedule, schedule_id)

    if not schedule:
        return jsonify({'error': '找不到該排程'}), 404

    if schedule.manager_id != current_user.id and current_user.level != UserLevel.ADMIN.value:
        return jsonify({'error': '您沒有權限刪除此排程'}), 403

    try:
        db.session.delete(schedule)
        db.session.commit()
        return jsonify({'message': '排程已成功刪除'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'刪除排程時發生錯誤: {e}'}), 500

@app.route('/api/report_schedule/<int:schedule_id>/toggle', methods=['POST'])
@login_required
def toggle_report_schedule(schedule_id):
    current_user = get_current_user()
    schedule = db.session.get(ReportSchedule, schedule_id)

    if not schedule:
        return jsonify({'error': '找不到該排程'}), 404

    if schedule.manager_id != current_user.id and current_user.level != UserLevel.ADMIN.value:
        return jsonify({'error': '您沒有權限修改此排程'}), 403

    try:
        schedule.is_active = not schedule.is_active
        db.session.commit()
        return jsonify({'message': '排程狀態已更新', 'is_active': schedule.is_active}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'更新排程狀態時發生錯誤: {e}'}), 500

@app.route('/api/report_schedule/<int:schedule_id>/send_now', methods=['POST'])
@login_required
def send_report_now(schedule_id):
    current_user = get_current_user()
    schedule = db.session.get(ReportSchedule, schedule_id)

    if not schedule:
        return jsonify({'error': '找不到該排程'}), 404

    if schedule.manager_id != current_user.id and current_user.level != UserLevel.ADMIN.value:
        return jsonify({'error': '您沒有權限執行此操作'}), 403

    try:
        generate_and_send_weekly_report(app, db, User, Todo, ReportSchedule, schedule.id, is_manual_send=True)
        return jsonify({'message': '報告已成功觸發發送，請稍後檢查您的信箱。'}), 200
    except Exception as e:
        logging.error(f"手動發送報告時發生錯誤 (schedule_id: {schedule_id}): {e}", exc_info=True)
        return jsonify({'error': f'手動發送報告時發生錯誤: {str(e)}'}), 500


def _build_organization_structure(all_users, user_todos_map, user_overdue_map, director):
    # 定義組織階層的順序，用於排序
    level_order = LEVEL_ORDER

    # 定義新的組織結構，以四大部門為基礎 (使用深複製)
    department_structure = copy.deepcopy(DEPARTMENT_STRUCTURE)

    # 輔助對應表：將資料庫中的單位(課)對應到四大部門
    unit_to_main_dept_map = UNIT_TO_MAIN_DEPT_MAP

    # 將 director 加入組織結構
    if director:
        main_dept_name = None
        if director.department == '製造中心':
            if director.unit in ['第一廠', '第三廠', '採購物流部', '品保部']:
                main_dept_name = director.unit
            elif director.unit in unit_to_main_dept_map:
                main_dept_name = unit_to_main_dept_map[director.unit]
        elif director.department in ['第一廠', '第三廠', '採購物流部', '品保部']:
            main_dept_name = director.department

        if main_dept_name and main_dept_name in department_structure:
            department_structure[main_dept_name]['management_team'].append(director)

    for user in all_users:
        # 如果當前用戶是協理，則跳過，因為協理已在前面處理過
        if director and user.user_key == director.user_key:
            continue
        user_current_todos = user_todos_map.get(user.id, [])
        user.total_tasks = len(user_current_todos)
        user.completed_tasks = sum(1 for todo in user_current_todos if todo.status == TodoStatus.COMPLETED.value)
        user.overdue_tasks = user_overdue_map.get(user.id, 0) # 獲取逾期任務計數

        main_dept_name = None
        
        # 根據用戶的部門和單位，判斷其所屬的主要部門
        if user.department == '製造中心':
            if user.unit in ['第一廠', '第三廠', '採購物流部', '品保部']:
                main_dept_name = user.unit  # 廠長/經理級別，直接歸屬到四大部門
            elif user.unit in unit_to_main_dept_map:
                main_dept_name = unit_to_main_dept_map[user.unit] # 課級或以下，歸屬到對應的廠
        elif user.department in ['第一廠', '第三廠', '採購物流部', '品保部']:
            main_dept_name = user.department # 如果部門本身就是四大部門之一，直接使用部門名稱

        if not main_dept_name or main_dept_name not in department_structure:
            continue

        # 將用戶放入對應的結構中
        dept_data = department_structure[main_dept_name]

        # 1. 分配部門主管 (廠長/經理/副理)
        if user.level in [UserLevel.PLANT_MANAGER.value, UserLevel.MANAGER.value, UserLevel.ASSISTANT_MANAGER.value]:
            # 避免重複添加 director
            if user.user_key != director.user_key if director else False:
                dept_data['management_team'].append(user)
        
        # 2. 分配單位(課)內成員
        elif user.unit:
            unit_name = user.unit
            if unit_name not in dept_data['units']:
                dept_data['units'][unit_name] = {'management_team': [], 'leaders': [], 'staff': []}
            
            unit_data = dept_data['units'][unit_name]
            if user.level in [UserLevel.SECTION_CHIEF.value, UserLevel.DEPUTY_SECTION_CHIEF.value]:
                unit_data['management_team'].append(user)
            elif user.level == UserLevel.TEAM_LEADER.value:
                unit_data['leaders'].append(user)
            elif user.level == UserLevel.STAFF.value:
                unit_data['staff'].append(user)
        
        # 3. 分配部門內無明確單位的成員 (主要針對品保部/採購部)
        else:
            unit_name = "部門直屬"
            if unit_name not in dept_data['units']:
                dept_data['units'][unit_name] = {'management_team': [], 'leaders': [], 'staff': []}
            
            # 將非主管級別的用戶放入
            if user.level not in [UserLevel.MANAGER.value, UserLevel.ASSISTANT_MANAGER.value]:
                 dept_data['units'][unit_name]['staff'].append(user)


    # 對每個部門和單位內的成員進行排序
    for dept_data in department_structure.values():
        dept_data['management_team'].sort(key=lambda x: LEVEL_ORDER.get(x.level, 99))
        for unit_data in dept_data['units'].values():
            unit_data['management_team'].sort(key=lambda x: LEVEL_ORDER.get(x.level, 99))
            unit_data['leaders'].sort(key=lambda x: LEVEL_ORDER.get(x.level, 99))
            unit_data['staff'].sort(key=lambda x: LEVEL_ORDER.get(x.level, 99))
    
    return department_structure

@app.route('/')
@login_required
def index():
    current_user = get_current_user()
    
    # 優化 N+1 查詢：一次性獲取所有使用者的本週任務
    all_current_todos = Todo.query.filter_by(todo_type=TodoType.CURRENT.value).all()
    user_todos_map = {}
    for todo in all_current_todos:
        if todo.user_id not in user_todos_map:
            user_todos_map[todo.user_id] = []
        user_todos_map[todo.user_id].append(todo)

    # 新增：一次性獲取所有逾期任務
    # 獲取今天的開始時間 (UTC)
    today_start_of_day_utc = datetime.now(utc).replace(hour=0, minute=0, second=0, microsecond=0)
    overdue_todos = Todo.query.filter(
        Todo.due_date < today_start_of_day_utc, # 逾期任務不包含今天
        Todo.status != TodoStatus.COMPLETED.value
    ).all()
    user_overdue_map = {}
    for todo in overdue_todos:
        if todo.user_id not in user_overdue_map:
            user_overdue_map[todo.user_id] = 0
        user_overdue_map[todo.user_id] += 1

    # 最高層級主管 (製造中心-協理)
    director = User.query.filter_by(level=UserLevel.EXECUTIVE_MANAGER.value).first()
    if director:
        director_current_todos = user_todos_map.get(director.id, [])
        director.total_tasks = len(director_current_todos)
        director.completed_tasks = sum(1 for todo in director_current_todos if todo.status == TodoStatus.COMPLETED.value)
        director.overdue_tasks = user_overdue_map.get(director.id, 0)
    
    all_users = User.query.filter(User.level != UserLevel.ADMIN.value).all()

    departments = _build_organization_structure(all_users, user_todos_map, user_overdue_map, director)

    return render_template('index.html', 
                           director=director, 
                           departments=departments, 
                           current_user=current_user)

@app.route('/api/user/<user_key>')
@login_required
def get_user_detail(user_key):
    current_user = get_current_user()
    
    # 檢查權限
    if not current_user.can_access_user_data(user_key):
        return jsonify({'error': 'Access denied'}), 403
    
    user = User.query.filter_by(user_key=user_key).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # 查詢並依 due_date 排序
    # 優先將已完成的任務排在最後，然後再依 due_date 排序
    current_todos = Todo.query.filter_by(user_id=user.id, todo_type=TodoType.CURRENT.value).order_by(
            db.case(
                (Todo.status == TodoStatus.COMPLETED.value, 1),
                else_=0
            ),
            Todo.due_date
        ).all()
    next_todos = Todo.query.filter_by(user_id=user.id, todo_type=TodoType.NEXT.value).order_by(
            db.case(
                (Todo.status == TodoStatus.COMPLETED.value, 1),
                else_=0
            ),
            Todo.due_date
        ).all()
    
    def format_todo(todo):
        assigned_by_info = None
        if todo.assigned_by:
            assigned_by_info = {
                'name': todo.assigned_by.name,
                'role': todo.assigned_by.role,
                'level': todo.assigned_by.level,
                'user_key': todo.assigned_by.user_key
            }
        return {
            'id': todo.id,
            'title': todo.title,
            'description': todo.description,
            'status': todo.status,
            'due_date': todo.due_date.isoformat() if todo.due_date else None, # 包含 due_date
            'history_log': [
                {
                    **entry, 
                    'timestamp': (lambda ts: 
                        (utc.localize(datetime.fromisoformat(ts)) if datetime.fromisoformat(ts).tzinfo is None else datetime.fromisoformat(ts))
                        .astimezone(timezone('Asia/Taipei')).strftime('%Y/%m/%d %H:%M')
                    )(entry['timestamp']) if 'timestamp' in entry and entry['timestamp'] else entry.get('timestamp')
                }
                for entry in json.loads(todo.history_log)
            ] if todo.history_log else [],
            'assigned_by': assigned_by_info,
            'assignee_user_key': user.user_key,
            'assigner_user_key': todo.assigned_by.user_key if todo.assigned_by else None,
            'can_edit_status': current_user.id == todo.user_id
        }

    return jsonify({
        'user': {
            'name': user.name,
            'role': user.role,
            'department': user.department,
            'unit': user.unit, # 新增 unit 欄位
            'avatar': user.avatar
        },
        'todos': {
            'current': [format_todo(t) for t in current_todos],
            'next': [format_todo(t) for t in next_todos]
        },
        'permissions': {
            'can_modify': current_user.user_key == user_key or current_user.can_access_user_data(user_key),
            'can_assign': current_user.level in [UserLevel.ADMIN.value, UserLevel.EXECUTIVE_MANAGER.value, UserLevel.PLANT_MANAGER.value, UserLevel.MANAGER.value, UserLevel.SECTION_CHIEF.value, UserLevel.TEAM_LEADER.value],
            'assignable_users': [{'user_key': u.user_key, 'name': u.name, 'role': u.role} for u in User.query.all() if current_user.can_assign_to(u)]
        }
    })

@app.route('/api/todo', methods=['POST'])
@login_required
def add_todo():
    current_user = get_current_user()
    data = request.get_json()
    
    target_user_key = data.get('user_key')
    
    # 如果沒有指定 user_key，則預設為當前使用者
    if not target_user_key:
        target_user = current_user
    else:
        target_user = User.query.filter_by(user_key=target_user_key).first()
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        
        # 檢查指派權限
        if target_user.id != current_user.id and not current_user.can_assign_to(target_user):
            return jsonify({'error': '您沒有權限指派任務給此使用者'}), 403
    
    # 驗證輸入資料，確保 title, description, type, due_date 都存在
    if not all(key in data for key in ['title', 'description', 'type', 'due_date']):
        return jsonify({'error': 'Missing required fields (title, description, type, due_date)'}), 400
    
    try:
        # 將 due_date 字串轉換為 datetime 物件
        due_date = datetime.fromisoformat(data['due_date']).replace(tzinfo=utc)
    except ValueError:
        return jsonify({'error': 'Invalid due_date format. Use ISO format (YYYY-MM-DD).'}), 400

    todo = Todo(
        title=data['title'],
        description=data['description'],
        status=TodoStatus.PENDING.value, # 直接指定為「待開始」
        todo_type=data['type'],
        user_id=target_user.id,
        assigned_by_user_id=current_user.id if target_user.id != current_user.id else None, # 如果是指派，記錄指派人
        due_date=due_date # 設定預計完成日期
    )
    
    # 初始化 history_log
    history_entry = {
        'event_type': 'assigned',
        'timestamp': datetime.now(utc).isoformat(),
        'actor': {'id': current_user.id, 'name': current_user.name, 'user_key': current_user.user_key},
        'details': {'assigned_to': {'id': target_user.id, 'name': target_user.name, 'user_key': target_user.user_key}}
    }
    if todo.assigned_by_user_id: # If it was assigned by someone else
        history_entry['details']['assigned_by'] = {'id': current_user.id, 'name': current_user.name, 'user_key': current_user.user_key}
    
    todo.history_log = json.dumps([history_entry])
    
    db.session.add(todo)
    db.session.commit()
    
    # 發送「收到指派任務」通知
    try:
        # 檢查是否為他人指派，且對方已啟用通知
        if target_user.id != current_user.id and target_user.notification_enabled:
            subject = f"[新任務指派] {todo.title}"
            body = (
                f"您好 {target_user.name}，<br><br>"
                f"您被 {current_user.name} 指派了一項新任務。<br><br>"
                f"<b>任務標題:</b> {todo.title}<br>"
                f"<b>任務描述:</b><br>{todo.description.replace('\n', '<br>')}<br><br>"
                f"<b>預計完成日期:</b> {todo.due_date.strftime('%Y-%m-%d')}<br><br>"
                f"請登入系統查看：<br><a href='http://192.168.6.119:5001'>http://192.168.6.119:5001</a>"
            )
            send_mail(subject, body, target_user.email)
            logging.info(f"Sent 'new task' notification for task {todo.id} to {target_user.email}")
    except Exception as e:
        logging.error(f"Failed to send 'new task' notification for task {todo.id}: {e}")
    
    return jsonify({'message': 'Todo added successfully', 'id': todo.id})

@app.route('/api/batch_add_todo', methods=['POST'])
@login_required
def batch_add_todo():
    current_user = get_current_user()
    data = request.get_json()
    
    user_keys = data.get('user_keys')
    if not user_keys or not isinstance(user_keys, list):
        return jsonify({'error': 'Missing or invalid user_keys (must be a list)'}), 400

    # 驗證輸入資料，確保 title, description, type, due_date 都存在
    if not all(key in data for key in ['title', 'description', 'type', 'due_date']):
        return jsonify({'error': 'Missing required fields (title, description, type, due_date)'}), 400
    
    try:
        # 將 due_date 字串轉換為 datetime 物件
        due_date = datetime.fromisoformat(data['due_date'])
    except ValueError:
        return jsonify({'error': 'Invalid due_date format. Use ISO format (YYYY-MM-DD).'}), 400

    successful_assignments = []
    failed_assignments = []

    for user_key in user_keys:
        target_user = User.query.filter_by(user_key=user_key).first()
        if not target_user:
            failed_assignments.append({'user_key': user_key, 'reason': 'User not found'})
            continue
        
        # 檢查指派權限
        if target_user.id != current_user.id and not current_user.can_assign_to(target_user):
            failed_assignments.append({'user_key': user_key, 'reason': 'Permission denied'})
            continue

        todo = Todo(
            title=data['title'],
            description=data['description'],
            status=TodoStatus.PENDING.value, # 直接指定為「待開始」
            todo_type=data['type'],
            user_id=target_user.id,
            assigned_by_user_id=current_user.id if target_user.id != current_user.id else None, # 如果是指派，記錄指派人
            due_date=due_date # 設定預計完成日期
        )
        
        # 初始化 history_log
        history_entry = {
            'event_type': 'assigned',
            'timestamp': datetime.now(utc).isoformat(),
            'actor': {'id': current_user.id, 'name': current_user.name, 'user_key': current_user.user_key},
            'details': {'assigned_to': {'id': target_user.id, 'name': target_user.name, 'user_key': target_user.user_key}}
        }
        if todo.assigned_by_user_id: # If it was assigned by someone else
            history_entry['details']['assigned_by'] = {'id': current_user.id, 'name': current_user.name, 'user_key': current_user.user_key}
        
        todo.history_log = json.dumps([history_entry])
        
        db.session.add(todo)
        successful_assignments.append({'user_key': user_key, 'id': todo.id})
        
        # 發送「收到指派任務」通知
        # 只有當指派對象不是當前使用者本人，且對方已啟用通知時才發送
        if target_user.id != current_user.id and target_user.email and target_user.notification_enabled:
            try:
                subject = f"[新任務指派] {data['title']}"
                body = (
                    f"您好 {target_user.name}，<br><br>"
                    f"您被 {current_user.name} 指派了一項新任務。<br><br>"
                    f"<b>任務標題:</b> {data['title']}<br>"
                    f"<b>任務描述:</b><br>{data['description'].replace('\n', '<br>')}<br><br>"
                    f"<b>預計完成日期:</b> {due_date.strftime('%Y-%m-%d')}<br><br>"
                    f"請登入系統查看：<br><a href='http://192.168.6.119:5001'>http://192.168.6.119:5001</a>"
                )
                send_mail(subject, body, target_user.email)
                logging.info(f"Sent 'new task' notification for batch-added task to {target_user.email}")
            except Exception as e:
                logging.error(f"Failed to send 'new task' notification for batch-added task to {target_user.email}: {e}")

    try:
        db.session.commit()
        message = f'成功指派 {len(successful_assignments)} 個任務。'
        if failed_assignments:
            message += f' {len(failed_assignments)} 個任務指派失敗。'
        return jsonify({'message': message, 'successful_assignments': successful_assignments, 'failed_assignments': failed_assignments})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'批量指派任務時發生錯誤: {str(e)}'}), 500

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_user = get_current_user()
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([current_password, new_password, confirm_password]):
            flash('請填寫所有欄位', 'error')
            return render_template('change_password.html')
        
        if not current_user.check_password(current_password):
            flash('目前密碼錯誤', 'error')
            return render_template('change_password.html')
        
        if new_password != confirm_password:
            flash('新密碼與確認密碼不符', 'error')
            return render_template('change_password.html')
        
        if len(new_password) < 6:
            flash('密碼長度至少需要6個字元', 'error')
            return render_template('change_password.html')
        
        current_user.set_password(new_password)
        current_user.must_change_password = False # 密碼修改成功後，將此旗標設為 False
        db.session.commit()
        
        flash('密碼已成功更新', 'success')
        return redirect(url_for('index'))
    
    return render_template('change_password.html')

@app.route('/api/dept-stats')
def get_dept_stats():
    users = User.query.filter(User.level != UserLevel.ADMIN.value).all()
    dept_stats = {}
    
    for user in users:
        dept = user.department
        if dept not in dept_stats:
            dept_stats[dept] = {'total': 0, 'completed': 0}
        
        current_todos = Todo.query.filter_by(user_id=user.id, todo_type=TodoType.CURRENT.value).all()
        for todo in current_todos:
            dept_stats[dept]['total'] += 1
            if todo.status == TodoStatus.COMPLETED.value:
                dept_stats[dept]['completed'] += 1
    
    # 計算完成率
    for dept in dept_stats:
        if dept_stats[dept]['total'] > 0:
            dept_stats[dept]['completion_rate'] = round(
                (dept_stats[dept]['completed'] / dept_stats[dept]['total']) * 100
            )
        else:
            dept_stats[dept]['completion_rate'] = 0
    
    return jsonify(dept_stats)

@app.route('/api/export')
def export_data():
    users = User.query.all()
    export_data = {
        'export_date': datetime.now().isoformat(),
        'users': []
    }
    
    for user in users:
        current_todos = Todo.query.filter_by(user_id=user.id, todo_type=TodoType.CURRENT.value).all()
        next_todos = Todo.query.filter_by(user_id=user.id, todo_type=TodoType.NEXT.value).all()
        
        user_data = {
            'name': user.name,
            'role': user.role,
            'department': user.department,
            'todos': {
                'current': [{'title': t.title, 'description': t.description, 'status': t.status} for t in current_todos],
                'next': [{'title': t.title, 'description': t.description, 'status': t.status} for t in next_todos]
            }
        }
        export_data['users'].append(user_data)
    
    return jsonify(export_data)

@app.route('/api/org-structure')
def get_org_structure():
    departments_list = ['製造中心', '採購物流部', '品保部', '第一廠', '第三廠']
    units_map = {
        '製造中心': ['第一廠', '第三廠','採購物流部', '品保部'],
        '第一廠': ['裝一課', '裝二課', '組件課'],
        '第三廠': ['裝三課','加工課' ],
        '採購物流部': ['資材成本課', '資材管理課'],
        '品保部': ['品管課']
    }
    return jsonify({'departments': departments_list, 'units': units_map})

def _generate_report_data(start_date, end_date):
    # 查詢指定日期範圍內歸檔的任務
    archived_todos = ArchivedTodo.query.filter(
        ArchivedTodo.archived_at >= start_date,
        ArchivedTodo.archived_at <= end_date
    ).all()

    report_data = {}
    for todo in archived_todos:
        user = db.session.get(User, todo.user_id)
        if user:
            if user.department not in report_data:
                report_data[user.department] = {
                    'total_tasks': 0,
                    'completed_tasks': 0,
                    'uncompleted_tasks': 0,
                    'users': {}
                }
            
            dept_data = report_data[user.department]
            if user.user_key not in dept_data['users']:
                dept_data['users'][user.user_key] = {
                    'name': user.name,
                    'role': user.role,
                    'total_tasks': 0,
                    'completed_tasks': 0,
                    'uncompleted_tasks': 0,
                    'tasks': []
                }
            
            user_data = dept_data['users'][user.user_key]

            dept_data['total_tasks'] += 1
            user_data['total_tasks'] += 1

            if todo.status == TodoStatus.COMPLETED.value:
                dept_data['completed_tasks'] += 1
                user_data['completed_tasks'] += 1
            else:
                dept_data['uncompleted_tasks'] += 1
                user_data['uncompleted_tasks'] += 1
            
            processed_history_log = []
            if todo.history_log:
                try:
                    history_entries = json.loads(todo.history_log)
                    for entry in history_entries:
                        if isinstance(entry, dict) and 'timestamp' in entry and entry['timestamp']:
                            try:
                                formatted_timestamp = isoparse(entry['timestamp']).astimezone(utc).astimezone(timezone('Asia/Taipei')).strftime('%Y/%m/%d %H:%M')
                                processed_history_log.append({**entry, 'timestamp': formatted_timestamp})
                            except ValueError:
                                logging.warning(f"Invalid timestamp format in history_log for todo ID {todo.id}: {entry.get('timestamp')}")
                                processed_history_log.append({**entry, 'timestamp': 'Invalid Timestamp'})
                        else:
                            processed_history_log.append(entry) # Keep entry as is if not a dict or no timestamp
                except Exception as e: # Catch any exception during history_log processing
                    logging.error(f"Error processing history_log for todo ID {todo.id}: {todo.history_log}. Error: {e}")
                    processed_history_log = [{'event_type': 'error', 'details': f'Error processing history log: {e}'}]

            user_data['tasks'].append({
                'title': todo.title,
                'description': todo.description,
                'status': todo.status,
                'archived_at': utc.localize(todo.archived_at).astimezone(timezone('Asia/Taipei')).strftime('%Y/%m/%d %H:%M') if todo.archived_at else None,
                'history_log': processed_history_log
            })
    
    # 計算完成率
    for dept in report_data.values():
        if dept['total_tasks'] > 0:
            dept['completion_rate'] = round((dept['completed_tasks'] / dept['total_tasks']) * 100, 2)
        else:
            dept['completion_rate'] = 0
        
        for user_key, user_stats in dept['users'].items():
            if user_stats['total_tasks'] > 0:
                user_stats['completion_rate'] = round((user_stats['completed_tasks'] / user_stats['total_tasks']) * 100, 2)
            else:
                user_stats['completion_rate'] = 0
    return report_data

@app.route('/api/reports/weekly')
@login_required
def get_weekly_report():
    current_user = get_current_user()
    if not current_user or current_user.level not in [UserLevel.ADMIN.value, UserLevel.EXECUTIVE_MANAGER.value, UserLevel.MANAGER.value]:
        return jsonify({'error': '您沒有權限查看報告'}), 403

    today = datetime.now(utc)
    # 計算本週的開始日期 (週一) 和結束日期 (週日)
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    report_data = _generate_report_data(start_of_week, end_of_week)

    return jsonify({
        'report_type': 'weekly',
        'start_date': start_of_week.isoformat(),
        'end_date': end_of_week.isoformat(),
        'data': report_data
    })

@app.route('/api/reports/monthly')
@login_required
def get_monthly_report():
    current_user = get_current_user()
    if not current_user or current_user.level not in [UserLevel.ADMIN.value, UserLevel.EXECUTIVE_MANAGER.value, UserLevel.MANAGER.value]:
        return jsonify({'error': '您沒有權限查看報告'}), 403

    today = datetime.now(utc)
    # 計算本月的開始日期和結束日期
    start_of_month = today.replace(day=1)
    # 下個月的第一天減去一天就是本月的最後一天
    end_of_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    report_data = _generate_report_data(start_of_month, end_of_month)

    return jsonify({
        'report_type': 'monthly',
        'start_date': start_of_month.isoformat(),
        'end_date': end_of_month.isoformat(),
        'data': report_data
    })

@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')

@app.route('/scheduled-notifications', methods=['GET', 'POST'])
@login_required
def scheduled_notifications():
    current_user = get_current_user()
    assignable_users = [u for u in User.query.filter_by(is_active=True).all() if current_user.can_assign_to(u)]
    if current_user not in assignable_users:
        assignable_users.append(current_user)
    assignable_users.sort(key=lambda u: u.name)
    all_users = User.query.all() # For displaying recipient names in the table

    if request.method == 'POST':
        title = request.form.get('title')
        body = request.form.get('body')
        recipient_user_ids = request.form.getlist('recipient_user_ids') # Multi-select
        schedule_type = request.form.get('schedule_type')
        specific_date_str = request.form.get('specific_date')
        specific_time_str = request.form.get('specific_time')
        weekly_day_str = request.form.get('weekly_day')

        # --- Start of new validation logic ---
        if not all([title, body, recipient_user_ids, schedule_type]):
            flash('標題、內容、收件人、排程類型為必填欄位！', 'error')
            return redirect(url_for('scheduled_notifications'))

        specific_date = None
        specific_time = None
        weekly_day = None

        if schedule_type == 'one_time':
            if not specific_date_str:
                flash('「特定日期與時間」排程必須選擇日期和時間！', 'error')
                return redirect(url_for('scheduled_notifications'))
            try:
                # Parse combined date and time string from flatpickr
                full_datetime = datetime.strptime(specific_date_str, '%Y-%m-%d %H:%M')
                specific_date = full_datetime.date()
                specific_time = full_datetime.time()
            except ValueError:
                flash('日期時間格式無效！請使用 YYYY-MM-DD HH:MM 格式。', 'error')
                return redirect(url_for('scheduled_notifications'))
        
        elif schedule_type == 'weekly':
            if not weekly_day_str or not specific_time_str:
                flash('「每週重複」排程必須選擇星期和時間！', 'error')
                return redirect(url_for('scheduled_notifications'))
            
            weekly_day = int(weekly_day_str)
            try:
                specific_time = dt_time.fromisoformat(specific_time_str)
            except ValueError:
                flash('時間格式無效！', 'error')
                return redirect(url_for('scheduled_notifications'))
        else:
            flash('無效的排程類型！', 'error')
            return redirect(url_for('scheduled_notifications'))
        # --- End of new validation logic ---

        # Convert recipient_user_ids list to comma-separated string
        recipient_user_ids_str = ','.join(recipient_user_ids)

        new_notification = ScheduledNotification(
            user_id=current_user.id,
            title=title,
            body=body,
            recipient_user_ids=recipient_user_ids_str,
            schedule_type=schedule_type,
            specific_date=specific_date,
            specific_time=specific_time,
            weekly_day=weekly_day,
            is_active=True
        )
        db.session.add(new_notification)
        db.session.commit()
        flash('通知已成功建立！', 'success')
        return redirect(url_for('scheduled_notifications'))

    notifications = ScheduledNotification.query.filter_by(user_id=current_user.id).order_by(ScheduledNotification.created_at.desc()).all()
    return render_template('scheduled_notifications.html', 
                           notifications=notifications, 
                           assignable_users=assignable_users,
                           all_users=all_users) # Pass all_users for recipient name lookup in table

@app.route('/meeting_tasks')
@login_required
def meeting_tasks():
    return render_template('meeting_tasks.html')

@app.route('/scheduled-notifications/edit/<int:notification_id>', methods=['GET', 'POST'])
@login_required
def edit_scheduled_notification(notification_id):
    current_user = get_current_user()
    notification_to_edit = db.session.get(ScheduledNotification, notification_id)

    if not notification_to_edit:
        flash('找不到該通知！', 'error')
        return redirect(url_for('scheduled_notifications'))

    # Ensure the current user has permission to edit this notification
    if notification_to_edit.user_id != current_user.id and current_user.level != UserLevel.ADMIN.value:
        flash('您沒有權限編輯此通知！', 'error')
        return redirect(url_for('scheduled_notifications'))

    assignable_users = [u for u in User.query.filter_by(is_active=True).all() if current_user.can_assign_to(u)]
    if current_user not in assignable_users:
        assignable_users.append(current_user)
    assignable_users.sort(key=lambda u: u.name)
    all_users = User.query.all() # For displaying recipient names in the table

    if request.method == 'POST':
        title = request.form.get('title')
        body = request.form.get('body')
        recipient_user_ids = request.form.getlist('recipient_user_ids') # Multi-select
        schedule_type = request.form.get('schedule_type')
        specific_date_str = request.form.get('specific_date')
        specific_time_str = request.form.get('specific_time')
        weekly_day_str = request.form.get('weekly_day')

        # --- Start of new validation logic for edit ---
        if not all([title, body, recipient_user_ids, schedule_type]):
            flash('標題、內容、收件人、排程類型為必填欄位！', 'error')
            return redirect(url_for('edit_scheduled_notification', notification_id=notification_id))

        specific_date = None
        specific_time = None
        weekly_day = None

        if schedule_type == 'one_time':
            if not specific_date_str:
                flash('「特定日期與時間」排程必須選擇日期和時間！', 'error')
                return redirect(url_for('edit_scheduled_notification', notification_id=notification_id))
            try:
                # Parse combined date and time string from flatpickr
                full_datetime = datetime.strptime(specific_date_str, '%Y-%m-%d %H:%M')
                specific_date = full_datetime.date()
                specific_time = full_datetime.time()
            except ValueError:
                flash('日期時間格式無效！請使用 YYYY-MM-DD HH:MM 格式。', 'error')
                return redirect(url_for('edit_scheduled_notification', notification_id=notification_id))
        
        elif schedule_type == 'weekly':
            if not weekly_day_str or not specific_time_str:
                flash('「每週重複」排程必須選擇星期和時間！', 'error')
                return redirect(url_for('edit_scheduled_notification', notification_id=notification_id))
            
            weekly_day = int(weekly_day_str)
            try:
                specific_time = dt_time.fromisoformat(specific_time_str)
            except ValueError:
                flash('時間格式無效！', 'error')
                return redirect(url_for('edit_scheduled_notification', notification_id=notification_id))
        else:
            flash('無效的排程類型！', 'error')
            return redirect(url_for('edit_scheduled_notification', notification_id=notification_id))
        # --- End of new validation logic for edit ---

        # Convert recipient_user_ids list to comma-separated string
        recipient_user_ids_str = ','.join(recipient_user_ids)

        try:
            notification_to_edit.title = title
            notification_to_edit.body = body
            notification_to_edit.recipient_user_ids = recipient_user_ids_str
            notification_to_edit.schedule_type = schedule_type
            notification_to_edit.specific_date = specific_date
            notification_to_edit.specific_time = specific_time
            notification_to_edit.weekly_day = weekly_day
            
            db.session.commit()
            flash('通知已成功更新！', 'success')
            return redirect(url_for('scheduled_notifications'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新通知時發生錯誤: {e}', 'error')
            return redirect(url_for('edit_scheduled_notification', notification_id=notification_id))

    return render_template('scheduled_notifications.html', 
                           notifications=ScheduledNotification.query.filter_by(user_id=current_user.id).order_by(ScheduledNotification.created_at.desc()).all(), 
                           assignable_users=assignable_users,
                           all_users=all_users,
                           editing_notification=notification_to_edit)

@app.route('/api/scheduled_notification/<int:notification_id>/toggle', methods=['POST'])
@login_required
def toggle_scheduled_notification(notification_id):
    current_user = get_current_user()
    notification = db.session.get(ScheduledNotification, notification_id)

    if not notification:
        return jsonify({'error': '找不到該通知！'}), 404

    if notification.user_id != current_user.id and current_user.level != UserLevel.ADMIN.value:
        return jsonify({'error': '您沒有權限修改此通知！'}), 403

    try:
        notification.is_active = not notification.is_active
        db.session.commit()
        return jsonify({'message': '通知狀態已更新！', 'is_active': notification.is_active}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'更新通知狀態時發生錯誤: {e}'}), 500

@app.route('/api/scheduled_notification/<int:notification_id>', methods=['DELETE'])
@login_required
def delete_scheduled_notification(notification_id):
    current_user = get_current_user()
    notification = db.session.get(ScheduledNotification, notification_id)

    if not notification:
        return jsonify({'error': '找不到該通知！'}), 404

    if notification.user_id != current_user.id and current_user.level != UserLevel.ADMIN.value:
        return jsonify({'error': '您沒有權限刪除此通知！'}), 403

    try:
        db.session.delete(notification)
        db.session.commit()
        return jsonify({'message': '通知已成功刪除！'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'刪除通知時發生錯誤: {e}'}), 500

@app.route('/api/todo/<int:todo_id>/status', methods=['PUT'])
@login_required
def update_todo_status(todo_id):
    current_user = get_current_user()
    todo = db.get_or_404(Todo, todo_id)
    data = request.get_json()
    new_status = data.get('status')
    uncompleted_reason = data.get('uncompleted_reason', None)
    new_due_date = data.get('new_due_date', None)  # 新增：接收新的預計完成日期

    if not new_status or new_status not in [TodoStatus.PENDING.value, TodoStatus.IN_PROGRESS.value, TodoStatus.COMPLETED.value, TodoStatus.UNCOMPLETED.value]:
        return jsonify({'error': '無效的狀態'}), 400

    # 只有待辦事項的擁有者才能修改狀態
    if todo.user_id != current_user.id:
        return jsonify({'error': '您沒有權限修改此待辦事項的狀態'}), 403

    old_status = todo.status

    # 讀取現有的 history_log
    history = json.loads(todo.history_log or '[]')

    if new_status == TodoStatus.UNCOMPLETED.value:
        # 新增：處理預計完成日期的更新
        if new_due_date:
            try:
                new_due_date_parsed = isoparse(new_due_date)
                old_due_date = todo.due_date
                todo.due_date = new_due_date_parsed
                
                # 記錄預計完成日期變更到履歷
                taiwan_tz = timezone('Asia/Taipei')
                due_date_change_entry = {
                    'event_type': 'due_date_changed',
                    'timestamp': datetime.now(utc).isoformat(),
                    'actor': {'id': current_user.id, 'name': current_user.name, 'user_key': current_user.user_key},
                    'details': {
                        'old_due_date': old_due_date.astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M'),
                        'new_due_date': new_due_date_parsed.astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M'),
                        'reason': uncompleted_reason
                    }
                }
                history.append(due_date_change_entry)
                logging.info(f"Updated due date for Todo {todo.id} from {old_due_date} to {new_due_date_parsed}")
            except Exception as e:
                logging.error(f"Failed to parse new_due_date for Todo {todo.id}: {e}")
                return jsonify({'error': '無效的日期格式'}), 400
        
        # 記錄未完成事件
        history_entry = {
            'event_type': 'status_changed',
            'timestamp': datetime.now(utc).isoformat(),
            'actor': {'id': current_user.id, 'name': current_user.name, 'user_key': current_user.user_key},
            'details': {'old_status': old_status, 'new_status': TodoStatus.UNCOMPLETED.value, 'reason': uncompleted_reason}
        }
        history.append(history_entry)
        todo.history_log = json.dumps(history)
        todo.status = TodoStatus.IN_PROGRESS.value # 自動切換為進行中
    else:
        # 記錄狀態變更事件
        history_entry = {
            'event_type': 'status_changed',
            'timestamp': datetime.now(utc).isoformat(),
            'actor': {'id': current_user.id, 'name': current_user.name, 'user_key': current_user.user_key},
            'details': {'old_status': old_status, 'new_status': new_status}
        }
        history.append(history_entry)
        todo.history_log = json.dumps(history)
        todo.status = new_status

    # 如果 Todo 任務與 MeetingTask 相關聯，則更新 MeetingTask 的狀態和履歷
    logging.info(f"Checking todo.meeting_task_id for todo ID {todo.id}: {todo.meeting_task_id}")
    if todo.meeting_task_id:
        meeting_task = db.session.get(MeetingTask, todo.meeting_task_id)
        if meeting_task:
            logging.info(f"Found associated MeetingTask ID {meeting_task.id}. Updating its status and history.")
            # 更新 MeetingTask 狀態
            if new_status == TodoStatus.COMPLETED.value:
                meeting_task.status = MeetingTaskStatus.COMPLETED.value
                meeting_task.actual_completion_date = datetime.now(utc)
                meeting_task.uncompleted_reason_from_todo = None
            elif new_status == TodoStatus.IN_PROGRESS.value:
                meeting_task.status = MeetingTaskStatus.IN_PROGRESS_TODO.value
                meeting_task.actual_completion_date = None
                meeting_task.uncompleted_reason_from_todo = None
            elif new_status == TodoStatus.UNCOMPLETED.value:
                meeting_task.status = MeetingTaskStatus.UNCOMPLETED_TODO.value
                meeting_task.actual_completion_date = None
                meeting_task.uncompleted_reason_from_todo = uncompleted_reason
                # 新增：同步更新 MeetingTask 的預計完成日期
                if new_due_date:
                    try:
                        new_due_date_parsed = isoparse(new_due_date)
                        meeting_task.expected_completion_date = new_due_date_parsed
                        logging.info(f"Updated expected_completion_date for MeetingTask {meeting_task.id} to {new_due_date_parsed}")
                    except Exception as e:
                        logging.error(f"Failed to update MeetingTask expected_completion_date: {e}")
            elif new_status == TodoStatus.PENDING.value:
                meeting_task.status = MeetingTaskStatus.ASSIGNED.value
                meeting_task.actual_completion_date = None
                meeting_task.uncompleted_reason_from_todo = None

            # 將 Todo 的最新履歷附加到 MeetingTask 的履歷中
            meeting_task_history = json.loads(meeting_task.history_log or '[]')
            if history: # history 是從 todo.history_log 來的
                # 如果有日期變更事件，先添加它
                if new_status == TodoStatus.UNCOMPLETED.value and new_due_date and len(history) >= 2:
                    # 添加倒數第二個事件（日期變更事件）
                    meeting_task_history.append(history[-2])
                # 添加最新的事件（狀態變更事件）
                latest_todo_event = history[-1]
                meeting_task_history.append(latest_todo_event)
            meeting_task.history_log = json.dumps(meeting_task_history)
            
            db.session.add(meeting_task)

    db.session.commit()

    try:
        if new_status == TodoStatus.COMPLETED.value:
            assigner = todo.assigned_by
            if assigner and assigner.id != todo.user_id and assigner.notification_enabled:
                subject = f"[任務完成] {todo.title}"
                body = (
                    f"您好 {assigner.name}，<br><br>"
                    f"由您指派給 {todo.user.name} 的任務已完成。<br><br>"
                    f"<b>任務標題:</b> {todo.title}<br>"
                    f"<b>任務描述:</b><br>{todo.description.replace('\n', '<br>')}<br><br>"
                    f"<b>完成日期:</b> {datetime.now(timezone('Asia/Taipei')).strftime('%Y-%m-%d')}<br><br>"
                    f"請登入系統查看：<br><a href='http://192.168.6.119:5001'>http://192.168.6.119:5001</a>"
                )
                send_mail(subject, body, assigner.email)
                logging.info(f"Sent 'task completed' notification for task {todo.id} to assigner {assigner.email}")
    except Exception as e:
        logging.error(f"Failed to send 'task completed' notification for task {todo.id}: {e}")

    return jsonify({'message': '待辦事項狀態已更新'})


@app.route('/api/all_users')
@login_required
def get_all_users():
    users = User.query.all()
    users_data = [{'user_key': user.user_key, 'name': user.name, 'role': user.role, 'level': user.level, 'id': user.id} for user in users]
    return jsonify(users_data)


@app.route('/api/add_meeting_task', methods=['POST'])
@login_required
def add_meeting_task():
    current_user = get_current_user()
    data = request.get_json()

    # 獲取並驗證基本會議資訊
    meeting_topic = data.get('meeting_topic')
    meeting_date_str = data.get('meeting_date')
    chairman_user_key = data.get('chairman_user_key')
    recorder_user_key = data.get('recorder_user_key') # 新增接收紀錄人員
    attendees_user_keys = data.get('attendees_user_keys', [])
    discussion_topic = data.get('discussion_topic') # 新增討論議題
    location = data.get('location') # 新增地點

    # 獲取並驗證任務資訊
    task_type = data.get('task_type')
    task_description = data.get('task_description')
    assigned_to_user_key = data.get('assigned_to_user_key')
    controller_user_key = data.get('controller_user_key')
    expected_completion_date_str = data.get('expected_completion_date')

    # 檢查必填欄位
    if not all([meeting_topic, meeting_date_str, chairman_user_key, discussion_topic, task_type, task_description, assigned_to_user_key]):
        return jsonify({'error': '缺少必要的會議或任務資訊'}), 400

    # 驗證任務類型
    if task_type not in [MeetingTaskType.TRACKING.value, MeetingTaskType.RESOLUTION.value]:
        return jsonify({'error': '無效的任務類型'}), 400

    # 決議項目必須有預計完成日期
    if task_type == MeetingTaskType.RESOLUTION.value and not expected_completion_date_str:
        return jsonify({'error': '決議項目必須填寫預計完成日期'}), 400

    try:
        taipei_tz = timezone('Asia/Taipei')
        
        # 解析為 naive datetime
        naive_meeting_date = datetime.fromisoformat(meeting_date_str)
        # 本地化為台北時區
        meeting_date = taipei_tz.localize(naive_meeting_date)

        expected_completion_date = None
        if expected_completion_date_str:
            naive_expected_completion_date = datetime.fromisoformat(expected_completion_date_str)
            expected_completion_date = taipei_tz.localize(naive_expected_completion_date)

        if expected_completion_date:
            # 檢查日期是否為週末 (週六是5, 週日是6)
            if expected_completion_date.weekday() >= 5:
                return jsonify({'error': '預計完成日期不能是週末，請選擇週一至週五'}), 400
            # 檢查日期是否早于今天
            if expected_completion_date.date() < datetime.now(utc).date():
                return jsonify({'error': '預計完成日期不能早于今天'}), 400
    except ValueError:
        return jsonify({'error': '日期格式無效，請使用 YYYY-MM-DD 格式'}), 400

    # 查找相關使用者 ID
    chairman = User.query.filter_by(user_key=chairman_user_key).first()
    assigned_to = User.query.filter_by(user_key=assigned_to_user_key).first()
    recorder = User.query.filter_by(user_key=recorder_user_key).first() if recorder_user_key else None
    controller = User.query.filter_by(user_key=controller_user_key).first() if controller_user_key else None
    

    if not chairman or not assigned_to:
        return jsonify({'error': '主席或負責人員不存在'}), 400

    try:
        # 1. 處理 Meeting 記錄
        # 檢查是否已存在相同主題和日期的會議
        existing_meeting = Meeting.query.filter(
            Meeting.subject == meeting_topic,
            func.date(Meeting.meeting_date) == meeting_date.date(),
            Meeting.chairman_user_id == chairman.id
        ).first()

        is_new_meeting_created = False
        if existing_meeting:
            meeting = existing_meeting
            # Update location for existing meeting
            meeting.location = location
        else:
            meeting = Meeting(
                subject=meeting_topic,
                location=location,
                meeting_date=meeting_date,
                chairman_user_id=chairman.id,
                recorder_user_id=recorder.id if recorder else None, # 設定紀錄人員
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(meeting)
            db.session.flush() # 確保 meeting.id 被賦值
            is_new_meeting_created = True # Set flag to True if a new meeting is created

        # 2. 處理 MeetingAttendee 記錄
        for user_key in attendees_user_keys:
            attendee_user = User.query.filter_by(user_key=user_key).first()
            if attendee_user:
                # 檢查是否已存在此參與者，避免重複添加
                existing_attendee = MeetingAttendee.query.filter_by(
                    meeting_id=meeting.id,
                    user_id=attendee_user.id
                ).first()
                if not existing_attendee:
                    attendee = MeetingAttendee(
                        meeting_id=meeting.id,
                        user_id=attendee_user.id
                    )
                    db.session.add(attendee)

        # 3. 處理 DiscussionItem 記錄 (與 MeetingTask 解耦)
        # 檢查該會議是否已存在討論議題
        discussion_item = DiscussionItem.query.filter_by(meeting_id=meeting.id).first()
        if not discussion_item:
            discussion_item = DiscussionItem(
                meeting_id=meeting.id,
                topic=discussion_topic,
                reporter_user_id=None, 
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(discussion_item)
            db.session.flush() # 確保 discussion_item.id 被賦值

        # 4. 處理 MeetingTask 記錄
        initial_status = MeetingTaskStatus.UNASSIGNED.value if task_type == MeetingTaskType.TRACKING.value else "resolved_executing"
        is_assigned_to_todo = False

        new_meeting_task = MeetingTask(
            meeting_id=meeting.id, # 直接關聯到 meeting.id
            task_type=task_type,
            task_description=task_description,
            assigned_by_user_id=current_user.id,
            assigned_to_user_id=assigned_to.id,
            controller_user_id=controller.id if controller else None,
            expected_completion_date=expected_completion_date,
            actual_completion_date=None,
            status=initial_status,
            is_assigned_to_todo=is_assigned_to_todo,
            history_log=json.dumps([{
                'event_type': 'created',
                'timestamp': datetime.now(utc).isoformat(),
                'actor': {'id': current_user.id, 'name': current_user.name, 'user_key': current_user.user_key},
                'details': {'message': '會議任務已建立'}
            }]),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.session.add(new_meeting_task)
        db.session.commit()

        return jsonify({'message': '會議任務已成功記錄'}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"新增會議任務時發生錯誤: {e}", exc_info=True)
        return jsonify({'error': f'新增會議任務時發生錯誤: {str(e)}'}), 500


@app.route('/api/create_new_meeting_discussion', methods=['POST'])
@login_required
def create_new_meeting_discussion():
    current_user = get_current_user()
    data = request.get_json()

    meeting_topic = data.get('meeting_topic')
    meeting_date_str = data.get('meeting_date')
    chairman_user_key = data.get('chairman_user_key')
    recorder_user_key = data.get('recorder_user_key') # 新增接收紀錄人員
    attendees_user_keys = data.get('attendees_user_keys', [])
    discussion_topic = data.get('discussion_topic')
    location = data.get('location') # 新增接收地點
    if location == '': # 如果前端傳送空字串，則轉換為 None
        location = None

    if not all([meeting_topic, meeting_date_str, chairman_user_key, discussion_topic]):
        return jsonify({'error': '缺少必要的會議或討論議題資訊'}), 400

    try:
        taipei_tz = timezone('Asia/Taipei')
        # 解析為 naive datetime
        naive_meeting_date = datetime.fromisoformat(meeting_date_str)
        # 本地化為台北時區
        meeting_date = taipei_tz.localize(naive_meeting_date)
    except ValueError:
        return jsonify({'error': '日期格式無效，請使用 YYYY-MM-DD 格式'}), 400

    chairman = User.query.filter_by(user_key=chairman_user_key).first()
    recorder = User.query.filter_by(user_key=recorder_user_key).first() if recorder_user_key else None # 獲取紀錄人員
    if not chairman:
        return jsonify({'error': '主席不存在'}), 400

    try:
        # 創建新的 Meeting 記錄
        new_meeting = Meeting(
            subject=meeting_topic,
            location=location, # 儲存地點
            meeting_date=meeting_date,
            chairman_user_id=chairman.id,
            recorder_user_id=recorder.id if recorder else None, # 儲存紀錄人員
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.session.add(new_meeting)
        db.session.flush() # 確保 new_meeting.id 被賦值

        # 處理 MeetingAttendee 記錄
        for user_key in attendees_user_keys:
            attendee_user = User.query.filter_by(user_key=user_key).first()
            if attendee_user:
                existing_attendee = MeetingAttendee.query.filter_by(
                    meeting_id=new_meeting.id,
                    user_id=attendee_user.id
                ).first()
                if not existing_attendee:
                    attendee = MeetingAttendee(
                        meeting_id=new_meeting.id,
                        user_id=attendee_user.id
                    )
                    db.session.add(attendee)

        # 創建新的 DiscussionItem 記錄
        new_discussion_item = DiscussionItem(
            meeting_id=new_meeting.id,
            topic=discussion_topic,
            reporter_user_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.session.add(new_discussion_item)
        db.session.commit()

        # Prepare email notification for attendees (Moved from add_meeting_task)
        attendee_emails = []
        for user_key in attendees_user_keys:
            attendee_user = User.query.filter_by(user_key=user_key).first()
            if attendee_user and attendee_user.email and attendee_user.notification_enabled:
                attendee_emails.append(attendee_user.email)
        
        # Also include chairman if not already in attendees_user_keys and has email/notifications enabled
        if chairman.email and chairman.notification_enabled and chairman.user_key not in attendees_user_keys:
            attendee_emails.append(chairman.email)

        # Also include recorder if not already in attendees_user_keys/chairman and has email/notifications enabled
        if recorder and recorder.email and recorder.notification_enabled and \
           recorder.user_key not in attendees_user_keys and recorder.user_key != chairman.user_key:
            attendee_emails.append(recorder.email)

        # Collect all potential recipients
        all_recipients_emails = set(attendee_emails) # Start with attendees, chairman, recorder

        # Add special CC recipient if applicable
        if meeting_topic == "製造中心會議":
            special_cc_email = "jang@hartford.com.tw"
            all_recipients_emails.add(special_cc_email)
            logging.info(f"Adding {special_cc_email} as a primary recipient for '製造中心會議'.")

        if all_recipients_emails:
            # Format meeting date and time for email
            meeting_date_taipei = meeting_date.astimezone(timezone('Asia/Taipei')).strftime('%Y年%m月%d日 %H:%M')
            
            subject = f"{meeting_topic}[會議通知] " # Using meeting_topic for subject
            
            # Get attendee names for the email body
            attendee_names_for_body = [User.query.filter_by(user_key=uk).first().name for uk in attendees_user_keys if User.query.filter_by(user_key=uk).first()]
            
            for recipient_email in all_recipients_emails:
                body = (
                    f"您好，<br><br>"
                    f"有一場新的會議已安排，詳細資訊如下：<br><br>"
                    f"<b>會議主題:</b> {meeting_topic}<br>"
                    f"<b>會議日期:</b> {meeting_date_taipei}<br>"
                    f"<b>會議地點:</b> {new_meeting.location or '未指定'}<br>"
                    f"<b>主席:</b> {chairman.name}<br>"
                    f"<b>紀錄人員:</b> {recorder.name if recorder else '未指定'}<br>"
                    f"<b>討論議題:</b> {discussion_topic}<br>"
                    f"<b>與會人員:</b> {', '.join(attendee_names_for_body) if attendee_names_for_body else '無'}<br><br>"
                    f"請登入系統查看：<br><a href='http://192.168.6.119:5001'>http://192.168.6.119:5001</a>"
                )
                
                try:
                    send_mail(subject, body, recipient_email)
                    logging.info(f"Sent meeting notification for '{meeting_topic}' to {recipient_email}")
                except Exception as mail_e:
                    logging.error(f"Failed to send meeting notification for '{meeting_topic}' to {recipient_email}: {mail_e}")

        return jsonify({'message': '新會議和討論議題已成功創建', 'meeting_id': new_meeting.id, 'discussion_item_id': new_discussion_item.id}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"創建新會議和討論議題時發生錯誤: {e}", exc_info=True)
        return jsonify({'error': f'創建新會議和討論議題時發生錯誤: {str(e)}'}), 500


@app.route('/api/meeting_history')
@login_required
def get_meeting_history():
    try:
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)

        # 查詢所有不重複的會議主題和日期
        query = db.session.query(
            Meeting.subject,
            Meeting.meeting_date,
            Meeting.chairman_user_id,
            Meeting.id
        ).distinct()

        if year:
            query = query.filter(db.extract('year', Meeting.meeting_date) == year)
        if month:
            query = query.filter(db.extract('month', Meeting.meeting_date) == month)

        meetings = query.order_by(Meeting.meeting_date.desc()).all()

        history_data = []
        for meeting in meetings:
            chairman = db.session.get(User, meeting.chairman_user_id)
            history_data.append({
                'meeting_topic': meeting.subject, # 返回會議主題
                'meeting_date': meeting.meeting_date.astimezone(timezone('Asia/Taipei')).strftime('%Y-%m-%d'), # 返回會議日期
                'chairman_name': chairman.name if chairman else 'N/A'
            })
        return jsonify(history_data)
    except Exception as e:
        logging.error(f"Error in get_meeting_history: {e}", exc_info=True)
        return jsonify({'error': '無法載入會議歷史記錄，請聯繫管理員。'}), 500


@app.route('/api/discussion_item/<int:discussion_item_id>', methods=['PUT'])
@login_required
def update_discussion_item(discussion_item_id):
    current_user = get_current_user()
    discussion_item = db.get_or_404(DiscussionItem, discussion_item_id)

    meeting = db.session.get(Meeting, discussion_item.meeting_id)
    if not meeting:
        return jsonify({'error': '找不到相關的會議'}), 404

    # 權限檢查：管理員或會議主席可以編輯討論議題
    can_edit = (
        current_user.level == UserLevel.ADMIN.value or
        current_user.level == UserLevel.PLANT_MANAGER.value or
        current_user.level == UserLevel.MANAGER.value or
        current_user.id == meeting.chairman_user_id
    )

    if not can_edit:
        return jsonify({'error': '您沒有權限編輯此討論議題'}), 403

    data = request.get_json()
    new_topic = data.get('topic')
    recorder_user_key = data.get('recorder_user_key')
    new_location = data.get('location')
    new_meeting_date_str = data.get('meeting_date')

    if not new_topic or not new_topic.strip():
        return jsonify({'error': '討論議題內容不可為空'}), 400

    # 更新議題
    discussion_item.topic = new_topic
    discussion_item.updated_at = datetime.utcnow()

    # 更新會議地點
    meeting.location = new_location

    # 更新會議時間
    if new_meeting_date_str:
        try:
            meeting.meeting_date = datetime.fromisoformat(new_meeting_date_str).replace(tzinfo=utc)
        except ValueError:
            return jsonify({'error': '日期格式無效'}), 400

    # 更新紀錄人員
    if recorder_user_key is not None:
        recorder = User.query.filter_by(user_key=recorder_user_key).first()
        if recorder:
            meeting.recorder_user_id = recorder.id
        else:
            meeting.recorder_user_id = None
    
    meeting.updated_at = datetime.utcnow()

    try:
        db.session.commit()
        return jsonify({'message': '會議資訊已成功更新'})
    except Exception as e:
        db.session.rollback()
        logging.error(f"更新會議資訊時發生錯誤: {e}")
        return jsonify({'error': f'更新會議資訊時發生錯誤: {str(e)}'}), 500

@app.route('/api/meeting_task/<int:meeting_task_id>', methods=['PUT', 'DELETE'])
@login_required
def manage_meeting_task(meeting_task_id):
    meeting_task = db.get_or_404(MeetingTask, meeting_task_id)
    current_user = get_current_user()

    meeting = db.session.get(Meeting, meeting_task.meeting_id)
    if not meeting:
        return jsonify({'error': '找不到相關的會議'}), 404

    # 獲取討論議題 (如果存在)
    discussion_item = db.session.query(DiscussionItem).filter_by(meeting_id=meeting.id).first()

    # 權限檢查：管理員、主席、指派者、負責人可以編輯/刪除
    can_manage = (
        current_user.level == UserLevel.ADMIN.value or
        current_user.level == UserLevel.PLANT_MANAGER.value or
        current_user.level == UserLevel.MANAGER.value or
        current_user.id == meeting.chairman_user_id or
        current_user.id == meeting_task.assigned_by_user_id or
        current_user.id == meeting_task.assigned_to_user_id
    )

    # General permission check for managing the task (delete or edit any field)
    can_manage_overall = (
        current_user.level == UserLevel.ADMIN.value or
        current_user.level == UserLevel.PLANT_MANAGER.value or
        current_user.level == UserLevel.MANAGER.value or
        current_user.id == meeting.chairman_user_id or
        current_user.id == meeting_task.assigned_by_user_id or
        current_user.id == meeting_task.assigned_to_user_id
    )

    if not can_manage_overall:
        return jsonify({'error': '您沒有權限執行此操作'}), 403

    if request.method == 'PUT':
        if meeting_task.status == MeetingTaskStatus.AGREED_FINALIZED.value:
            return jsonify({'error': '已同意的決議不能修改'}), 400
        
        data = request.get_json()
        history = json.loads(meeting_task.history_log or '[]')
        update_details = {}

        new_assigned_to_key = data.get('assigned_to_user_key')
        new_controller_key = data.get('controller_user_key')
        new_description = data.get('task_description')
        new_discussion_topic = data.get('discussion_topic')

        # Specific permission check for 'assigned_to' and 'controller' fields
        # 只有管理員、協理、廠長、經理可以編輯「主辦者」和「管制者」欄位
        can_edit_assignees = current_user.level in [
            UserLevel.ADMIN.value,
            UserLevel.EXECUTIVE_MANAGER.value,
            UserLevel.PLANT_MANAGER.value,
            UserLevel.MANAGER.value
        ]
        
        # Get current assigned_to and controller user_keys for comparison
        current_assigned_to_key = meeting_task.assigned_to_user.user_key if meeting_task.assigned_to_user else None
        current_controller_key = meeting_task.controller_user.user_key if meeting_task.controller_user else None

        # Check if assigned_to or controller fields are actually being changed
        assigned_to_changed = new_assigned_to_key is not None and new_assigned_to_key != current_assigned_to_key
        controller_changed = new_controller_key is not None and new_controller_key != current_controller_key

        # Specific permission check for 'assigned_to' and 'controller' fields
        # 只有管理員、協理、廠長、經理可以編輯「主辦者」和「管制者」欄位
        can_edit_assignees = current_user.level in [
            UserLevel.ADMIN.value,
            UserLevel.EXECUTIVE_MANAGER.value,
            UserLevel.PLANT_MANAGER.value,
            UserLevel.MANAGER.value
        ]
        
        if (assigned_to_changed or controller_changed) and not can_edit_assignees:
            return jsonify({'error': '您沒有權限編輯主辦者或管制者欄位'}), 403

        if assigned_to_changed or controller_changed:
            if meeting_task.is_assigned_to_todo:
                return jsonify({'error': '此任務已指派，無法修改主辦者或管制者'}), 400

            # Update assigned_to
            if assigned_to_changed:
                old_assigned_to_user = db.session.get(User, meeting_task.assigned_to_user_id)
                new_assigned_to_user = User.query.filter_by(user_key=new_assigned_to_key).first()
                if not new_assigned_to_user:
                    return jsonify({'error': f'找不到主辦者: {new_assigned_to_key}'}), 404
                meeting_task.assigned_to_user_id = new_assigned_to_user.id
                update_details['assigned_to'] = {
                    'old': {'name': old_assigned_to_user.name, 'user_key': old_assigned_to_user.user_key},
                    'new': {'name': new_assigned_to_user.name, 'user_key': new_assigned_to_user.user_key}
                }

            # Update controller
            if controller_changed:
                old_controller_user = db.session.get(User, meeting_task.controller_user_id) if meeting_task.controller_user_id else None
                new_controller_user = User.query.filter_by(user_key=new_controller_key).first()
                if not new_controller_user:
                    return jsonify({'error': f'找不到管制者: {new_controller_key}'}), 404
                meeting_task.controller_user_id = new_controller_user.id
                update_details['controller'] = {
                    'old': {'name': old_controller_user.name, 'user_key': old_controller_user.user_key} if old_controller_user else None,
                    'new': {'name': new_controller_user.name, 'user_key': new_controller_user.user_key}
                }
        
        # 處理描述和議題變更 (所有可以管理任務的人都可以編輯這些)
        if new_description is not None and new_description != meeting_task.task_description:
            update_details['description'] = {
                'old': meeting_task.task_description,
                'new': new_description
            }
            meeting_task.task_description = new_description
        
        if discussion_item and new_discussion_topic is not None and new_discussion_topic != discussion_item.topic:
            update_details['discussion_topic'] = {
                'old': discussion_item.topic,
                'new': new_discussion_topic
            }
            discussion_item.topic = new_discussion_topic

        # 如果有任何更新，則記錄並提交
        if update_details:
            history.append({
                'event_type': 'updated',
                'timestamp': datetime.now(utc).isoformat(),
                'actor': {'id': current_user.id, 'name': current_user.name, 'user_key': current_user.user_key},
                'details': update_details
            })
            meeting_task.history_log = json.dumps(history)
            db.session.commit()
            return jsonify({'message': '任務已更新'})
        
        return jsonify({'message': '沒有任何變更'})

    elif request.method == 'DELETE':
        if meeting_task.status == MeetingTaskStatus.AGREED_FINALIZED.value:
            return jsonify({'error': '已同意的決議不能刪除'}), 400
        if meeting_task.is_assigned_to_todo:
            return jsonify({'error': '此任務已指派到主任務列表，無法刪除'}), 400
            
        db.session.delete(meeting_task)
        
        # 由於 MeetingTask 不再直接關聯 DiscussionItem，這裡的邏輯需要調整
        # 如果要刪除 DiscussionItem，需要明確判斷是否還有其他 MeetingTask 關聯到同一個 Meeting
        # 這裡暫時不自動刪除 DiscussionItem，除非有明確的業務邏輯要求

        db.session.commit()
        return jsonify({'message': '任務已刪除'})


@app.route('/api/meeting_task/<int:meeting_task_id>/agree', methods=['POST'])
@login_required
def agree_meeting_task(meeting_task_id):
    current_user = get_current_user()
    meeting_task = db.get_or_404(MeetingTask, meeting_task_id)

    # 權限檢查：只有負責人或管理員可以同意決議
    if not (current_user.id == meeting_task.assigned_to_user_id or current_user.level == UserLevel.ADMIN.value):
        return jsonify({'error': '您沒有權限同意此決議'}), 403

    if meeting_task.status == MeetingTaskStatus.AGREED_FINALIZED.value:
        return jsonify({'error': '此決議已同意並最終確定'}), 400

    # 更新狀態
    meeting_task.status = MeetingTaskStatus.AGREED_FINALIZED.value

    # 記錄歷史事件
    history = json.loads(meeting_task.history_log or '[]')
    history.append({
        'event_type': 'agreed_finalized',
        'timestamp': datetime.now(utc).isoformat(),
        'actor': {'id': current_user.id, 'name': current_user.name, 'user_key': current_user.user_key},
        'details': {'message': '決議已同意並最終確定'}
    })
    meeting_task.history_log = json.dumps(history)

    try:
        db.session.commit()
        # 通知管制者 (如果存在)
        if meeting_task.controller_user_id:
            controller = db.session.get(User, meeting_task.controller_user_id)
            if controller and controller.email and controller.notification_enabled:
                subject = f"[決議已同意] {meeting_task.meeting.subject}"
                body = (
                    f"您好 {controller.name}，\n\n"
                    f"會議決議 {meeting_task.meeting.subject} 中的任務 {meeting_task.task_description} 已由 {current_user.name} 同意並最終確定。\n\n"
                    f"請登入系統查看：\nhttp://192.168.6.119:5001"
                )
                send_mail(subject, body, controller.email)
        return jsonify({'message': '決議已同意並最終確定'}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"同意決議時發生錯誤: {e}")
        return jsonify({'error': f'同意決議時發生錯誤: {str(e)}'}), 500


@app.route('/api/assign_tracking_task_to_todo/<int:meeting_task_id>', methods=['POST'])
@login_required
def assign_tracking_task_to_todo(meeting_task_id):
    current_user = get_current_user()
    meeting_task = db.get_or_404(MeetingTask, meeting_task_id)
    data = request.get_json()
    expected_completion_date_str = data.get('expected_completion_date')

    if not expected_completion_date_str:
        return jsonify({'error': '請提供預計完成日期'}), 400

    try:
        expected_completion_date = datetime.fromisoformat(expected_completion_date_str).replace(tzinfo=utc)
        # 檢查日期是否為週末 (週六是5, 週日是6)
        if expected_completion_date.weekday() >= 5:
            return jsonify({'error': '預計完成日期不能是週末，請選擇週一至週五'}), 400
        # 檢查日期是否早于今天
        if expected_completion_date.date() < datetime.now(utc).date():
            return jsonify({'error': '預計完成日期不能早于今天'}), 400
    except ValueError:
        return jsonify({'error': '無效的日期格式'}), 400

    # 權限檢查：組長及以上層級的使用者可以執行此操作
    team_leader_level_value = LEVEL_ORDER.get(UserLevel.TEAM_LEADER.value, 0)
    current_user_level_value = LEVEL_ORDER.get(current_user.level, 0)

    if not (current_user_level_value >= team_leader_level_value or current_user.level == UserLevel.ADMIN.value):
        return jsonify({'error': '您沒有權限指派此任務'}), 403

    if meeting_task.is_assigned_to_todo:
        return jsonify({'error': '此任務已經被指派過了'}), 400

    # 更新會議任務的預計完成日期
    meeting_task.expected_completion_date = expected_completion_date

    # 根據 expected_completion_date 決定 todo_type
    today_date = datetime.now(utc).date()
    start_of_current_week = today_date - timedelta(days=today_date.weekday())
    end_of_current_week = start_of_current_week + timedelta(days=6)

    if expected_completion_date.date() > end_of_current_week:
        todo_type_for_new_todo = TodoType.NEXT.value
    else:
        todo_type_for_new_todo = TodoType.CURRENT.value

    meeting = db.session.get(Meeting, meeting_task.meeting_id)
    if not meeting:
        return jsonify({'error': '找不到相關的會議'}), 404

    # Format meeting date for title
    formatted_meeting_date = meeting.meeting_date.strftime('%Y-%m-%d')

    # 確定指派人是管制者還是當前使用者
    assigner_user = None
    if meeting_task.controller_user_id:
        assigner_user = db.session.get(User, meeting_task.controller_user_id)
    
    if not assigner_user:
        assigner_user = current_user

    # 創建新的 Todo 項目
    new_todo = Todo(
        title=f"【會議追蹤】{meeting.subject} ({formatted_meeting_date})", # 使用 Meeting 的 subject
        description=meeting_task.task_description,
        status=TodoStatus.PENDING.value,
        todo_type=todo_type_for_new_todo,
        user_id=meeting_task.assigned_to_user_id,
        assigned_by_user_id=assigner_user.id,
        due_date=expected_completion_date,
        meeting_task_id=meeting_task.id
    )
    
    assigned_to_user = db.session.get(User, meeting_task.assigned_to_user_id)

    history_entry = {
        'event_type': 'assigned_from_meeting',
        'timestamp': datetime.now(utc).isoformat(),
        'actor': {'id': assigner_user.id, 'name': assigner_user.name, 'user_key': assigner_user.user_key},
        'details': {
            'meeting_topic': meeting.subject, # 使用 Meeting 的 subject
            'assigned_to': {'id': assigned_to_user.id, 'name': assigned_to_user.name, 'user_key': assigned_to_user.user_key},
            'assigned_by': {'id': assigner_user.id, 'name': assigner_user.name, 'user_key': assigner_user.user_key}
        }
    }
    new_todo.history_log = json.dumps([history_entry])

    meeting_task.is_assigned_to_todo = True
    meeting_task.status = MeetingTaskStatus.ASSIGNED.value
    meeting_task.todo = new_todo

    try:
        db.session.add(new_todo)
        db.session.add(meeting_task)
        db.session.flush()

        meeting_task_history = json.loads(meeting_task.history_log or '[]')
        meeting_task_history.append({
            'event_type': 'assigned_to_todo',
            'timestamp': datetime.now(utc).isoformat(),
            'actor': {'id': assigner_user.id, 'name': assigner_user.name, 'user_key': assigner_user.user_key},
            'details': {
                'assigned_to_todo_id': new_todo.id,
                'assigned_to_user': {'id': assigned_to_user.id, 'name': assigned_to_user.name, 'user_key': assigned_to_user.user_key},
                'assigned_by_user': {'id': assigner_user.id, 'name': assigner_user.name, 'user_key': assigner_user.user_key}
            }
        })
        meeting_task.history_log = json.dumps(meeting_task_history)
        
        db.session.commit()

        if assigned_to_user and assigned_to_user.email and assigned_to_user.notification_enabled:
            subject = f"會議任務指派已確認預計完成日期：{new_todo.title}"
            body = (
                f"您好 {assigned_to_user.name}，<br><br>"
                f"您有一項來自 <b>'{meeting_task.meeting.subject}'</b> 會議的新任務。<br><br>"
                f"<b>任務內容:</b> {meeting_task.task_description}<br>"
                f"<b>指派人:</b> {assigner_user.name}<br>"
                f"<b>預計完成日期:</b> {expected_completion_date.strftime('%Y-%m-%d')}<br><br>"
                f"請登入系統查看詳情：<br><a href='http://192.168.6.119:5001'>http://192.168.6.119:5001</a>"
            )
            
            mail_cc = ""
            # 只有當指派人不是被指派人，且指派人有郵箱且啟用通知時才CC
            if assigner_user.id != assigned_to_user.id and assigner_user.email and assigner_user.notification_enabled:
                mail_cc = assigner_user.email
            
            send_mail(subject, body, assigned_to_user.email, mail_cc=mail_cc)

        return jsonify({'message': '任務已成功指派到主任務列表'}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"指派會議任務到 Todo 時發生錯誤: {e}")
        return jsonify({'error': f'指派失敗: {str(e)}'}), 500


@app.route('/api/meeting_task/<int:meeting_task_id>')
@login_required
def get_single_meeting_task(meeting_task_id):
    meeting_task = db.get_or_404(MeetingTask, meeting_task_id)
    
    meeting = db.session.get(Meeting, meeting_task.meeting_id)
    if not meeting:
        return jsonify({'error': '找不到相關的會議'}), 404

    # 獲取討論議題 (如果存在)
    discussion_item = db.session.query(DiscussionItem).filter_by(meeting_id=meeting.id).first()

    chairman_name = db.session.get(User, meeting.chairman_user_id).name if meeting.chairman_user_id else 'N/A'
    assigned_by_name = db.session.get(User, meeting_task.assigned_by_user_id).name if meeting_task.assigned_by_user_id else 'N/A'
    assigned_to_name = db.session.get(User, meeting_task.assigned_to_user_id).name if meeting_task.assigned_to_user_id else 'N/A'
    recorder_name = db.session.get(User, meeting.recorder_user_id).name if meeting.recorder_user_id else None



    controller_name = db.session.get(User, meeting_task.controller_user_id).name if meeting_task.controller_user_id else None

    attendees_user_keys = []
    for attendee in meeting.attendees:
        attendees_user_keys.append(attendee.user.user_key)

    current_user = get_current_user()
    can_edit_assignee_fields = current_user.level in [
        UserLevel.ADMIN.value,
        UserLevel.EXECUTIVE_MANAGER.value,
        UserLevel.PLANT_MANAGER.value,
        UserLevel.MANAGER.value
    ]

    return jsonify({
        'id': meeting_task.id,
        'meeting_topic': meeting.subject,
        'meeting_date': meeting.meeting_date.astimezone(timezone('Asia/Taipei')).strftime('%Y-%m-%d'),
        'chairman_user_key': db.session.get(User, meeting.chairman_user_id).user_key if meeting.chairman_user_id else None,
        'chairman_name': chairman_name,
        'attendees_user_keys': attendees_user_keys,
        'discussion_topic': discussion_item.topic, # 新增討論議題
        'task_type': meeting_task.task_type,
        'task_description': meeting_task.task_description,
        'assigned_by_user_id': meeting_task.assigned_by_user_id,
        'assigned_by_name': assigned_by_name,
        'assigned_to_user_id': meeting_task.assigned_to_user_id,
        'assigned_to_name': assigned_to_name,
        'recorder_user_id': meeting.recorder_user_id, # 從 Meeting 獲取
        'recorder_name': recorder_name,
        'controller_user_id': meeting_task.controller_user_id,
        'controller_name': controller_name,
        'expected_completion_date': meeting_task.expected_completion_date.isoformat() if meeting_task.expected_completion_date else None,
        'actual_completion_date': meeting_task.actual_completion_date.isoformat() if meeting_task.actual_completion_date else None,
        'status': meeting_task.status,
        'is_assigned_to_todo': meeting_task.is_assigned_to_todo,
        'history_log': json.loads(meeting_task.history_log or '[]'),
        'permissions': {
            'can_edit_assignee_fields': can_edit_assignee_fields
        }
    })


@app.route('/api/get_meeting_details_by_topic_date')
@login_required
def get_meeting_details_by_topic_date():
    meeting_topic = request.args.get('meeting_topic')
    meeting_date_str = request.args.get('meeting_date')

    if not meeting_topic or not meeting_date_str:
        return jsonify({'error': '缺少會議主題或會議日期'}), 400

    try:
        meeting_date = datetime.fromisoformat(meeting_date_str).date()
    except ValueError:
        return jsonify({'error': '日期格式無效，請使用 YYYY-MM-DD 格式'}), 400

    meeting = db.session.query(Meeting).filter(
        Meeting.subject == meeting_topic,
        func.date(Meeting.meeting_date) == meeting_date
    ).first()

    if not meeting:
        return jsonify({'error': '找不到符合條件的會議'}), 404

    chairman_user_key = db.session.get(User, meeting.chairman_user_id).user_key if meeting.chairman_user_id else None
    
    attendees_user_keys = []
    for attendee in meeting.attendees:
        attendees_user_keys.append(attendee.user.user_key)

    # 獲取第一個討論議題的內容 (如果存在)
    discussion_item_topic = None
    discussion_item = None # 初始化 discussion_item
    if meeting.discussion_items:
        discussion_item = meeting.discussion_items[0]
        discussion_item_topic = discussion_item.topic

    # 獲取與此會議相關的 MeetingTask，並從中提取 recorder_user_id
    # 這裡假設一個會議只有一個 recorder，或者我們只取第一個找到的 recorder
    recorder_user_key = None
    if meeting.recorder_user_id:
        recorder_user = db.session.get(User, meeting.recorder_user_id)
        if recorder_user:
            recorder_user_key = recorder_user.user_key

    return jsonify({
        'meeting_topic': meeting.subject,
        'location': meeting.location,
        'meeting_date': meeting.meeting_date.strftime('%Y-%m-%dT%H:%M'),
        'chairman_user_key': chairman_user_key,
        'attendees_user_keys': attendees_user_keys,
        'discussion_topic': discussion_item_topic,
        'discussion_item_id': discussion_item.id if discussion_item else None, # 新增返回 discussion_item_id
        'recorder_user_key': recorder_user_key
    })


@app.route('/api/meeting_available_dates')
@login_required
def get_meeting_available_dates():
    try:
        # 查詢所有不重複的會議年份和月份，並按最新排序
        query = db.session.query(
            db.extract('year', Meeting.meeting_date).label('year'),
            db.extract('month', Meeting.meeting_date).label('month')
        ).distinct().order_by(
            db.extract('year', Meeting.meeting_date).desc(),
            db.extract('month', Meeting.meeting_date).desc()
        )
        available_pairs = query.all()

        # 如果沒有任何會議記錄
        if not available_pairs:
            now = datetime.now(timezone('Asia/Taipei'))
            current_year = now.year
            current_month = now.month
            return jsonify({
                'years': [current_year],
                'months': [current_month],
                'defaultYear': current_year,
                'defaultMonth': current_month
            })

        # 分離出獨立的年份和月份列表用於下拉選單
        available_years = sorted(list(set(p.year for p in available_pairs)), reverse=True)
        available_months = sorted(list(set(p.month for p in available_pairs)), reverse=True)

        # 判斷預設選項
        now = datetime.now(timezone('Asia/Taipei'))
        current_year = now.year
        current_month = now.month

        # 檢查當前年月組合是否存在於資料中
        current_month_has_data = any(p.year == current_year and p.month == current_month for p in available_pairs)

        if current_month_has_data:
            default_year = current_year
            default_month = current_month
        else:
            # 如果當前月份沒資料，則回退到最近有資料的月份
            most_recent_pair = available_pairs[0]
            default_year = most_recent_pair.year
            default_month = most_recent_pair.month

        return jsonify({
            'years': available_years,
            'months': available_months,
            'defaultYear': default_year,
            'defaultMonth': default_month
        })

    except Exception as e:
        logging.error(f"Error in get_meeting_available_dates: {e}", exc_info=True)
        return jsonify({'error': '無法載入可用的會議日期。'}), 500

@app.route('/api/meeting_tasks_list')
@login_required
def get_meeting_tasks_list():
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    meeting_topic = request.args.get('meeting_topic') # 新增接收 meeting_topic
    meeting_date_str = request.args.get('meeting_date') # 新增接收 meeting_date

    # 查詢所有 MeetingTask，並關聯到 Meeting
    query = db.session.query(MeetingTask, Meeting).join(
        Meeting, MeetingTask.meeting_id == Meeting.id
    )

    if year:
        query = query.filter(db.extract('year', Meeting.meeting_date) == year)
    if month:
        query = query.filter(db.extract('month', Meeting.meeting_date) == month)
    
    if meeting_topic:
        query = query.filter(Meeting.subject == meeting_topic)
    if meeting_date_str:
        try:
            meeting_date = datetime.fromisoformat(meeting_date_str).date()
            query = query.filter(func.date(Meeting.meeting_date) == meeting_date)
        except ValueError:
            pass # 忽略無效的日期格式

    results = query.all()
    tasks_data = []
    for task, meeting in results:
        # 獲取與此會議相關的 DiscussionItem (如果存在)
        discussion_item = db.session.query(DiscussionItem).filter_by(meeting_id=meeting.id).first()
        discussion_topic = discussion_item.topic if discussion_item else 'N/A'
        chairman_name = db.session.get(User, meeting.chairman_user_id).name if meeting.chairman_user_id else 'N/A'
        assigned_by_name = db.session.get(User, task.assigned_by_user_id).name if task.assigned_by_user_id else 'N/A'
        assigned_to_name = db.session.get(User, task.assigned_to_user_id).name if task.assigned_to_user_id else 'N/A'
        recorder_name = db.session.get(User, meeting.recorder_user_id).name if meeting.recorder_user_id else None
        controller_name = db.session.get(User, task.controller_user_id).name if task.controller_user_id else None
        
        attendees_names = []
        for attendee in meeting.attendees:
            attendees_names.append(attendee.user.name)

        tasks_data.append({
            'id': task.id,
            'meeting_topic': meeting.subject,
            'meeting_date': meeting.meeting_date.astimezone(timezone('Asia/Taipei')).strftime('%Y-%m-%d'),
            'chairman_name': chairman_name,
            'attendees_names': attendees_names,
            'discussion_topic': discussion_item.topic, # 新增討論議題
            'task_type': task.task_type,
            'task_description': task.task_description,
            'assigned_by_name': assigned_by_name,
            'assigned_to_user_key': task.assigned_to_user.user_key if task.assigned_to_user else None, # 新增 user_key
            'assigned_to_name': assigned_to_name,
            'recorder_user_id': meeting.recorder_user_id, # 從 Meeting 獲取
            'recorder_name': recorder_name,
            'controller_user_key': task.controller_user.user_key if task.controller_user else None, # 新增 user_key
            'controller_name': controller_name,
            'expected_completion_date': task.expected_completion_date.astimezone(timezone('Asia/Taipei')).strftime('%Y-%m-%d') if task.expected_completion_date else None,
            'actual_completion_date': task.actual_completion_date.isoformat() if task.actual_completion_date else None,
            'status': task.status,
            'is_assigned_to_todo': task.is_assigned_to_todo,
            'history_log': json.loads(task.history_log or '[]')
        })
    return jsonify(tasks_data)

@app.route('/api/export_meeting_tasks_pdf', methods=['POST'])
@login_required
def export_meeting_tasks_pdf():
    data = request.get_json()
    meeting_topic = data.get('meeting_topic')
    meeting_date_str = data.get('meeting_date')

    if not meeting_topic or not meeting_date_str:
        return jsonify({'error': '缺少會議主題或會議日期'}), 400

    try:
        meeting_date = datetime.fromisoformat(meeting_date_str).replace(tzinfo=utc)
    except ValueError:
        return jsonify({'error': '日期格式無效，請使用 YYYY-MM-DD 格式'}), 400

    # 查詢指定會議主題和日期的所有 Meeting
    meeting = db.session.query(Meeting).filter(
        Meeting.subject == meeting_topic,
        func.date(Meeting.meeting_date) == meeting_date.date()
    ).first()

    if not meeting:
        return jsonify({'error': '找不到符合條件的會議'}), 404

    # 獲取與此會議相關的所有 DiscussionItem
    discussion_items = db.session.query(DiscussionItem).filter_by(meeting_id=meeting.id).all()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5 * inch, leftMargin=0.5 * inch, rightMargin=0.5 * inch)
    story = []

    formatted_date_for_header = meeting.meeting_date.astimezone(timezone('Asia/Taipei')).strftime('%Y年%m月%d日')
    formatted_time_for_header = meeting.meeting_date.astimezone(timezone('Asia/Taipei')).strftime('%H:%M')

    chairman_name = db.session.get(User, meeting.chairman_user_id).name if meeting.chairman_user_id else 'N/A'
    recorder_name = db.session.get(User, meeting.recorder_user_id).name if meeting.recorder_user_id else '無'
    
    # 獲取所有參與者名稱
    attendees_names = []
    for attendee in meeting.attendees:
        attendees_names.append(attendee.user.name)
    
    # 獲取所有討論議題的報告人員名稱
    reporter_names = []
    for di in discussion_items:
        if di.reporter_user_id:
            reporter = db.session.get(User, di.reporter_user_id)
            if reporter and reporter.name not in reporter_names:
                reporter_names.append(reporter.name)

    story.append(Paragraph(f"主題: {meeting.subject}", styles['Normal']))
    story.append(Paragraph(f"日期: {formatted_date_for_header}", styles['Normal']))
    story.append(Paragraph(f"時間: {formatted_time_for_header}", styles['Normal']))
    story.append(Paragraph(f"地點: {meeting.location or '未指定'}", styles['Normal']))
    story.append(Paragraph(f"主席: {chairman_name}", styles['Normal']))
    story.append(Paragraph(f"紀錄: {recorder_name}", styles['Normal'])) # 新增紀錄人員
    story.append(Paragraph(f"出席人員: {', '.join(attendees_names) if attendees_names else '無'}", styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))

    # 分類任務
    tracking_items = []
    resolution_items = []

    # 獲取與此會議相關的所有 MeetingTask
    all_tasks_for_meeting = db.session.query(MeetingTask).filter(
        MeetingTask.meeting_id == meeting.id
    ).all()

    for task in all_tasks_for_meeting:
        if task.task_type == MeetingTaskType.TRACKING.value:
            tracking_items.append(task)
        else:
            resolution_items.append(task)

    # 追蹤項目
    story.append(Paragraph("追蹤項目", styles['h3']))
    if tracking_items:
        col_widths_tracking = [
            0.5 * inch,  # 項次
            2.5 * inch,  # 任務事項
            0.7 * inch,   # 主辦者
            0.7 * inch,   # 管制者
            1.1 * inch, # 預計完成日期
            1.1 * inch, # 實際完成日期
            0.9 * inch    # 狀態
        ]
        
        data = [['項次', '任務事項', '主辦者', '管制者', '預計完成日期', '實際完成日期', '狀態']]
        for i, task in enumerate(tracking_items, 1):
            assigned_to_name = db.session.get(User, task.assigned_to_user_id).name if task.assigned_to_user_id else 'N/A'
            controller_name = db.session.get(User, task.controller_user_id).name if task.controller_user_id else 'N/A'
            expected_date = task.expected_completion_date.astimezone(timezone('Asia/Taipei')).strftime('%Y-%m-%d') if task.expected_completion_date else '未設定'
            actual_date = task.actual_completion_date.astimezone(timezone('Asia/Taipei')).strftime('%Y-%m-%d') if task.actual_completion_date else '未完成'
            translated_status = STATUS_TRANSLATIONS.get(task.status, task.status)
            
            data.append([
                Paragraph(str(i), styles['Normal']),
                Paragraph(task.task_description, styles['Normal']),
                Paragraph(assigned_to_name, styles['Normal']),
                Paragraph(controller_name, styles['Normal']),
                Paragraph(expected_date, styles['Normal']),
                Paragraph(actual_date, styles['Normal']),
                Paragraph(translated_status, styles['Normal'])
            ])
        table = Table(data, colWidths=col_widths_tracking)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'NotoSansCJKtc'),
            ('FONTNAME', (0, 1), (-1, -1), 'NotoSansCJKtc'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("暫無追蹤項目。", styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))

    # 決議項目
    story.append(Paragraph("決議項目", styles['h3']))
    if resolution_items:
        col_widths_resolution = [
            0.5 * inch,  # 項次
            3.5 * inch,  # 任務事項
            1.0 * inch,  # 主辦者
            1.0 * inch,  # 管制者
            1.0 * inch,  # 開始執行日期
            0.5 * inch   # 狀態
        ]
        
        data = [['項次', '任務事項', '主辦者', '管制者', '開始執行日期', '狀態']]
        for i, task in enumerate(resolution_items, 1):
            assigned_to_name = db.session.get(User, task.assigned_to_user_id).name if task.assigned_to_user_id else 'N/A'
            controller_name = db.session.get(User, task.controller_user_id).name if task.controller_user_id else 'N/A'
            expected_date = task.expected_completion_date.astimezone(timezone('Asia/Taipei')).strftime('%Y-%m-%d') if task.expected_completion_date else '未設定'
            translated_status = STATUS_TRANSLATIONS.get(task.status, task.status)
            
            data.append([
                Paragraph(str(i), styles['Normal']),
                Paragraph(task.task_description, styles['Normal']),
                Paragraph(assigned_to_name, styles['Normal']),
                Paragraph(controller_name, styles['Normal']),
                Paragraph(expected_date, styles['Normal']),
                Paragraph(translated_status, styles['Normal'])
            ])
        table = Table(data, colWidths=col_widths_resolution)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'NotoSansCJKtc'),
            ('FONTNAME', (0, 1), (-1, -1), 'NotoSansCJKtc'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("暫無決議項目。", styles['Normal']))

    header_footer_with_context = lambda c, d: _header_footer_template(c, d, 
        meeting_topic="會議記錄", 
        meeting_date_str=formatted_date_for_header,
        title="會議記錄" # 傳遞標題
    )

    doc.build(story, onFirstPage=header_footer_with_context, onLaterPages=header_footer_with_context)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f"會議任務_{meeting_topic}_{meeting_date_str}.pdf", mimetype='application/pdf')


@app.route('/api/export_discussion_items_pdf', methods=['POST'])
@login_required
def export_discussion_items_pdf():
    data = request.get_json()
    meeting_topic = data.get('meeting_topic')
    meeting_date_str = data.get('meeting_date')

    if not meeting_topic or not meeting_date_str:
        return jsonify({'error': '缺少會議主題或會議日期'}), 400

    try:
        meeting_date = datetime.fromisoformat(meeting_date_str).replace(tzinfo=utc)
    except ValueError:
        return jsonify({'error': '日期格式無效，請使用 YYYY-MM-DD 格式'}), 400

    meeting = db.session.query(Meeting).filter(
        Meeting.subject == meeting_topic,
        func.date(Meeting.meeting_date) == meeting_date.date()
    ).first()

    if not meeting:
        return jsonify({'error': '找不到符合條件的會議'}), 404

    # 獲取與此會議相關的所有 DiscussionItem
    discussion_items = db.session.query(DiscussionItem).filter_by(meeting_id=meeting.id).all()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5 * inch, leftMargin=0.5 * inch, rightMargin=0.5 * inch)
    story = []

    formatted_date_for_header = meeting.meeting_date.astimezone(timezone('Asia/Taipei')).strftime('%Y年%m月%d日')
    formatted_time_for_header = meeting.meeting_date.astimezone(timezone('Asia/Taipei')).strftime('%H:%M')

    chairman_name = db.session.get(User, meeting.chairman_user_id).name if meeting.chairman_user_id else 'N/A'
    recorder_name = db.session.get(User, meeting.recorder_user_id).name if meeting.recorder_user_id else '無'
    attendees_names = []
    for attendee in meeting.attendees:
        attendees_names.append(attendee.user.name)

    story.append(Paragraph(f"主題: {meeting.subject}", styles['Normal']))
    story.append(Paragraph(f"日期: {formatted_date_for_header}", styles['Normal']))
    story.append(Paragraph(f"時間: {formatted_time_for_header}", styles['Normal']))
    story.append(Paragraph(f"地點: {meeting.location or '未指定'}", styles['Normal']))
    story.append(Paragraph(f"主席: {chairman_name}", styles['Normal']))
    story.append(Paragraph(f"紀錄: {recorder_name}", styles['Normal'])) # 新增紀錄人員
    story.append(Paragraph(f"出席人員: {', '.join(attendees_names) if attendees_names else '無'}", styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("討論議題", styles['h3']))
    if discussion_items:
        # 創建一個新的樣式，用於議題內容，字體更大
        agenda_style = styles['Normal']
        agenda_style.fontSize = 12 # 調整字體大小
        agenda_style.leading = 14 # 行距

        data = [['議題內容']]
        for di in discussion_items:
            try:
                # 假設原始資料是 Big5 編碼，但被錯誤地存儲
                # 我們需要先將其編碼回 bytes (使用 latin-1，因為它能處理任何 byte 值)
                # 然後再用正確的編碼 (big5) 解碼
                topic_text = di.topic.encode('latin-1').decode('big5')
            except (UnicodeEncodeError, UnicodeDecodeError):
                # 如果解碼失敗，則回退到原始的、可能亂碼的文字
                topic_text = di.topic

            # 將換行符統一處理
            topic_text = topic_text.replace('\r\n', '\n').replace('\r', '\n')
            # 將換行符轉換為 <br/> 標籤以供 Paragraph 使用
            topic_text_with_br = topic_text.replace('\n', '<br/>')

            data.append([
                Paragraph(topic_text_with_br, agenda_style)
            ])
        table = Table(data, colWidths=[7.5 * inch]) # 佔滿整個寬度
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'NotoSansCJKtc'),
            ('FONTNAME', (0, 1), (-1, -1), 'NotoSansCJKtc'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("暫無討論議題。", styles['Normal']))

    header_footer_with_context = lambda c, d: _header_footer_template(c, d, 
        meeting_topic="會議議程", 
        meeting_date_str=formatted_date_for_header,
        title="會議議程" # 傳遞標題
    )

    doc.build(story, onFirstPage=header_footer_with_context, onLaterPages=header_footer_with_context)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f"會議議題_{meeting_topic}_{meeting_date_str}.pdf", mimetype='application/pdf')


@app.route('/admin_users')
@super_admin_required
def admin_users():
    users = User.query.all()
    taiwan_tz = timezone('Asia/Taipei')
    for user in users:
        if user.last_login:
            # 將 UTC 時間轉換為台灣時間
            user.last_login_taiwan = user.last_login.replace(tzinfo=utc).astimezone(taiwan_tz)
        else:
            user.last_login_taiwan = None
    return render_template('admin_users.html', users=users, UserLevel=UserLevel)

@app.route('/add_user', methods=['GET', 'POST'])
@super_admin_required
def add_user():
    if request.method == 'POST':
        user_key = request.form.get('user_key')
        name = request.form.get('name')
        email = request.form.get('email')
        role = request.form.get('role')
        department = request.form.get('department')
        unit = request.form.get('unit')
        level = request.form.get('level')
        avatar = request.form.get('avatar')
        password = request.form.get('password')

        if not all([user_key, name, email, role, department, level, avatar, password]):
            flash('所有欄位都是必填的！', 'error')
            return render_template('add_user.html', UserLevel=UserLevel, DEPARTMENT_STRUCTURE=DEPARTMENT_STRUCTURE, UNIT_TO_MAIN_DEPT_MAP=UNIT_TO_MAIN_DEPT_MAP)

        if User.query.filter_by(user_key=user_key).first():
            flash('使用者鍵已存在！', 'error')
            return render_template('add_user.html', UserLevel=UserLevel, DEPARTMENT_STRUCTURE=DEPARTMENT_STRUCTURE, UNIT_TO_MAIN_DEPT_MAP=UNIT_TO_MAIN_DEPT_MAP)
        
        if User.query.filter_by(email=email).first():
            flash('電子郵件已存在！', 'error')
            return render_template('add_user.html', UserLevel=UserLevel, DEPARTMENT_STRUCTURE=DEPARTMENT_STRUCTURE, UNIT_TO_MAIN_DEPT_MAP=UNIT_TO_MAIN_DEPT_MAP)

        new_user = User(
            user_key=user_key,
            name=name,
            email=email,
            role=role,
            department=department,
            unit=unit if unit else None,
            level=level,
            avatar=avatar,
            is_active=True,
            must_change_password=True # 新增使用者預設強制修改密碼
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('使用者新增成功！', 'success')
        return redirect(url_for('admin_users'))
    return render_template('add_user.html', UserLevel=UserLevel, DEPARTMENT_STRUCTURE=DEPARTMENT_STRUCTURE, UNIT_TO_MAIN_DEPT_MAP=UNIT_TO_MAIN_DEPT_MAP)

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@super_admin_required
def edit_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('找不到使用者！', 'error')
        return redirect(url_for('admin_users'))

    # 使用新的輔助函式來決定主管列表
    user_main_dept = user.get_main_department()
    user_level_value = LEVEL_ORDER.get(user.level, 0)

    all_potential_managers = User.query.filter(User.id != user_id).all()
    managers = []
    for p_manager in all_potential_managers:
        if LEVEL_ORDER.get(p_manager.level, 0) > user_level_value:
            if p_manager.get_main_department() == user_main_dept:
                managers.append(p_manager)
    managers.sort(key=lambda m: LEVEL_ORDER.get(m.level, 0), reverse=True)

    if request.method == 'POST':
        user.name = request.form.get('name')
        user.email = request.form.get('email')
        user.role = request.form.get('role')
        user.department = request.form.get('department')
        user.unit = request.form.get('unit') if request.form.get('unit') else None
        user.level = request.form.get('level')
        user.avatar = request.form.get('avatar')
        user.notification_enabled = 'notification_enabled' in request.form

        # 更新直屬主管
        manager_id = request.form.get('manager_id')
        user.manager_id = int(manager_id) if manager_id and manager_id.isdigit() else None

        # 檢查電子郵件是否重複 (排除自己)
        if User.query.filter(User.email == user.email, User.id != user.id).first():
            flash('電子郵件已存在！', 'error')
            return render_template('edit_user.html', user=user, managers=managers, UserLevel=UserLevel, DEPARTMENT_STRUCTURE=DEPARTMENT_STRUCTURE, UNIT_TO_MAIN_DEPT_MAP=UNIT_TO_MAIN_DEPT_MAP)

        try:
            db.session.commit()
            flash('使用者資料更新成功！', 'success')
            return redirect(url_for('admin_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新使用者資料時發生錯誤: {str(e)}', 'error')
            return render_template('edit_user.html', user=user, managers=managers, UserLevel=UserLevel, DEPARTMENT_STRUCTURE=DEPARTMENT_STRUCTURE, UNIT_TO_MAIN_DEPT_MAP=UNIT_TO_MAIN_DEPT_MAP)
    
    return render_template('edit_user.html', user=user, managers=managers, UserLevel=UserLevel, DEPARTMENT_STRUCTURE=DEPARTMENT_STRUCTURE, UNIT_TO_MAIN_DEPT_MAP=UNIT_TO_MAIN_DEPT_MAP)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@super_admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('找不到使用者！', 'error')
        return redirect(url_for('admin_users'))
    
    # 檢查是否為管理員帳號，管理員帳號不允許刪除
    if user.level == UserLevel.ADMIN.value:
        flash('不允許刪除管理員帳號！', 'error')
        return redirect(url_for('admin_users'))

    db.session.delete(user)
    db.session.commit()
    flash('使用者已成功刪除！', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/toggle-status', methods=['POST'])
@super_admin_required
def toggle_user_status(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': '找不到使用者！'}), 404
    
    # 檢查是否為管理員帳號，管理員帳號不允許停用
    if user.level == UserLevel.ADMIN.value:
        return jsonify({'success': False, 'message': '不允許停用管理員帳號！'}), 403

    user.is_active = not user.is_active
    db.session.commit()
    status_text = "啟用" if user.is_active else "停用"
    return jsonify({'success': True, 'message': f'使用者 {user.name} 的狀態已更新為 {status_text}！', 'is_active': user.is_active}), 200

@app.route('/unlock_user_account/<int:user_id>', methods=['POST'])
@super_admin_required
def unlock_user_account(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('找不到使用者！', 'error')
        return redirect(url_for('admin_users'))
    
    user.unlock_account()
    flash(f'使用者 {user.name} 的帳戶已解鎖！', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/reset-password', methods=['POST'])
@super_admin_required
def reset_user_password(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': '找不到使用者！'}), 404
    
    # 生成一個新的隨機密碼
    new_password = secrets.token_urlsafe(8)
    user.set_password(new_password)
    user.must_change_password = True # 強制使用者下次登入時修改密碼
    db.session.commit()
    try:
        if user.notification_enabled:
            subject = "[重要] 您的密碼已重設"
            body = (
                f"您好 {user.name}，\n\n"
                f"您的帳戶密碼已由管理員重設。\n\n"
                f"您的臨時密碼是: {new_password}\n\n"
                f"請立即使用此臨時密碼登入，並設定您的新密碼。\n\n"
                f"請登入系統：\nhttp://192.168.6.119:5001"
            )
            send_mail(subject, body, user.email)
            logging.info(f"Sent 'password reset' notification to {user.email}")
    except Exception as e:
        logging.error(f"Failed to send 'password reset' notification to {user.email}: {e}")
    return jsonify({'message': f'使用者 {user.name} 的密碼已重設。', 'temp_password': new_password})

@app.route('/api/scheduled_notification/<int:notification_id>/send_now', methods=['POST'])
@login_required
def send_scheduled_notification_now(notification_id):
    current_user = get_current_user()
    notification = db.session.get(ScheduledNotification, notification_id)

    if not notification:
        return jsonify({'error': '找不到該通知！'}), 404

    # 權限檢查：只有通知的創建者或管理員可以手動發送
    if notification.user_id != current_user.id and current_user.level != UserLevel.ADMIN.value:
        return jsonify({'error': '您沒有權限手動發送此通知！'}), 403

    recipient_ids = [int(uid) for uid in notification.recipient_user_ids.split(',') if uid.strip()]
    recipients_to_email_list = []
    for user_id in recipient_ids:
        user = db.session.get(User, user_id)
        if user and user.email and user.notification_enabled:
            recipients_to_email_list.append(user.email)
    
    if not recipients_to_email_list:
        return jsonify({'error': '此通知沒有有效的收件人或收件人已禁用通知。'}), 400

    # Convert list of emails to a semicolon-separated string
    recipients_to_email_str = ";".join(recipients_to_email_list)

    subject = f"【手動發送通知】{notification.title}"
    # Convert plain text body to HTML for the mail service and wrap in full HTML structure
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
            <p>這是一則手動發送的通知：</p>
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
        success, message = send_mail(subject, body, recipients_to_email_str)
        if success:
            # Optionally update last_sent_at, but for manual send, it might not be necessary
            # notification.last_sent_at = datetime.now(utc)
            # db.session.commit()
            logging.info(f"Manually sent scheduled notification {notification.id} to {recipients_to_email_str} by {current_user.name}.")
            return jsonify({'message': '通知已成功手動發送！'}), 200
        else:
            logging.error(f"Failed to manually send scheduled notification {notification.id} to {recipients_to_email_str} by {current_user.name}. Error: {message}")
            return jsonify({'error': f'手動發送失敗: {message}'}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred while manually sending notification {notification.id}: {e}", exc_info=True)
        return jsonify({'error': f'手動發送時發生未知錯誤: {str(e)}'}), 500

def init_sample_data():
    """初始化範例資料"""
    if User.query.count() == 0:
        # 定義新的組織結構
        departments = ['製造中心']
        units = {
            '製造中心': ['第一廠', '第三廠', '採購物流部', '品保部'],
            '第一廠': ['裝一課', '裝二課', '組件課'],
            '第三廠': ['裝三課', '加工課'],
            '採購物流部': ['資材成本課', '資材管理課'], # 假設沒有細分單位
            '品保部': ['品管課'] # 假設沒有細分單位
        }
        
        # 建立系統管理員帳號
        users_data = [
            {'user_key': 'admin', 'name': '系統管理員', 'role': '系統管理員', 'department': '資訊部', 'unit': None, 'level': UserLevel.ADMIN.value, 'avatar': '👨‍💻', 'email': 'admin@admin.com'},
            
            # 製造中心-協理
            {'user_key': 'exec_manager', 'name': '鍾協理', 'role': '製造中心-協理', 'department': '製造中心', 'unit': None, 'level': UserLevel.EXECUTIVE_MANAGER.value, 'avatar': '👨‍💼', 'email': 'exec.manager@hartford.com.tw'},

            # 廠長
            {'user_key': 'plant_manager1', 'name': '莊廠長', 'role': '廠長', 'department': '製造中心', 'unit': '第一廠', 'level': UserLevel.PLANT_MANAGER.value, 'avatar': '👨‍🏭', 'email': 'plant.manager1@hartford.com.tw'},
            {'user_key': 'plant_manager3', 'name': '陳廠長', 'role': '廠長', 'department': '製造中心', 'unit': '第三廠', 'level': UserLevel.PLANT_MANAGER.value, 'avatar': '👨‍🏭', 'email': 'plant.manager3@hartford.com.tw'},

            # 經理
            {'user_key': 'manager_purchase', 'name': '張經理', 'role': '經理', 'department': '製造中心', 'unit': '採購物流部', 'level': UserLevel.MANAGER.value, 'avatar': '👨‍💻', 'email': 'manager.purchase@hartford.com.tw'},
            {'user_key': 'manager_qa', 'name': '郭經理', 'role': '副理', 'department': '製造中心', 'unit': '品保部', 'level': UserLevel.MANAGER.value, 'avatar': '👩‍🔬', 'email': 'manager.qa@hartford.com.tw'},

            # 課長
            {'user_key': 'section_chief_z1', 'name': '吳課長', 'role': '課長', 'department': '第一廠', 'unit': '裝一課', 'level': UserLevel.SECTION_CHIEF.value, 'avatar': '👨‍🔧', 'email': 'chief.z1@hartford.com.tw'},
            {'user_key': 'section_chief_z2', 'name': '鄭課長', 'role': '課長', 'department': '第一廠', 'unit': '裝二課', 'level': UserLevel.SECTION_CHIEF.value, 'avatar': '👨‍🔧', 'email': 'chief.z2@hartford.com.tw'},
            {'user_key': 'section_chief_z3', 'name': '徐課長', 'role': '課長', 'department': '第三廠', 'unit': '裝三課', 'level': UserLevel.SECTION_CHIEF.value, 'avatar': '👨‍🔧', 'email': 'chief.z3@hartford.com.tw'},
            {'user_key': 'section_chief_pg', 'name': '高課長', 'role': '課長', 'department': '品保部', 'unit': '品管課', 'level': UserLevel.SECTION_CHIEF.value, 'avatar': '👩‍🏭', 'email': 'chief.pg@hartford.com.tw'},

            # 副課長 (範例)
            {'user_key': 'deputy_chief_z1', 'name': '趙副課長', 'role': '副課長', 'department': '第一廠', 'unit': '裝一課', 'level': UserLevel.DEPUTY_SECTION_CHIEF.value, 'avatar': '👨‍🔧', 'email': 'deputy.chief.z1@hartford.com.tw'},

            # 組長
            {'user_key': 'team_leader_z1_1', 'name': '錢組長', 'role': '組長', 'department': '第一廠', 'unit': '組件課', 'level': UserLevel.TEAM_LEADER.value, 'avatar': '👨‍🏭', 'email': 'leader.z1.1@hartford.com.tw'},
            {'user_key': 'team_leader_z2_1', 'name': '孫組長', 'role': '組長', 'department': '第一廠', 'unit': '裝二課', 'level': UserLevel.TEAM_LEADER.value, 'avatar': '👨‍🏭', 'email': 'leader.z2.1@hartford.com.tw'},
            {'user_key': 'team_leader_z3_1', 'name': '李組長', 'role': '組長', 'department': '第三廠', 'unit': '裝三課', 'level': UserLevel.TEAM_LEADER.value, 'avatar': '👨‍🏭', 'email': 'leader.z3.1@hartford.com.tw'},

            # 作業員 (範例)
            {'user_key': 'staff_z1_1', 'name': '李作業員', 'role': '作業員', 'department': '第一廠', 'unit': '裝一課', 'level': UserLevel.STAFF.value, 'avatar': '👷', 'email': 'staff.z1.1@hartford.com.tw'},
            {'user_key': 'staff_scm', 'name': '王作業員', 'role': '作業員', 'department': '採購物流部', 'unit': '資材成本課', 'level': UserLevel.STAFF.value, 'avatar': '👷', 'email': 'staff.scm@hartford.com.tw'},
            {'user_key': 'staff_qa', 'name': '林作業員', 'role': '作業員', 'department': '品保部', 'unit': '品管課', 'level': UserLevel.STAFF.value, 'avatar': '👷', 'email': 'staff.qa@hartford.com.tw'},
        ]
        
        for user_data in users_data:
            user = User(**user_data)
            if user_data['level'] == UserLevel.ADMIN.value:
                user.set_password('admin')
                user.must_change_password = False # 管理員預設不需要強制修改密碼
            else:
                user.set_password('password123')
                user.must_change_password = True # 其他使用者預設需要強制修改密碼
            db.session.add(user)
        
        db.session.commit()
        
        # 添加範例待辦事項 (根據新的組織結構調整)
        # 製造中心-協理的待辦事項
        exec_manager = User.query.filter_by(user_key='exec_manager').first()
        if exec_manager:
            todos_data = [
                {'title': '製造中心月度營運會議', 'description': '召開製造中心各廠、部主管會議，檢討月度績效', 'status': TodoStatus.IN_PROGRESS.value, 'todo_type': TodoType.CURRENT.value, 'user_id': exec_manager.id, 'due_date': datetime.now(utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=7)},
                {'title': '新產線導入評估', 'description': '評估新產品線導入可行性與效益分析', 'status': TodoStatus.PENDING.value, 'todo_type': TodoType.NEXT.value, 'user_id': exec_manager.id, 'due_date': datetime.now(utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=14)},
            ]
            for todo_data in todos_data:
                todo = Todo(**todo_data)
                history_entry = {
                    'event_type': 'assigned',
                    'timestamp': datetime.now(utc).isoformat(),
                    'actor': {'id': exec_manager.id, 'name': exec_manager.name, 'user_key': exec_manager.user_key},
                    'details': {'assigned_to': {'id': exec_manager.id, 'name': exec_manager.name, 'user_key': exec_manager.user_key}}
                }
                todo.history_log = json.dumps([history_entry])
                db.session.add(todo)

        # 廠長的待辦事項
        plant_manager1 = User.query.filter_by(user_key='plant_manager1').first()
        if plant_manager1:
            todos_data = [
                {'title': '第一廠週生產會議', 'description': '召開第一廠各課主管會議，檢討週生產進度', 'status': TodoStatus.IN_PROGRESS.value, 'todo_type': TodoType.CURRENT.value, 'user_id': plant_manager1.id, 'due_date': datetime.now(utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=7)},
                {'title': '第一廠設備維護計畫', 'description': '制定第一廠年度設備預防性維護計畫', 'status': TodoStatus.PENDING.value, 'todo_type': TodoType.NEXT.value, 'user_id': plant_manager1.id, 'due_date': datetime.now(utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=14)},
            ]
            for todo_data in todos_data:
                todo = Todo(**todo_data)
                history_entry = {
                    'event_type': 'assigned',
                'timestamp': datetime.now(utc).isoformat(),
                    'actor': {'id': plant_manager1.id, 'name': plant_manager1.name, 'user_key': plant_manager1.user_key},
                    'details': {'assigned_to': {'id': plant_manager1.id, 'name': plant_manager1.name, 'user_key': plant_manager1.user_key}}
                }
                todo.history_log = json.dumps([history_entry])
                db.session.add(todo)

        # 課長的待辦事項 (裝一課)
        section_chief_z1 = User.query.filter_by(user_key='section_chief_z1').first()
        if section_chief_z1:
            todos_data = [
                {'title': '裝一課生產排程', 'description': '安排本週裝一課生產排程與人力配置', 'status': TodoStatus.COMPLETED.value, 'todo_type': TodoType.CURRENT.value, 'user_id': section_chief_z1.id, 'due_date': datetime.now(utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=7)},
                {'title': '裝一課品質改善專案', 'description': '推動裝一課品質改善專案，降低不良率', 'status': TodoStatus.IN_PROGRESS.value, 'todo_type': TodoType.CURRENT.value, 'user_id': section_chief_z1.id, 'due_date': datetime.now(utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=14)},
            ]
            for todo_data in todos_data:
                todo = Todo(**todo_data)
                history_entry = {
                    'event_type': 'assigned',
                    'timestamp': datetime.now(utc).isoformat(),
                    'actor': {'id': section_chief_z1.id, 'name': section_chief_z1.name, 'user_key': section_chief_z1.user_key},
                    'details': {'assigned_to': {'id': section_chief_z1.id, 'name': section_chief_z1.name, 'user_key': section_chief_z1.user_key}}
                }
                todo.history_log = json.dumps([history_entry])
                db.session.add(todo)

        # 組長的待辦事項 (裝一課)
        team_leader_z1_1 = User.query.filter_by(user_key='team_leader_z1_1').first()
        if team_leader_z1_1:
            todos_data = [
                {'title': '裝一課組別日報', 'description': '填寫裝一課組別每日生產進度報告', 'status': TodoStatus.IN_PROGRESS.value, 'todo_type': TodoType.CURRENT.value, 'user_id': team_leader_z1_1.id, 'due_date': datetime.now(utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=7)},
            ]
            for todo_data in todos_data:
                todo = Todo(**todo_data)
                history_entry = {
                    'event_type': 'assigned',
                    'timestamp': datetime.now(utc).isoformat(),
                    'actor': {'id': team_leader_z1_1.id, 'name': team_leader_z1_1.name, 'user_key': team_leader_z1_1.user_key},
                    'details': {'assigned_to': {'id': team_leader_z1_1.id, 'name': team_leader_z1_1.name, 'user_key': team_leader_z1_1.user_key}}
                }
                todo.history_log = json.dumps([history_entry])
                db.session.add(todo)

        db.session.commit()








if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_sample_data()
        
    
    # 在開發環境下使用 Flask 內建伺服器，生產環境下應使用 WSGI 伺服器 (如 Waitress)
    # 確保主執行緒不會退出，以便排程器可以繼續運行
    # 注意：排程器已在上面啟動。use_reloader=False 很重要，可避免排程器被啟動兩次。
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5001)
