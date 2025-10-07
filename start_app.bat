@echo off
echo 🚀 MAIC 앱 자동 시작 시스템
echo ================================

REM Python이 설치되어 있는지 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python이 설치되어 있지 않습니다.
    pause
    exit /b 1
)

REM 필요한 패키지 설치 확인
echo 📦 필요한 패키지 확인 중...
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo 📥 Streamlit 설치 중...
    pip install streamlit
)

python -c "import psutil" >nul 2>&1
if errorlevel 1 (
    echo 📥 psutil 설치 중...
    pip install psutil
)

REM 앱 실행
echo 🎯 앱 시작 중...
python auto_restart_app.py

pause


