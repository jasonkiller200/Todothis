from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
import os
import secrets
import json
import copy
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
from dotenv import load_dotenv
from config import LEVEL_ORDER, DEPARTMENT_STRUCTURE, UNIT_TO_MAIN_DEPT_MAP, UserLevel, TodoStatus, TodoType, LOGIN_ATTEMPTS_LIMIT, ACCOUNT_LOCK_MINUTES

load_dotenv() # 加載 .env 文件中的環境變數

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') # 從環境變數中獲取 SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todo_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 配置日誌記錄
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

db = SQLAlchemy(app)

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
            return datetime.utcnow() < self.account_locked_until
        return False
    
    def lock_account(self, minutes=30):
        """鎖定帳戶"""
        self.account_locked_until = datetime.utcnow() + timedelta(minutes=minutes)
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
        todo_owner = User.query.get(todo.user_id)
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

        # 組長和作業員沒有指派權限
        return False

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

    user = db.relationship('User', foreign_keys=[user_id], backref='archived_tasks', lazy=True)
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_user_id], backref='assigned_archived_tasks', lazy=True)

# 認證裝飾器
def login_required(f):
    """要求登入的裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # 檢查使用者是否仍然存在且啟用
        user = User.query.get(session['user_id'])
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
        
        user = User.query.get(session['user_id'])
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
            return redirect(url_for('login'))
        
        user = User.query.get(session['user_id'])
        if not user or user.level != UserLevel.ADMIN.value:
            flash('您沒有權限執行此操作', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """取得當前登入使用者"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
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
            user.last_login = datetime.utcnow()
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

