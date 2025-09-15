import tkinter as tk
from tkinter import ttk, messagebox, font as tkFont
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, inspect
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import os
import json
from enum import Enum
import traceback # 為了更詳細的錯誤輸出

# --- 核心設定與模型定義 (與之前相同) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'todo_system.db')
os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class UserLevel(Enum):
    ADMIN = "admin"
    EXECUTIVE_MANAGER = "executive-manager"
    PLANT_MANAGER = "plant-manager"
    MANAGER = "manager"
    ASSISTANT_MANAGER = "assistant-manager"
    SECTION_CHIEF = "section-chief"
    DEPUTY_SECTION_CHIEF = "deputy-section-chief"
    TEAM_LEADER = "team-leader"
    STAFF = "staff"

class TodoStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    UNCOMPLETED = "uncompleted"

class TodoType(Enum):
    CURRENT = "current"
    NEXT = "next"

class MeetingTaskStatus(Enum):
    UNASSIGNED = "unassigned"
    ASSIGNED = "assigned"
    RESOLVED_EXECUTING = "resolved_executing"
    AGREED_FINALIZED = "agreed_finalized"
    COMPLETED = "completed"
    IN_PROGRESS_TODO = "in_progress_todo"
    UNCOMPLETED_TODO = "uncompleted_todo"

class MeetingTaskType(Enum):
    TRACKING = "tracking"
    RESOLUTION = "resolution"

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    user_key = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    unit = Column(String(100), nullable=True)
    level = Column(String(50), nullable=False)
    avatar = Column(String(10), nullable=False, default='default')
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    failed_login_attempts = Column(Integer, default=0)
    account_locked_until = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    must_change_password = Column(Boolean, default=True)

class Todo(Base):
    __tablename__ = 'todo'
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default=TodoStatus.PENDING.value)
    todo_type = Column(String(20), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    assigned_by_user_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    history_log = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    due_date = Column(DateTime, nullable=False)
    meeting_task_id = Column(Integer, ForeignKey('meeting_task.id'), nullable=True)
    user = relationship('User', foreign_keys=[user_id])
    assigned_by = relationship('User', foreign_keys=[assigned_by_user_id])

class ArchivedTodo(Base):
    __tablename__ = 'archived_todo'
    id = Column(Integer, primary_key=True)
    original_todo_id = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False)
    todo_type = Column(String(20), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    assigned_by_user_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    history_log = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    archived_at = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, nullable=True)
    user = relationship('User', foreign_keys=[user_id])
    assigned_by = relationship('User', foreign_keys=[assigned_by_user_id])

class Meeting(Base):
    __tablename__ = 'meeting'
    id = Column(Integer, primary_key=True)
    subject = Column(String(200), nullable=False)
    meeting_date = Column(DateTime, nullable=False)
    chairman_user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    recorder_user_id = Column(Integer, ForeignKey('user.id'), nullable=True) # 新增紀錄人員
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chairman = relationship('User', foreign_keys=[chairman_user_id])
    recorder = relationship('User', foreign_keys=lambda: [Meeting.recorder_user_id])
    attendees = relationship('MeetingAttendee', backref='meeting', cascade='all, delete-orphan')
    discussion_items = relationship('DiscussionItem', backref='meeting', cascade='all, delete-orphan')

class MeetingAttendee(Base):
    __tablename__ = 'meeting_attendee'
    meeting_id = Column(Integer, ForeignKey('meeting.id'), primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), primary_key=True)
    
    user = relationship('User')

class DiscussionItem(Base):
    __tablename__ = 'discussion_item'
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey('meeting.id'), nullable=False, unique=True)
    topic = Column(Text, nullable=False)
    reporter_user_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reporter = relationship('User', foreign_keys=[reporter_user_id])
    

