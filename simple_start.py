# 간단한 앱 시작 스크립트
import os
import sys
import subprocess
import time

def kill_processes_on_port(port=8501):
    """포트를 사용하는 프로세스 종료"""
    try:
        result = subprocess.run(f'netstat -ano | findstr :{port}', shell=True, capture_output=True, text=True)
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            pids = set()
            for line in lines:
                if 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        if pid.isdigit():
                            pids.add(pid)
            
            for pid in pids:
                try:
                    subprocess.run(f'taskkill /F /PID {pid}', shell=True)
                    print(f"프로세스 {pid} 종료됨")
                except:
                    pass
    except:
        pass

def start_app():
    """앱 시작"""
    print("앱 시작 중...")
    
    # 기존 프로세스 정리
    kill_processes_on_port()
    time.sleep(2)
    
    # 앱 시작
    try:
        subprocess.run([sys.executable, '-m', 'streamlit', 'run', 'app.py', '--server.port', '8501'])
    except KeyboardInterrupt:
        print("앱 종료됨")

if __name__ == "__main__":
    start_app()