def _build_organization_structure(all_users, user_todos_map, director):
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

    # 最高層級主管 (製造中心-協理)
    director = User.query.filter_by(level=UserLevel.EXECUTIVE_MANAGER.value).first()
    if director:
        director_current_todos = user_todos_map.get(director.id, [])
        director.total_tasks = len(director_current_todos)
        director.completed_tasks = sum(1 for todo in director_current_todos if todo.status == TodoStatus.COMPLETED.value)
    
    all_users = User.query.filter(User.level != UserLevel.ADMIN.value).all()

    departments = _build_organization_structure(all_users, user_todos_map, director)

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
    
    current_todos = Todo.query.filter_by(user_id=user.id, todo_type=TodoType.CURRENT.value).all()
    next_todos = Todo.query.filter_by(user_id=user.id, todo_type=TodoType.NEXT.value).all()
    
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
            'history_log': json.loads(todo.history_log) if todo.history_log else [],
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
            'can_assign': current_user.level in [UserLevel.ADMIN.value, UserLevel.EXECUTIVE_MANAGER.value, UserLevel.PLANT_MANAGER.value, UserLevel.MANAGER.value, UserLevel.SECTION_CHIEF.value],
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
    
    # 驗證輸入資料
    if not all(key in data for key in ['title', 'description', 'status', 'type']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    todo = Todo(
        title=data['title'],
        description=data['description'],
        status=data['status'],
        todo_type=data['type'],
        user_id=target_user.id,
        assigned_by_user_id=current_user.id if target_user.id != current_user.id else None # 如果是指派，記錄指派人
    )
    
    # 初始化 history_log
    history_entry = {
        'event_type': 'assigned',
        'timestamp': datetime.utcnow().isoformat(),
        'actor': {'id': current_user.id, 'name': current_user.name, 'user_key': current_user.user_key},
        'details': {'assigned_to': {'id': target_user.id, 'name': target_user.name, 'user_key': target_user.user_key}}
    }
    if todo.assigned_by_user_id: # If it was assigned by someone else
        history_entry['details']['assigned_by'] = {'id': current_user.id, 'name': current_user.name, 'user_key': current_user.user_key}
    
    todo.history_log = json.dumps([history_entry])
    
    db.session.add(todo)
    db.session.commit()
    
    return jsonify({'message': 'Todo added successfully', 'id': todo.id})

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
        user = User.query.get(todo.user_id)
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
            
            user_data['tasks'].append({
                'title': todo.title,
                'description': todo.description,
                'status': todo.status,
                'archived_at': todo.archived_at.isoformat(),
                'history_log': json.loads(todo.history_log) if todo.history_log else []
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

    today = datetime.utcnow()
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

    today = datetime.utcnow()
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

@app.route('/api/todo/<int:todo_id>/status', methods=['PUT'])
@login_required
def update_todo_status(todo_id):
    current_user = get_current_user()
    todo = Todo.query.get_or_404(todo_id)
    data = request.get_json()
    new_status = data.get('status')
    uncompleted_reason = data.get('uncompleted_reason', None)

    if not new_status or new_status not in [TodoStatus.PENDING.value, TodoStatus.IN_PROGRESS.value, TodoStatus.COMPLETED.value, TodoStatus.UNCOMPLETED.value]:
        return jsonify({'error': '無效的狀態'}), 400

    # 只有待辦事項的擁有者才能修改狀態
    if todo.user_id != current_user.id:
        return jsonify({'error': '您沒有權限修改此待辦事項的狀態'}), 403

    old_status = todo.status

    # 讀取現有的 history_log
    history = json.loads(todo.history_log or '[]')

    if new_status == TodoStatus.UNCOMPLETED.value:
        # 記錄未完成事件
        history_entry = {
            'event_type': 'status_changed',
            'timestamp': datetime.utcnow().isoformat(),
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
            'timestamp': datetime.utcnow().isoformat(),
            'actor': {'id': current_user.id, 'name': current_user.name, 'user_key': current_user.user_key},
            'details': {'old_status': old_status, 'new_status': new_status}
        }
        history.append(history_entry)
        todo.history_log = json.dumps(history)
        todo.status = new_status

    db.session.commit()
    return jsonify({'message': '待辦事項狀態已更新'})
@app.route('/admin/users')
@super_admin_required
def admin_users():
    users = User.query.filter(User.level != UserLevel.ADMIN.value).all()  # 不顯示其他管理員帳號

    # 定義組織結構數據，用於前端下拉選單
    departments_list = ['製造中心', '採購物流部', '品保部']
    units_map = {
        '製造中心': ['第一廠', '第三廠'],
        '第一廠': ['裝一課', '裝二課', '裝三課'],
        '第三廠': ['品管課', '資材成本課', '資材管理課'],
        '採購物流部': [],
        '品保部': []
    }

    return render_template('admin_users.html', 
                           users=users,
                           departments_list=departments_list,
                           units_map=units_map)

@app.route('/admin/users/add', methods=['GET', 'POST'])
@super_admin_required
def add_user():
    if request.method == 'POST':
        data = request.form
        
        # 檢查必填欄位
        required_fields = ['user_key', 'name', 'role', 'department', 'level', 'email']
        if not all(field in data and data[field].strip() for field in required_fields):
            flash('請填寫所有必填欄位', 'error')
            return render_template('add_user.html')
        
        # 檢查 user_key 和 email 是否已存在
        if User.query.filter_by(user_key=data['user_key']).first():
            flash('使用者代碼已存在', 'error')
            return render_template('add_user.html')
        
        if User.query.filter_by(email=data['email']).first():
            flash('電子郵件已存在', 'error')
            return render_template('add_user.html')
        
        # 建立新使用者
        new_user = User(
            user_key=data['user_key'],
            name=data['name'],
            role=data['role'],
            department=data['department'],
            unit=data.get('unit'), # 新增 unit 欄位
            level=data['level'],
            avatar=data.get('avatar', '👤'),
            email=data['email'],
            must_change_password=True # 新增使用者預設需要強制修改密碼
        )
        
        # 設置預設密碼
        default_password = data.get('password', 'password123')
        new_user.set_password(default_password)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f'使用者 {new_user.name} 已成功新增', 'success')
            return redirect(url_for('admin_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'新增使用者時發生錯誤: {str(e)}', 'error')
            return render_template('add_user.html')
    
    return render_template('add_user.html')

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@super_admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # 防止編輯管理員帳號
    if user.level == UserLevel.ADMIN.value:
        flash('無法編輯管理員帳號', 'error')
        return redirect(url_for('admin_users'))
    
    if request.method == 'POST':
        data = request.form
        
        # 檢查必填欄位
        required_fields = ['user_key', 'name', 'role', 'department', 'level', 'email']
        if not all(field in data and data[field].strip() for field in required_fields):
            flash('請填寫所有必填欄位', 'error')
            return render_template('edit_user.html', user=user)
        
        # 檢查 user_key 和 email 是否與其他使用者衝突
        existing_user_key = User.query.filter(User.user_key == data['user_key'], User.id != user_id).first()
        if existing_user_key:
            flash('使用者代碼已存在', 'error')
            return render_template('edit_user.html', user=user)
        
        existing_email = User.query.filter(User.email == data['email'], User.id != user_id).first()
        if existing_email:
            flash('電子郵件已存在', 'error')
            return render_template('edit_user.html', user=user)
        
        # 更新使用者資料
        user.user_key = data['user_key']
        user.name = data['name']
        user.role = data['role']
        user.department = data['department']
        user.unit = data.get('unit') # 更新 unit 欄位
        user.level = data['level']
        user.avatar = data.get('avatar', user.avatar)
        user.email = data['email']
        
        # 如果有提供新密碼，則更新密碼
        if data.get('password'):
            user.set_password(data['password'])
        
        try:
            db.session.commit()
            flash(f'使用者 {user.name} 資料已更新', 'success')
            return redirect(url_for('admin_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新使用者時發生錯誤: {str(e)}', 'error')
            return render_template('edit_user.html', user=user)
    
    return render_template('edit_user.html', user=user)

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@super_admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # 防止刪除管理員帳號
    if user.level == UserLevel.ADMIN.value:
        return jsonify({'error': '無法刪除管理員帳號'}), 400
    
    try:
        # 刪除相關的待辦事項
        Todo.query.filter_by(user_id=user_id).delete()
        
        # 刪除使用者
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'message': f'使用者 {user.name} 已刪除'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'刪除使用者時發生錯誤: {str(e)}'}), 500

@app.route('/admin/user/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    current_user = get_current_user()
    target_user = User.query.get_or_404(user_id)
    
    # 防止自己停用自己
    if target_user.id == current_user.id:
        return jsonify({'error': 'Cannot disable your own account'}), 400
    
    target_user.is_active = not target_user.is_active
    db.session.commit()
    
    status = '啟用' if target_user.is_active else '停用'
    return jsonify({'message': f'使用者 {target_user.name} 已{status}', 'is_active': target_user.is_active})

@app.route('/admin/user/<int:user_id>/unlock', methods=['POST'])
@admin_required
def unlock_user_account(user_id):
    user = User.query.get_or_404(user_id)
    user.unlock_account()
    return jsonify({'message': f'使用者 {user.name} 的帳戶已解鎖'})

@app.route('/admin/user/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    user = User.query.get_or_404(user_id)
    
    # 重置為預設密碼
    temp_password = 'password123'
    user.set_password(temp_password)
    user.must_change_password = True # 重置密碼後強制使用者修改密碼
    db.session.commit()
    
    return jsonify({
        'message': f'使用者 {user.name} 的密碼已重置為預設密碼 "password123"'
    })

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
                {'title': '製造中心月度營運會議', 'description': '召開製造中心各廠、部主管會議，檢討月度績效', 'status': TodoStatus.IN_PROGRESS.value, 'todo_type': TodoType.CURRENT.value, 'user_id': exec_manager.id},
                {'title': '新產線導入評估', 'description': '評估新產品線導入可行性與效益分析', 'status': TodoStatus.PENDING.value, 'todo_type': TodoType.NEXT.value, 'user_id': exec_manager.id},
            ]
            for todo_data in todos_data:
                todo = Todo(**todo_data)
                history_entry = {
                    'event_type': 'assigned',
                    'timestamp': datetime.utcnow().isoformat(),
                    'actor': {'id': exec_manager.id, 'name': exec_manager.name, 'user_key': exec_manager.user_key},
                    'details': {'assigned_to': {'id': exec_manager.id, 'name': exec_manager.name, 'user_key': exec_manager.user_key}}
                }
                todo.history_log = json.dumps([history_entry])
                db.session.add(todo)

        # 廠長的待辦事項
        plant_manager1 = User.query.filter_by(user_key='plant_manager1').first()
        if plant_manager1:
            todos_data = [
                {'title': '第一廠週生產會議', 'description': '召開第一廠各課主管會議，檢討週生產進度', 'status': TodoStatus.IN_PROGRESS.value, 'todo_type': TodoType.CURRENT.value, 'user_id': plant_manager1.id},
                {'title': '第一廠設備維護計畫', 'description': '制定第一廠年度設備預防性維護計畫', 'status': TodoStatus.PENDING.value, 'todo_type': TodoType.NEXT.value, 'user_id': plant_manager1.id},
            ]
            for todo_data in todos_data:
                todo = Todo(**todo_data)
                history_entry = {
                    'event_type': 'assigned',
                    'timestamp': datetime.utcnow().isoformat(),
                    'actor': {'id': plant_manager1.id, 'name': plant_manager1.name, 'user_key': plant_manager1.user_key},
                    'details': {'assigned_to': {'id': plant_manager1.id, 'name': plant_manager1.name, 'user_key': plant_manager1.user_key}}
                }
                todo.history_log = json.dumps([history_entry])
                db.session.add(todo)

        # 課長的待辦事項 (裝一課)
        section_chief_z1 = User.query.filter_by(user_key='section_chief_z1').first()
        if section_chief_z1:
            todos_data = [
                {'title': '裝一課生產排程', 'description': '安排本週裝一課生產排程與人力配置', 'status': TodoStatus.COMPLETED.value, 'todo_type': TodoType.CURRENT.value, 'user_id': section_chief_z1.id},
                {'title': '裝一課品質改善專案', 'description': '推動裝一課品質改善專案，降低不良率', 'status': TodoStatus.IN_PROGRESS.value, 'todo_type': TodoType.CURRENT.value, 'user_id': section_chief_z1.id},
            ]
            for todo_data in todos_data:
                todo = Todo(**todo_data)
                history_entry = {
                    'event_type': 'assigned',
                    'timestamp': datetime.utcnow().isoformat(),
                    'actor': {'id': section_chief_z1.id, 'name': section_chief_z1.name, 'user_key': section_chief_z1.user_key},
                    'details': {'assigned_to': {'id': section_chief_z1.id, 'name': section_chief_z1.name, 'user_key': section_chief_z1.user_key}}
                }
                todo.history_log = json.dumps([history_entry])
                db.session.add(todo)

        # 組長的待辦事項 (裝一課)
        team_leader_z1_1 = User.query.filter_by(user_key='team_leader_z1_1').first()
        if team_leader_z1_1:
            todos_data = [
                {'title': '裝一課組別日報', 'description': '填寫裝一課組別每日生產進度報告', 'status': TodoStatus.IN_PROGRESS.value, 'todo_type': TodoType.CURRENT.value, 'user_id': team_leader_z1_1.id},
            ]
            for todo_data in todos_data:
                todo = Todo(**todo_data)
                history_entry = {
                    'event_type': 'assigned',
                    'timestamp': datetime.utcnow().isoformat(),
                    'actor': {'id': team_leader_z1_1.id, 'name': team_leader_z1_1.name, 'user_key': team_leader_z1_1.user_key},
                    'details': {'assigned_to': {'id': team_leader_z1_1.id, 'name': team_leader_z1_1.name, 'user_key': team_leader_z1_1.user_key}}
                }
                todo.history_log = json.dumps([history_entry])
                db.session.add(todo)

        db.session.commit()


def transfer_and_archive_todos():
    """每週任務轉移和歸檔的排程任務"""
    with app.app_context():
        logging.info(f"Running weekly todo transfer and archive job...")
        
        # 1. 轉移下週計畫到本週進度
        next_week_todos = Todo.query.filter_by(todo_type=TodoType.NEXT.value).all()
        for todo in next_week_todos:
            todo.todo_type = TodoType.CURRENT.value
            # 記錄自動轉移事件
            history = json.loads(todo.history_log or '[]')
            history.append({
                'event_type': 'auto_transfer',
                'timestamp': datetime.utcnow().isoformat(),
                'actor': {'name': 'System', 'user_key': 'system'},
                'details': {'from_type': 'next', 'to_type': 'current'}
            })
            todo.history_log = json.dumps(history)
            db.session.add(todo)
        db.session.commit()
        logging.info(f"Transferred {len(next_week_todos)} next week todos to current.")

        # 2. 歸檔已完成的本週進度
        completed_current_todos = Todo.query.filter_by(todo_type=TodoType.CURRENT.value, status=TodoStatus.COMPLETED.value).all()
        for todo in completed_current_todos:
            # 記錄歸檔事件
            history = json.loads(todo.history_log or '[]')
            history.append({
                'event_type': 'archived',
                'timestamp': datetime.utcnow().isoformat(),
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
                archived_at=datetime.utcnow()
            )
            db.session.add(archived_todo)
            db.session.delete(todo) # 從主表刪除
        db.session.commit()
        logging.info(f"Archived {len(completed_current_todos)} completed current todos.")
        logging.info(f"Weekly todo job finished.")


# 初始化排程器
scheduler = BackgroundScheduler()
# 設定時區為台灣時間 (Asia/Taipei)
taiwan_tz = timezone('Asia/Taipei')

# 每週一 00:01 執行任務轉移和歸檔
scheduler.add_job(transfer_and_archive_todos, 'cron', day_of_week='mon', hour=0, minute=1, timezone=taiwan_tz)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_sample_data()
    
    # 啟動排程器
    scheduler.start()

    # 確保主執行緒不會退出，以便排程器可以繼續運行
    try:
        app.run(debug=True, use_reloader=False) # use_reloader=False 是為了避免在 debug 模式下重複啟動排程器
    except (KeyboardInterrupt, SystemExit):
        # 關閉排程器
        scheduler.shutdown()