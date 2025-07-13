@echo off
echo 正在安裝 Python 套件...
echo.

REM 檢查 Python 是否安裝
python --version >nul 2>&1
if errorlevel 1 (
    echo 錯誤: 找不到 Python，請先安裝 Python
    echo 請從 https://www.python.org/downloads/ 下載並安裝 Python
    pause
    exit /b 1
)

echo Python 版本:
python --version
echo.

REM 升級 pip
echo 升級 pip...
python -m pip install --upgrade pip
echo.

REM 安裝套件
echo 安裝 Flask 相關套件...
pip install Flask==2.3.3
echo.

echo 安裝 Flask-SQLAlchemy...
pip install Flask-SQLAlchemy==3.0.5
echo.

echo 安裝 Werkzeug...
pip install Werkzeug==2.3.7
echo.

REM 或者使用 requirements.txt 一次安裝所有套件
echo 使用 requirements.txt 安裝所有套件...
pip install -r requirements.txt
echo.

echo ✅ 所有套件安裝完成！
echo.
echo 現在您可以執行以下指令啟動應用程序：
echo python app.py
echo.
pause