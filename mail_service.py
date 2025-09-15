import requests
import json
import logging
from config import MAIL_API_URL

# 配置日誌記錄
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_mail(subject, body, mail_to, mail_cc="", IsBodyHtml="H"):
    """
    發送郵件到指定的 API 服務。

    Args:
        subject (str): 信件主旨，最多40個文字。
        body (str): 信件內文，最多1000個文字。
        mail_to (str): 收件人，可設多個，用「;」分隔，最多150個文字。
        mail_cc (str, optional): 副本，可設多個，用「;」分隔，最多150個文字。預設為空字串。
        is_html (bool, optional): 內文是否為 HTML 格式。預設為 False。

    Returns:
        tuple: (bool, str) 表示發送是否成功以及訊息。
    """
    api_url = MAIL_API_URL
    headers = {'Content-Type': 'application/json'}

    # 確保主旨和內文不超過最大長度
    subject = subject[:40]
    # HTML 格式的郵件可能較長，這裡暫時移除內文長度限制，由 API 端處理
    # body = body[:1000]
    mail_to = mail_to[:300]
    mail_cc = mail_cc[:150]

    payload = {
        "Subject": subject,
        "Body": body,
        "MailTo": mail_to,
        "MailCC": mail_cc,
        "IsBodyHtml": "H"  # 可以把內容轉成HTML格式
    }

    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # 如果響應狀態碼是 4xx 或 5xx，則拋出 HTTPError

        try:
            response_json = response.json()
            if response_json.get("isSuccess") == True:
                logging.info(f"Email sent successfully to {mail_to}. Response: {response_json}")
                return True, "郵件發送成功"
            else:
                error_message = response_json.get("Message", "未知錯誤")
                logging.error(f"Failed to send email to {mail_to}. API response: {response_json}. Full response text: {response.text}")
                return False, f"郵件發送失敗: {error_message}"
        except json.JSONDecodeError:
            logging.error(f"Failed to decode JSON response from API. Full response text: {response.text}")
            return False, f"郵件服務 API 返回無效響應或非 JSON 格式。完整響應: {response.text}"

    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err} - Response: {http_err.response.text if http_err.response else 'N/A'}. Full request payload: {json.dumps(payload)}")
        return False, f"HTTP 錯誤: {http_err}"
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"Connection error occurred: {conn_err}. Full request payload: {json.dumps(payload)}")
        return False, f"連線錯誤: 無法連接到郵件服務 API"
    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"Timeout error occurred: {timeout_err}. Full request payload: {json.dumps(payload)}")
        return False, f"逾時錯誤: 郵件服務 API 無響應"
    except requests.exceptions.RequestException as req_err:
        logging.error(f"An error occurred during the request: {req_err}. Full request payload: {json.dumps(payload)}")
        return False, f"請求錯誤: {req_err}"
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}. Full request payload: {json.dumps(payload)}")
        return False, f"發生未知錯誤: {e}"

if __name__ == '__main__':
    # 測試範例
    print("--- 測試成功發送 ---")
    success, msg = send_mail(
        subject="發送mail測試",
        body="<h3>組件課 - 本週工作報告 (2025-09-08 to 2025-09-14)</h3> ",
        mail_to="ralf@hartford.com.tw" # 請替換為實際可用的收件人郵箱
    )
    print(f"Success: {success}, Message: {msg}\n")

   # print("--- 測試多個收件人 ---")
   # success, msg = send_mail(
    #    subject="Multiple Recipients Test",
   #     body="This email is sent to multiple recipients.",
   #     mail_to="ralf@hartford.com.tw", # 請替換為實際可用的收件人郵箱
  #      mail_cc="jimmywu@hartford.com.tw" # 請替換為實際可用的副本郵箱
  #  )
   # print(f"Success: {success}, Message: {msg}\n")
