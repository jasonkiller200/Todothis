@echo off
REM 進入專案目錄
cd /d "c:\app\Todothis_v4"
REM 激活虛擬環境
call .\venv\Scripts\activate
REM 使用 Waitress 運行 Flask 應用 (在後台運行)
start "" /B waitress-serve --listen=0.0.0.0:5001 app:app
REM 保持視窗開啟，以便查看日誌 (部署時通常移除，但測試時有用)
REM pause
