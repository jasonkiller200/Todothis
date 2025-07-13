@echo off
echo 🐍 設置 Python 虛擬環境...
echo.

REM 檢查 Python 是否安裝
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 錯誤: 找不到 Python
    echo 請先安裝 Python: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python 已安裝
python --version
echo.

REM 創建虛擬環境
echo 📁 創建虛擬環境 'venv'...
if exist "venv" (
    echo ⚠️ 虛擬環境已存在，跳過創建
) else (
    python -m venv venv
    if errorlevel 1 (
        echo ❌ 虛擬環境創建失敗
        pause
        exit /b 1
    )
    echo ✅ 虛擬環境創建成功
)
echo.

REM 啟動虛擬環境
echo 🔄 啟動虛擬環境...
call venv\Scripts\activate.bat
echo ✅ 虛擬環境已啟動
echo.

REM 升級 pip
echo 📦 升級 pip...
python -m pip install --upgrade pip
echo.

REM 安裝套件
echo 🔧 安裝所需套件...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ 套件安裝失敗
    pause
    exit /b 1
)
echo ✅ 套件安裝完成
echo.

echo 🚀 啟動應用程序...
echo 應用程序將在 http://localhost:5000 運行
echo 按 Ctrl+C 停止服務器
echo.

REM 啟動應用程序
python app.py