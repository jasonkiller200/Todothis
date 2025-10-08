document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded event fired.');
    let selectedUserKey = null;
    let selectedUserKeys = []; // 保持單選時的邏輯，但現在只會有一個元素
    let assignableUsers = [];

    // --- Utility Functions ---
    function escapeHTML(str) {
        if (str === null || str === undefined) return '';
        return str.toString()
            .replace(/&/g, '&')
            .replace(/</g, '<')
            .replace(/>/g, '>')
            .replace(/"/g, '"')
            .replace(/'/g, '&#039;');
    }

    function getStatusText(status) {
        const statusMap = {
            'pending': '待開始',
            'in-progress': '進行中',
            'completed': '已完成',
            'uncompleted': '未完成'
        };
        return statusMap[status] || status;
    }

    // --- API Fetching Functions ---
    function fetchUserDetail(userKey) {
        console.log(`Fetching user detail for: ${userKey}`);
        fetch(`/api/user/${userKey}`)
            .then(response => response.json())
            .then(data => {
                console.log('Received user detail data:', data);
                if (data.error) throw new Error(data.error);
                renderUserDetail(data);
                assignableUsers = data.permissions.assignable_users || [];
                updateAssignToDropdown(data.permissions.can_assign);
            })
            .catch(err => {
                console.error('Error fetching user detail:', err);
                let msg = (err.message === 'Access denied') ? '您沒有權限觀看此使用者的待辦事項。' : `無法載入資料: ${err.message}`;
                document.getElementById('user-content').innerHTML = `<div class="no-user-selected">${msg}</div>`;
                document.getElementById('add-todo-form-container').style.display = 'none';
            });
    }

    function updateDeptStats() {
        fetch('/api/dept-stats')
            .then(response => response.json())
            .then(data => {
                const statsContainer = document.getElementById('dept-stats');
                statsContainer.innerHTML = ''; // Clear existing stats
                for (const deptName in data) {
                    const stats = data[deptName];
                    const card = `
                        <div class="dept-card">
                            <div class="dept-name">${escapeHTML(deptName)}</div>
                            <div class="dept-stats-items">
                                <div class="stat-item">
                                    <div class="stat-number">${stats.total}</div>
                                    <div class="stat-label">總任務</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-number">${stats.completed}</div>
                                    <div class="stat-label">已完成</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-number">${stats.completion_rate}%</div>
                                    <div class="stat-label">完成率</div>
                                </div>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${stats.completion_rate}%;"></div>
                            </div>
                        </div>
                    `;
                    statsContainer.innerHTML += card;
                }
            })
            .catch(error => {
                console.error('Error fetching department stats:', error);
                const statsContainer = document.getElementById('dept-stats');
                statsContainer.innerHTML = '<p>無法載入部門統計資料。</p>';
            });
    }

    // --- Rendering Functions ---
    function renderUserDetail(data) {
        console.log('Rendering user detail with data:', data);
        const userContent = document.getElementById('user-content');
        const canModify = data.permissions.can_modify;

        const renderTodos = (todos, overdueCount) => {
            let overdueHtml = '';
            if (overdueCount > 0) {
                overdueHtml = `<div class="overdue-task-stats" style="margin-bottom: 15px; font-size: 1.1em;">逾期任務: ${overdueCount}</div>`;
            }

            if (!todos || todos.length === 0) {
                return overdueHtml + '<p>暫無事項</p>';
            }

            // 新增輔助函式：根據 due_date 和 status 判斷警示顏色
            function getTodoAlertClass(todo) {
                if (todo.status === 'completed') {
                    return ''; // 已完成的任務不顯示警示顏色
                }

                const dueDate = new Date(todo.due_date);
                const today = new Date();
                
                // 為了只比較日期，將時間部分設為一天的開始
                const dueDateOnly = new Date(dueDate.getFullYear(), dueDate.getMonth(), dueDate.getDate());
                const todayOnly = new Date(today.getFullYear(), today.getMonth(), today.getDate());

                const diffTime = dueDateOnly.getTime() - todayOnly.getTime();
                const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

                if (diffDays < 0) {
                    return 'todo-alert-red'; // 過期未完成
                } else if (diffDays <= 2) {
                    return 'todo-alert-yellow'; // 兩天內到期 (今天、明天、後天)
                } else {
                    return 'todo-alert-green'; // 正常
                }
            }

            return overdueHtml + todos.map(todo => `
                <div class="todo-item ${getTodoAlertClass(todo)}">
                    <h5>${escapeHTML(todo.title)}</h5>
                    <p>${escapeHTML(todo.description)}</p>
                    <p class="due-date">預計完成: ${new Date(todo.due_date).toLocaleDateString('zh-TW')}</p>
                    ${(() => {
                        let displayAssignedInfo = '';
                        if (todo.assigned_by) {
                            if (todo.assignee_user_key === todo.assigner_user_key) {
                                displayAssignedInfo = `自己指派`;
                            } else {
                                displayAssignedInfo = `由 ${escapeHTML(todo.assigned_by.name)} 指派給 ${escapeHTML(data.user.name)}`;
                            }
                        }
                        return displayAssignedInfo ? `<div class="assigned-by-info">${displayAssignedInfo}</div>` : '';
                    })()} 
                    ${todo.can_edit_status ? 
                        `<select id="status-select-${todo.id}" class="status-select" data-todo-id="${todo.id}">
                            <option value="pending" ${todo.status === 'pending' ? 'selected' : ''}>待開始</option>
                            <option value="in-progress" ${todo.status === 'in-progress' ? 'selected' : ''}>進行中</option>
                            <option value="completed" ${todo.status === 'completed' ? 'selected' : ''}>已完成</option>
                            <option value="uncompleted">未完成</option>
                        </select>
                        <div id="uncompleted-reason-container-${todo.id}" style="display:none; margin-top: 5px;">
                            <label for="uncompleted-reason-${todo.id}" style="display:block; margin-bottom:4px; font-weight:600;">未完成原因：</label>
                            <textarea id="uncompleted-reason-${todo.id}" class="uncompleted-reason-input" placeholder="請輸入未完成原因"></textarea>
                            <label for="new-due-date-${todo.id}" style="display:block; margin-top:8px; margin-bottom:4px; font-weight:600;">新的預計完成日期：</label>
                            <input type="date" id="new-due-date-${todo.id}" class="new-due-date-input" />
                            <button type="button" class="btn confirm-uncompleted-btn" data-todo-id="${todo.id}">確認</button>
                        </div>` : 
                        `<span class="status-badge status-${todo.status}">${getStatusText(todo.status)}</span>`
                    }
                    ${todo.history_log && todo.history_log.length > 0 ? 
                        `<div class="todo-history">
                            <h6>任務履歷:</h6>
                            ${todo.history_log.map(entry => {
                                let eventText = '';
                                // 嘗試將時間戳記解析為 UTC 時間，然後再轉換為台北時間
                                const date = new Date(entry.timestamp);
                                const timestamp = date.toLocaleString('zh-TW', { year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', hour12: false, timeZone: 'Asia/Taipei' });
                                
                                const getActorName = (actor) => (actor && actor.name) ? escapeHTML(actor.name) : '系統';
                                const actorName = (entry.actor && entry.actor.name) ? `由 ${escapeHTML(entry.actor.name)}` : '';

                                if (entry.event_type === 'assigned') {
                                    const assignedToName = (entry.details.assigned_to && entry.details.assigned_to.name) ? escapeHTML(entry.details.assigned_to.name) : '未知人員';
                                    if (entry.actor && entry.details.assigned_to && entry.actor.user_key === entry.details.assigned_to.user_key) {
                                        eventText = `自己指派`;
                                    } else if (entry.actor && entry.actor.name) {
                                        eventText = `由 ${escapeHTML(entry.actor.name)} 指派給 ${assignedToName}`; 
                                    } else {
                                        eventText = `指派給 ${assignedToName}`;
                                    }
                                } else if (entry.event_type === 'status_changed') {
                                    const actorDisplayName = `由 ${getActorName(entry.actor)}`;
                                    eventText = `${actorDisplayName} 狀態從 ${getStatusText(entry.details.old_status)} 變更為 ${getStatusText(entry.details.new_status)}`;
                                    if (entry.details.reason) {
                                        eventText += ` (原因: ${escapeHTML(entry.details.reason)})`;
                                    }
                                } else if (entry.event_type === 'due_date_changed') {
                                    const actorDisplayName = `由 ${getActorName(entry.actor)}`;
                                    eventText = `${actorDisplayName} 預計完成日期從 ${escapeHTML(entry.details.old_due_date)} 變更為 ${escapeHTML(entry.details.new_due_date)}`;
                                    if (entry.details.reason) {
                                        eventText += ` (原因: ${escapeHTML(entry.details.reason)})`;
                                    }
                                } else if (entry.event_type === 'assigned_from_meeting') {
                                    const assignedToName = (entry.details.assigned_to && entry.details.assigned_to.name) ? escapeHTML(entry.details.assigned_to.name) : '未知人員';
                                    const assignedByName = (entry.details.assigned_by && entry.details.assigned_by.name) ? escapeHTML(entry.details.assigned_by.name) : '未知人員';
                                    eventText = `由 ${assignedByName} 指派給 ${assignedToName}`;
                                } else if (entry.event_type === 'auto_transfer') {
                                    eventText = `系統自動從下週計畫轉移`;
                                } else if (entry.event_type === 'archived') {
                                    eventText = `系統自動歸檔`;
                                }
                                return `<div class="history-item">${eventText} (${timestamp})</div>`;
                            }).join('')}
                        </div>` : ''}
                </div>`).join('');
        };

        const overdueCount = data.todos.current.filter(todo => {
            if (todo.status === 'completed') return false;
            const dueDate = new Date(todo.due_date);
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            return dueDate < today;
        }).length;

        userContent.innerHTML = `
            <div class="todo-sections">
                <div class="section"><h4>📋 本週任務</h4>${renderTodos(data.todos.current, overdueCount)}</div>
                <div class="section"><h4>📅 未來任務</h4>${renderTodos(data.todos.next, 0)}</div>
            </div>`;
        
        document.getElementById('add-todo-form-container').style.display = canModify || data.permissions.can_assign ? 'block' : 'none';
    }

    function updateAssignToDropdown(canAssign) {
        const assignToGroup = document.getElementById('assign-to-group');
        const assignToSelect = document.getElementById('assign-to');
        const noAssignableUsersMessage = document.getElementById('no-assignable-users-message');
        assignToSelect.innerHTML = '';

        if (canAssign && assignableUsers.length > 0) {
            assignToGroup.style.display = 'block';
            noAssignableUsersMessage.style.display = 'none';
            
            const currentUserKey = document.body.dataset.currentUserKey;
            const currentUserName = document.body.dataset.currentUserName;

            // Add current user to the top of the list
            assignToSelect.innerHTML += `<option value="${currentUserKey}">自己 (${escapeHTML(currentUserName)})</option>`;

            // Add other assignable users
            assignableUsers.forEach(user => {
                if (user.user_key !== currentUserKey) { 
                    assignToSelect.innerHTML += `<option value="${user.user_key}">${escapeHTML(user.name)} (${escapeHTML(user.role)})</option>`;
                }
            });
            
            // Set the default selection
            assignToSelect.value = selectedUserKey;

        } else {
            assignToGroup.style.display = 'none';
            noAssignableUsersMessage.style.display = 'block';
        }
    }

    // --- Event Listener Setup ---
    function setupUserCardClickListeners() {
        const userCards = document.querySelectorAll('.user-card');
        userCards.forEach(card => {
            card.addEventListener('click', function(event) {
                const userKey = this.dataset.userKey;

                // 單選模式
                userCards.forEach(c => c.classList.remove('active'));
                this.classList.add('active');
                selectedUserKeys = [userKey]; // 清空並只選中當前
                selectedUserKey = userKey; // 更新單選時的 selectedUserKey
                fetchUserDetail(selectedUserKey); // 獲取單個用戶詳情
                updateAssignToDropdown(true); // 每次選擇後更新下拉選單
            });
        });
    }

    function setupTodoFormSubmitListener() {
        document.getElementById('todoForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            // 從多選下拉選單中獲取所有選定的 user_key
            const assignToSelect = document.getElementById('assign-to');
            const selectedOptions = Array.from(assignToSelect.selectedOptions);
            const targetUserKeysForTodo = selectedOptions.map(option => option.value);

            if (targetUserKeysForTodo.length === 0) { 
                alert('請選擇至少一個指派對象'); 
                return; 
            }

            const todoType = document.getElementById('todo-type').value;
            const dueDateInput = document.getElementById('due-date').value;
            const selectedDate = new Date(dueDateInput);
            const today = new Date();
            const firstDayOfWeek = new Date(today.setDate(today.getDate() - today.getDay() + (today.getDay() === 0 ? -6 : 1))); // 獲取本週的星期一
            const lastDayOfWeek = new Date(firstDayOfWeek);
            lastDayOfWeek.setDate(firstDayOfWeek.getDate() + 6); // 獲取本週的星期日

            // 將時間部分歸零，只比較日期
            selectedDate.setHours(0, 0, 0, 0);
            firstDayOfWeek.setHours(0, 0, 0, 0);
            lastDayOfWeek.setHours(0, 0, 0, 0);

            // 重新獲取今天的日期並歸零，因為上面的 today 物件已經被修改
            const todayOnly = new Date();
            todayOnly.setHours(0, 0, 0, 0);

            if (selectedDate < todayOnly) {
                alert('預計完成日期不能早於今天。');
                return; // 阻止表單提交
            }

            // --- 擴展的驗證邏輯 ---
            if (todoType === 'current') {
                if (selectedDate < firstDayOfWeek || selectedDate > lastDayOfWeek) {
                    alert('當任務類型為「本週任務」時，預計完成日期必須在本週範圍內。請指派人員選擇適當的日期。');
                    return; // 阻止表單提交
                }
            } else if (todoType === 'next') { // 未來任務的驗證
                if (selectedDate >= firstDayOfWeek && selectedDate <= lastDayOfWeek) {
                    alert('當任務類型為「未來任務」時，預計完成日期不能在本週範圍內。請指派人員選擇適當的日期。');
                    return; // 阻止表單提交
                }
            }

            // 新增：檢查是否為工作日 (週一到週五)
            const dayOfWeek = selectedDate.getDay(); // 0 = 星期日, 1 = 星期一, ..., 6 = 星期六
            if (dayOfWeek === 0 || dayOfWeek === 6) { // 如果是星期日或星期六
                alert('預計完成日期必須是工作日 (週一至週五)。請指派人員選擇適當的日期。');
                return; // 阻止表單提交
            }
            // --- 驗證邏輯結束 ---

            const todoData = {
                user_keys: targetUserKeysForTodo, // 將單一 user_key 改為 user_keys 陣列
                type: todoType,
                title: document.getElementById('todo-title').value,
                description: document.getElementById('todo-description').value,
                due_date: dueDateInput
            };

            fetch('/api/batch_add_todo', { // 修改 API 端點
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(todoData)
            })
            .then(response => response.json())
            .then(result => {
                if (result.error) { alert('錯誤: ' + result.error); }
                else { 
                    alert(result.message);
                    this.reset();
                    // 刷新當前選中的用戶詳情，如果有多選，則可能需要重新載入整個組織圖或顯示一個通用訊息
                    if (selectedUserKeys.length === 1) {
                        fetchUserDetail(selectedUserKeys[0]); 
                    } else {
                        // 如果有多個用戶被選中，可能需要刷新整個組織圖或顯示一個通用訊息
                        // 這裡簡單地刷新部門統計，並清空用戶詳情區域
                        document.getElementById('user-content').innerHTML = '<div class="no-user-selected">請點擊上方組織圖中的人員以查看詳細資訊</div>';
                        document.getElementById('add-todo-form-container').style.display = 'none';
                    }
                    updateDeptStats(); 
                }
            });
        });
    }

    function setupDynamicEventListeners() {
        // 設置日期驗證功能 - 只允許選擇週一到週五
        function setupDateInputValidation(dateInput) {
            if (!dateInput) return;
            
            dateInput.addEventListener('change', function() {
                const selectedDate = new Date(this.value + 'T00:00:00');
                const dayOfWeek = selectedDate.getDay();
                
                if (dayOfWeek === 0 || dayOfWeek === 6) { // 0 = Sunday, 6 = Saturday
                    alert('預計完成日期不能是週末，請選擇週一至週五。');
                    this.value = '';
                }
            });
        }
        
        document.body.addEventListener('change', function(e) {
            if (e.target && e.target.classList.contains('status-select')) {
                const todoId = e.target.dataset.todoId;
                const newStatus = e.target.value;
                const reasonContainer = document.getElementById(`uncompleted-reason-container-${todoId}`);

                if (newStatus === 'uncompleted') {
                    reasonContainer.style.display = 'block';
                    // 為新顯示的日期輸入框添加驗證
                    const dateInput = document.getElementById(`new-due-date-${todoId}`);
                    setupDateInputValidation(dateInput);
                } else {
                    reasonContainer.style.display = 'none';
                    updateTodoStatus(todoId, newStatus);
                }
            }
            
            // 為新的日期輸入框添加驗證（當它們被動態創建時）
            if (e.target && e.target.classList.contains('new-due-date-input')) {
                setupDateInputValidation(e.target);
            }
        });

        document.body.addEventListener('click', function(e) {
            if (e.target && e.target.classList.contains('confirm-uncompleted-btn')) {
                const todoId = e.target.dataset.todoId;
                const reasonInput = document.getElementById(`uncompleted-reason-${todoId}`);
                const reason = reasonInput.value.trim();
                
                // 新增：獲取新的預計完成日期（僅日期，不含時間）
                const newDueDateInput = document.getElementById(`new-due-date-${todoId}`);
                const newDueDate = newDueDateInput.value; // 格式為 YYYY-MM-DD
                
                if (!reason) {
                    alert('請輸入未完成原因');
                    return;
                }
                
                // 新增：驗證日期必填
                if (!newDueDate) {
                    alert('請選擇新的預計完成日期');
                    return;
                }
                
                updateTodoStatus(todoId, 'uncompleted', reason, newDueDate);
            }
        });
    }
    
    function updateTodoStatus(todoId, status, reason = null, newDueDate = null) {
        const body = { status: status };
        if (reason) {
            body.uncompleted_reason = reason;
        }
        // 新增：添加新的預計完成日期
        if (newDueDate) {
            // 將日期格式 YYYY-MM-DD 轉換為完整的日期時間（設定為當天 00:00，與指派任務時一致）
            const dateObj = new Date(newDueDate + 'T00:00:00');
            body.new_due_date = dateObj.toISOString();
        }

        fetch(`/api/todo/${todoId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
        .then(response => response.json())
        .then(result => {
            if (result.error) {
                alert('更新失敗: ' + result.error);
            } else {
                alert(result.message);
            }
            fetchUserDetail(selectedUserKey); // Refresh view
            updateDeptStats(); // Refresh stats
        })
        .catch(err => {
            console.error('Update status error:', err);
            alert('更新時發生網路錯誤');
        });
    }


    // --- Initial Page Load ---
    setupUserCardClickListeners();
    setupTodoFormSubmitListener();
    setupDynamicEventListeners();
    updateDeptStats();
    
    const currentUserKey = document.body.dataset.currentUserKey;
    if (currentUserKey) {
        const currentUserCard = document.querySelector(`.user-card[data-user-key="${currentUserKey}"]`);
        if (currentUserCard) {
            currentUserCard.classList.add('active');
        }
        selectedUserKey = currentUserKey;
        fetchUserDetail(currentUserKey);
    }
});