class MeetingTask(Base):
    __tablename__ = 'meeting_task'
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey('meeting.id'), nullable=False) # 直接關聯到會議
    task_type = Column(String(50), nullable=False)
    task_description = Column(Text, nullable=False)
    assigned_by_user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    assigned_to_user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    controller_user_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    expected_completion_date = Column(DateTime, nullable=True)
    actual_completion_date = Column(DateTime, nullable=True)
    uncompleted_reason_from_todo = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default=MeetingTaskStatus.UNASSIGNED.value)
    is_assigned_to_todo = Column(Boolean, default=False)
    todo_id = Column(Integer, ForeignKey('todo.id'), unique=True, nullable=True)
    history_log = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assigned_by_user = relationship('User', foreign_keys=[assigned_by_user_id])
    assigned_to_user = relationship('User', foreign_keys=[assigned_to_user_id])
    
    controller_user = relationship('User', foreign_keys=[controller_user_id])
    todo = relationship('Todo', foreign_keys=[todo_id], backref='meeting_task_link', uselist=False)
    meeting = relationship('Meeting', backref='meeting_tasks', lazy=True)

# --- Tkinter 圖形化介面應用程式 ---

class DatabaseManagerApp:
    def __init__(self, root):
        # ... __init__ 保持不變 ...
        self.root = root
        self.root.title("Todothis 資料庫管理工具 (除錯版)")
        self.root.geometry("1400x800")
        self.session = Session()
        self.current_table = None
        self.user_map = {}
        self.meeting_task_map = {} # 新增初始化
        self.setup_ui()
        self.load_tables()
        self.update_user_map()
        self.update_meeting_task_map() # 新增呼叫

    def setup_ui(self):
        # ... setup_ui 保持不變 ...
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        ttk.Label(top_frame, text="選擇資料表:").pack(side=tk.LEFT, padx=5)
        self.table_selector = ttk.Combobox(top_frame, state="readonly", width=30)
        self.table_selector.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.table_selector.bind("<<ComboboxSelected>>", self.on_table_selected)
        data_frame = ttk.Frame(self.root, padding="10")
        data_frame.pack(fill=tk.BOTH, expand=True)
        v_scroll = ttk.Scrollbar(data_frame, orient=tk.VERTICAL)
        h_scroll = ttk.Scrollbar(data_frame, orient=tk.HORIZONTAL)
        self.tree = ttk.Treeview(data_frame, show="headings", yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        v_scroll.config(command=self.tree.yview)
        h_scroll.config(command=self.tree.xview)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)
        button_frame = ttk.Frame(self.root, padding="10")
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="新增", command=self.add_record).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="編輯", command=self.edit_record).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="刪除", command=self.delete_record).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="重新整理", command=self.refresh_data).pack(side=tk.LEFT, padx=5)

    def load_tables(self):
        # ... load_tables 保持不變 ...
        self.models = {'User': User, 'Todo': Todo, 'ArchivedTodo': ArchivedTodo, 'Meeting': Meeting, 'MeetingAttendee': MeetingAttendee, 'DiscussionItem': DiscussionItem, 'MeetingTask': MeetingTask}
        table_names = sorted(list(self.models.keys()))
        self.table_selector['values'] = table_names
        if table_names:
            self.table_selector.set(table_names[0])
            self.on_table_selected(None)

    def update_user_map(self):
        # ... update_user_map 保持不變 ...
        try:
            users = self.session.query(User).all()
            self.user_map = {user.id: user.name for user in users}
        except Exception as e:
            messagebox.showerror("錯誤", f"無法載入使用者列表: {e}")
            self.session.rollback()

    def update_meeting_task_map(self):
        try:
            meeting_tasks = self.session.query(MeetingTask).all()
            self.meeting_task_map = {task.id: task.task_description for task in meeting_tasks}
        except Exception as e:
            messagebox.showerror("錯誤", f"無法載入會議任務列表: {e}")
            self.session.rollback()

    def on_table_selected(self, event):
        # ... on_table_selected 保持不變 ...
        selected_table_name = self.table_selector.get()
        self.current_table = self.models.get(selected_table_name)
        if self.current_table:
            self.refresh_data()
        else:
            messagebox.showerror("錯誤", "無效的資料表選擇。")

    # vvvvvvvvvv 已更新的函式 vvvvvvvvvv
    def refresh_data(self):
        print("\n--- [開始刷新資料] ---")
        # 清空舊資料
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.tree["columns"] = []

        if not self.current_table:
            print("[警告] 沒有選擇任何資料表。")
            return
            
        print(f"選擇的資料表: {self.current_table.__name__}")
        self.update_user_map() # 每次刷新都更新使用者列表
        self.update_meeting_task_map() # 每次刷新都更新會議任務列表

        # 設定欄位
        try: # <--- 新增 try 區塊來捕捉欄位定義錯誤
            columns = [c.name for c in self.current_table.__table__.columns]
            print(f"成功讀取到 {len(columns)} 個欄位: {columns}") # <--- 新增除錯輸出
            self.tree["columns"] = tuple(columns)
            
            for col in columns:
                self.tree.heading(col, text=col, command=lambda c=col: self.sort_column(c, False))
                col_width = tkFont.Font().measure(col) + 20
                self.tree.column(col, width=max(col_width, 150), stretch=tk.YES)
            print("Treeview 欄位標題設定完成。")

            # 載入資料
            records = self.session.query(self.current_table).all()
            print(f"從資料庫查詢到 {len(records)} 筆記錄。")
            
            for i, record in enumerate(records):
                values = []
                for col in columns:
                    val = getattr(record, col)
                    # 優化顯示
                    if isinstance(val, datetime):
                        values.append(val.strftime('%Y-%m-%d %H:%M:%S') if val else "")
                    elif col.endswith('_user_id') and val in self.user_map:
                        values.append(f"{val} ({self.user_map[val]})")
                    elif col == 'history_log' and val:
                        try:
                            entries = json.loads(val)
                            formatted = "\n".join([f"{e.get('timestamp','')} - {e.get('actor',{}).get('name','N/A')}: {e.get('event_type','')}" for e in entries])
                            values.append(formatted)
                        except (json.JSONDecodeError, TypeError):
                            values.append(val)
                    else:
                        values.append(val if val is not None else "")
                
                if len(values) != len(columns):
                    print(f"[嚴重錯誤] 記錄 ID {record.id} 的值數量 ({len(values)}) 與欄位數量 ({len(columns)}) 不匹配！")
                    continue

                if self.current_table == MeetingAttendee:
                    # 對於 MeetingAttendee，使用複合主鍵作為 iid
                    item_id = f"{record.meeting_id}-{record.user_id}"
                else:
                    item_id = record.id

                self.tree.insert("", "end", values=tuple(values), iid=item_id)
            
            print(f"資料載入完成，共插入 {len(self.tree.get_children())} 行。")

        except Exception as e:
            print("\n!!!!!! 在 refresh_data 過程中發生嚴重錯誤 !!!!!!")
            traceback.print_exc() # <--- 打印完整的錯誤追蹤
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
            
            messagebox.showerror("資料庫錯誤", f"載入資料失敗: {e}")
            self.session.rollback()
        
        print("--- [刷新資料結束] ---\n")
    # ^^^^^^^^^^ 已更新的函式 ^^^^^^^^^^

    def sort_column(self, col, reverse):
        # ... sort_column 保持不變 ...
        data = [(self.tree.set(child, col), child) for child in self.tree.get_children('')]
        try:
            data.sort(key=lambda t: (datetime.fromisoformat(t[0]) if '-' in t[0] and ':' in t[0] else float(t[0].split(' ')[0])), reverse=reverse)
        except (ValueError, TypeError):
            data.sort(reverse=reverse)
        for index, (val, child) in enumerate(data):
            self.tree.move(child, '', index)
        self.tree.heading(col, command=lambda: self.sort_column(col, not reverse))

    def add_record(self):
        # ... add_record 保持不變 ...
        if not self.current_table:
            messagebox.showwarning("警告", "請先選擇一個資料表。")
            return
        self.open_edit_window(None)

    def edit_record(self):
        # ... edit_record 保持不變 ...
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("警告", "請選擇要編輯的記錄。")
            return
        record = self.session.query(self.current_table).get(int(selected_item))
        if record:
            self.open_edit_window(record)
        else:
            messagebox.showerror("錯誤", "找不到選定的記錄。")

    def delete_record(self):
        # ... delete_record 保持不變 ...
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("警告", "請選擇要刪除的記錄。")
            return
        record_id = int(selected_item)
        if messagebox.askyesno("確認刪除", f"確定要刪除 ID 為 {record_id} 的記錄嗎？\n此操作無法復原，且可能影響關聯資料。"):
            try:
                record = self.session.query(self.current_table).get(record_id)
                if record:
                    self.session.delete(record)
                    self.session.commit()
                    messagebox.showinfo("成功", "記錄已成功刪除。")
                    self.refresh_data()
                else:
                    messagebox.showerror("錯誤", "找不到要刪除的記錄。")
            except Exception as e:
                self.session.rollback()
                messagebox.showerror("錯誤", f"刪除記錄失敗: {e}\n\n可能是因為此記錄被其他資料表引用(外鍵約束)。")

    def open_edit_window(self, record=None):
        # ... open_edit_window 保持不變 ...
        # (此函式非常長，為節省篇幅此處省略，請使用您原本的版本即可)
        edit_window = tk.Toplevel(self.root)
        edit_window.title("編輯記錄" if record else "新增記錄")
        edit_window.geometry("800x600")
        edit_window.transient(self.root)
        edit_window.grab_set()
        main_frame = ttk.Frame(edit_window)
        main_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        form_frame = ttk.Frame(canvas, padding="10")
        form_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        entries = {}
        inspector = inspect(self.current_table)
        columns = inspector.c
        enum_map = {
            'level': UserLevel,
            'status': TodoStatus if self.current_table in [Todo, ArchivedTodo] else MeetingTaskStatus,
            'todo_type': TodoType,
            'task_type': MeetingTaskType,
        }
        for col in columns:
            frame = ttk.Frame(form_frame)
            frame.pack(fill=tk.X, padx=5, pady=4)
            label = ttk.Label(frame, text=f"{col.name}:", width=20, anchor='w')
            label.pack(side=tk.LEFT)
            is_readonly = col.primary_key or col.name in ['created_at', 'updated_at', 'archived_at']
            current_value = getattr(record, col.name) if record else col.default.arg if col.default else None
            widget = None
            widget_type = None
            if col.foreign_keys:
                if 'user' in col.name: # 處理 user_id 和 assigned_by_user_id
                    widget = ttk.Combobox(frame, state='readonly' if is_readonly else 'normal')
                    user_list = [""] + [f"{uid} - {uname}" for uid, uname in sorted(self.user_map.items(), key=lambda item: item[1])]
                    widget['values'] = user_list
                    if current_value:
                        widget.set(f"{current_value} - {self.user_map.get(current_value, '未知使用者')}")
                    widget_type = 'foreign_key_combobox_user'
                elif col.name == 'meeting_task_id' and self.current_table == Todo: # 處理 Todo 的 meeting_task_id
                    widget = ttk.Combobox(frame, state='readonly' if is_readonly else 'normal')
                    # 格式化 MeetingTask 列表為 "ID - 描述"
                    task_list = [""] + [f"{tid} - {tdesc}" for tid, tdesc in sorted(self.meeting_task_map.items(), key=lambda item: item[0])]
                    widget['values'] = task_list
                    if current_value:
                        widget.set(f"{current_value} - {self.meeting_task_map.get(current_value, '未知會議任務')}")
                    widget_type = 'foreign_key_combobox_meeting_task'
                elif col.name == 'todo_id' and self.current_table == MeetingTask: # 處理 MeetingTask 的 todo_id
                    widget = ttk.Combobox(frame, state='readonly' if is_readonly else 'normal')
                    # 獲取所有 Todo 的 ID 和 Title
                    todo_records = self.session.query(Todo).all()
                    todo_list = [""] + [f"{t.id} - {t.title}" for t in sorted(todo_records, key=lambda t: t.id)]
                    widget['values'] = todo_list
                    if current_value:
                        # 查找對應的 Todo 標題
                        current_todo = self.session.query(Todo).get(current_value)
                        if current_todo:
                            widget.set(f"{current_value} - {current_todo.title}")
                        else:
                            widget.set(f"{current_value} - 未知待辦事項")
                    widget_type = 'foreign_key_combobox_todo'
            elif isinstance(col.type, Boolean):
                var = tk.BooleanVar(value=bool(current_value))
                widget = ttk.Checkbutton(frame, variable=var, state=tk.DISABLED if is_readonly else tk.NORMAL)
                widget_type = 'checkbutton'
            elif col.name in enum_map:
                widget = ttk.Combobox(frame, state='readonly' if is_readonly else 'normal')
                widget['values'] = [e.value for e in enum_map[col.name]]
                if current_value:
                    widget.set(current_value)
                elif not record and col.default:
                     widget.set(col.default.arg)
                widget_type = 'enum_combobox'
            elif isinstance(col.type, Text):
                widget = tk.Text(frame, height=5, width=60)
                if current_value:
                    widget.insert('1.0', str(current_value))
                if is_readonly:
                    widget.config(state=tk.DISABLED)
                widget_type = 'text'
            else:
                widget = ttk.Entry(frame)
                if current_value is not None:
                    if isinstance(current_value, datetime):
                        widget.insert(0, current_value.isoformat().split('.')[0])
                    else:
                        widget.insert(0, str(current_value))
                if isinstance(col.type, DateTime):
                     label.config(text=f"{col.name} (YYYY-MM-DD HH:MM:SS):")
                if is_readonly:
                    widget.config(state='readonly')
                widget_type = 'entry'
            if widget:
                widget.pack(side=tk.RIGHT, fill=tk.X, expand=True)
                if widget_type == 'checkbutton':
                    entries[col.name] = (widget, var)
                else:
                    entries[col.name] = (widget, widget_type) # 儲存 widget_type
        def save_changes():
            data = {}
            try:
                for col in columns:
                    col_name = col.name
                    if col.primary_key and not record: continue
                    if col_name in ['created_at', 'updated_at', 'archived_at']: continue
                    widget_tuple = entries.get(col_name)
                    if not widget_tuple: continue
                    widget = widget_tuple[0]
                    widget_type = widget_tuple[1] if len(widget_tuple) > 1 else None # 獲取 widget_type
                    value = None
                    if widget_type and 'foreign_key_combobox' in widget_type:
                        selected = widget.get()
                        value = int(selected.split(' - ')[0]) if selected else None
                    elif isinstance(widget, ttk.Checkbutton):
                        value = widget_tuple[1].get()
                    elif isinstance(widget, tk.Text):
                        value = widget.get('1.0', 'end-1c') # 獲取 Text 控件的內容
                        if not value.strip(): # 如果內容為空字串，則設為 None
                            value = None
                    elif isinstance(widget, ttk.Entry):
                        value = widget.get().strip() or None
                    elif isinstance(widget, ttk.Combobox): # 處理非外鍵的 Combobox (例如 Enum)
                        value = widget.get() if widget.get() else None

                    if value is None and not col.nullable and not col.primary_key:
                        raise ValueError(f"欄位 '{col_name}' 不可為空。")
                    if value is not None:
                        if isinstance(col.type, Integer) and not col.foreign_keys: data[col_name] = int(value)
                        elif isinstance(col.type, DateTime): data[col_name] = datetime.fromisoformat(value)
                        elif isinstance(col.type, Boolean): data[col_name] = value
                        else: data[col_name] = value
                    else:
                        data[col_name] = None
                if record:
                    for key, value in data.items():
                        setattr(record, key, value)
                else:
                    new_record = self.current_table(**data)
                    self.session.add(new_record)
                self.session.commit()
                messagebox.showinfo("成功", "記錄已成功儲存。")
                edit_window.destroy()
                self.refresh_data()
            except Exception as e:
                self.session.rollback()
                messagebox.showerror("儲存失敗", f"錯誤: {e}", parent=edit_window)
        button_frame = ttk.Frame(edit_window)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)
        save_button = ttk.Button(button_frame, text="儲存", command=save_changes)
        save_button.pack()

if __name__ == "__main__":
    # ... __main__ 保持不變 ...
    messagebox.showwarning(
        "警告",
        "您正在使用一個直接的資料庫管理工具。\n\n"
        "1. 請謹慎操作，特別是「刪除」功能，資料無法復原。\n"
        "2. 此工具只會在資料庫檔案不存在時，根據模型創建新的資料表。\n"
        "   它無法處理現有資料庫的結構變更 (如新增/刪除欄位)。如果您的模型有變更，請優先使用 Flask-Migrate (Alembic) 來進行資料庫遷移。"
    )
    if not os.path.exists(DB_PATH):
        try:
            print(f"資料庫檔案在 {DB_PATH} 未找到，正在根據模型創建...")
            Base.metadata.create_all(engine)
            print("資料庫和資料表創建完成。")
        except Exception as e:
            messagebox.showerror("資料庫創建失敗", f"無法創建資料庫檔案或資料表: {e}")
            exit()
    root = tk.Tk()
    app = DatabaseManagerApp(root)
    root.mainloop()
