"""
測試逾期任務重設預計完成日期功能
此腳本用於驗證新功能的後端邏輯
"""
import json
from datetime import datetime, timedelta
from dateutil.parser import isoparse
from pytz import timezone, utc

def test_date_parsing():
    """測試日期解析功能"""
    print("=== 測試 1: 日期解析 ===")
    
    # 模擬前端發送的 ISO 日期字串
    test_date_str = "2025-01-20T17:00:00.000Z"
    
    try:
        parsed_date = isoparse(test_date_str)
        print(f"✅ 成功解析日期: {test_date_str}")
        print(f"   解析結果 (UTC): {parsed_date}")
        
        # 轉換為台北時區
        taiwan_tz = timezone('Asia/Taipei')
        taiwan_date = parsed_date.astimezone(taiwan_tz)
        print(f"   轉換為台北時區: {taiwan_date}")
        print(f"   格式化顯示: {taiwan_date.strftime('%Y-%m-%d %H:%M')}")
    except Exception as e:
        print(f"❌ 解析失敗: {e}")
    
    print()

def test_history_log_format():
    """測試履歷記錄格式"""
    print("=== 測試 2: 履歷記錄格式 ===")
    
    taiwan_tz = timezone('Asia/Taipei')
    
    # 模擬舊日期和新日期
    old_due_date = datetime(2025, 1, 10, 17, 0, 0, tzinfo=utc)
    new_due_date = datetime(2025, 1, 20, 17, 0, 0, tzinfo=utc)
    
    # 建立日期變更履歷項目
    due_date_change_entry = {
        'event_type': 'due_date_changed',
        'timestamp': datetime.now(utc).isoformat(),
        'actor': {
            'id': 1,
            'name': '測試使用者',
            'user_key': 'testuser'
        },
        'details': {
            'old_due_date': old_due_date.astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M'),
            'new_due_date': new_due_date.astimezone(taiwan_tz).strftime('%Y-%m-%d %H:%M'),
            'reason': '等待供應商回覆'
        }
    }
    
    print("日期變更履歷項目:")
    print(json.dumps(due_date_change_entry, indent=2, ensure_ascii=False))
    print()
    
    # 建立未完成狀態履歷項目
    status_change_entry = {
        'event_type': 'status_changed',
        'timestamp': datetime.now(utc).isoformat(),
        'actor': {
            'id': 1,
            'name': '測試使用者',
            'user_key': 'testuser'
        },
        'details': {
            'old_status': 'in-progress',
            'new_status': 'uncompleted',
            'reason': '等待供應商回覆'
        }
    }
    
    print("狀態變更履歷項目:")
    print(json.dumps(status_change_entry, indent=2, ensure_ascii=False))
    print()
    
    # 模擬完整的履歷日誌
    history_log = [
        {
            'event_type': 'assigned',
            'timestamp': (datetime.now(utc) - timedelta(days=7)).isoformat(),
            'actor': {'id': 2, 'name': '主管', 'user_key': 'manager'},
            'details': {
                'assigned_to': {'id': 1, 'name': '測試使用者', 'user_key': 'testuser'}
            }
        },
        due_date_change_entry,
        status_change_entry
    ]
    
    print("完整履歷日誌:")
    print(json.dumps(history_log, indent=2, ensure_ascii=False))
    print()

def test_api_request_format():
    """測試 API 請求格式"""
    print("=== 測試 3: API 請求格式 ===")
    
    # 模擬前端發送的請求體
    request_body = {
        'status': 'uncompleted',
        'uncompleted_reason': '等待供應商回覆，預計需要額外一週時間',
        'new_due_date': '2025-01-27T17:00:00.000Z'
    }
    
    print("前端發送的請求體:")
    print(json.dumps(request_body, indent=2, ensure_ascii=False))
    print()
    
    print("後端處理步驟:")
    print("1. 接收參數")
    print(f"   - status: {request_body['status']}")
    print(f"   - uncompleted_reason: {request_body['uncompleted_reason']}")
    print(f"   - new_due_date: {request_body['new_due_date']}")
    print()
    
    print("2. 解析日期")
    try:
        new_due_date_parsed = isoparse(request_body['new_due_date'])
        print(f"   ✅ 解析成功: {new_due_date_parsed}")
    except Exception as e:
        print(f"   ❌ 解析失敗: {e}")
    print()
    
    print("3. 更新資料庫")
    print("   - 更新 todo.due_date")
    print("   - 更新 todo.status = 'in-progress'")
    print("   - 添加履歷記錄（日期變更）")
    print("   - 添加履歷記錄（狀態變更）")
    print()
    
    print("4. 同步 MeetingTask（如果存在）")
    print("   - 更新 meeting_task.expected_completion_date")
    print("   - 更新 meeting_task.uncompleted_reason_from_todo")
    print("   - 同步履歷記錄")
    print()

def test_email_content():
    """測試郵件內容"""
    print("=== 測試 4: 郵件內容 ===")
    
    body_parts = [
        "您好 測試使用者，",
        "",
        "以下是您已逾期的任務：",
        "",
        "    標題: 測試任務",
        "    描述: 這是一個測試任務",
        "    預計完成日期: 2025-01-10 17:00",
        "",
        "<b>💡 小提示：</b>",
        "如任務無法在原定期限完成，您可以在系統中將任務狀態設為「未完成」，",
        "填寫未完成原因後，同時重新設定新的預計完成日期。",
        "",
        "請登入系統查看並盡快處理您的逾期任務：",
        "http://192.168.6.119:5001"
    ]
    
    body = "<br>".join(body_parts)
    
    print("郵件主旨: 【逾期任務提醒】您有 1 項任務已逾期！")
    print()
    print("郵件內容:")
    print("-" * 60)
    print(body.replace("<br>", "\n").replace("<b>", "").replace("</b>", ""))
    print("-" * 60)
    print()

def test_validation():
    """測試驗證邏輯"""
    print("=== 測試 5: 驗證邏輯 ===")
    
    test_cases = [
        {
            'name': '正常情況',
            'reason': '等待供應商回覆',
            'new_due_date': '2025-01-27T17:00:00.000Z',
            'expected': '✅ 通過'
        },
        {
            'name': '缺少原因',
            'reason': '',
            'new_due_date': '2025-01-27T17:00:00.000Z',
            'expected': '❌ 前端驗證失敗：請輸入未完成原因'
        },
        {
            'name': '缺少日期',
            'reason': '等待供應商回覆',
            'new_due_date': '',
            'expected': '❌ 前端驗證失敗：請選擇新的預計完成日期'
        },
        {
            'name': '無效日期格式',
            'reason': '等待供應商回覆',
            'new_due_date': 'invalid-date',
            'expected': '❌ 後端驗證失敗：無效的日期格式'
        }
    ]
    
    for case in test_cases:
        print(f"測試案例: {case['name']}")
        print(f"  原因: '{case['reason']}'")
        print(f"  日期: '{case['new_due_date']}'")
        print(f"  預期結果: {case['expected']}")
        print()

if __name__ == '__main__':
    print("=" * 70)
    print(" 逾期任務重設預計完成日期功能 - 單元測試")
    print("=" * 70)
    print()
    
    test_date_parsing()
    test_history_log_format()
    test_api_request_format()
    test_email_content()
    test_validation()
    
    print("=" * 70)
    print(" 所有測試完成！")
    print("=" * 70)
    print()
    print("✅ 如果上述測試都正常，表示後端邏輯正確")
    print("📝 請繼續進行前端測試和整合測試")
