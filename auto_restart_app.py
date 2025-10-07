# 자동 재시작 앱 시스템
"""
앱이 멈추는 문제를 해결하는 자동 재시작 시스템
- 포트 충돌 자동 해결
- 프로세스 정리
- 자동 재시작
- 오류 감지 및 복구
"""

import os
import sys
import time
import subprocess
import signal
import psutil
from pathlib import Path


class AutoRestartApp:
    """자동 재시작 앱 클래스"""
    
    def __init__(self, port=8501):
        self.port = port
        self.app_file = "app.py"
        self.max_retries = 5
        self.retry_delay = 3
        
    def kill_processes_on_port(self):
        """포트를 사용하는 프로세스 종료"""
        try:
            # netstat으로 포트 사용 프로세스 찾기
            result = subprocess.run(
                f'netstat -ano | findstr :{self.port}',
                shell=True, capture_output=True, text=True
            )
            
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
                
                # 프로세스 종료
                for pid in pids:
                    try:
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True)
                        print(f"프로세스 {pid} 종료됨")
                    except Exception as e:
                        print(f"프로세스 {pid} 종료 실패: {e}")
                        
        except Exception as e:
            print(f"포트 정리 실패: {e}")
    
    def kill_python_processes(self):
        """모든 Python 프로세스 종료"""
        try:
            subprocess.run('taskkill /F /IM python.exe', shell=True)
            print("모든 Python 프로세스 종료됨")
        except Exception as e:
            print(f"Python 프로세스 종료 실패: {e}")
    
    def check_app_syntax(self):
        """앱 구문 검사"""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'py_compile', self.app_file],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print("✅ 구문 검사 통과")
                return True
            else:
                print(f"❌ 구문 오류: {result.stderr}")
                return False
        except Exception as e:
            print(f"구문 검사 실패: {e}")
            return False
    
    def start_app(self):
        """앱 시작"""
        try:
            print(f"🚀 앱 시작 중... (포트: {self.port})")
            process = subprocess.Popen(
                [sys.executable, '-m', 'streamlit', 'run', self.app_file, '--server.port', str(self.port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return process
        except Exception as e:
            print(f"앱 시작 실패: {e}")
            return None
    
    def check_app_health(self):
        """앱 상태 확인"""
        try:
            result = subprocess.run(
                f'netstat -ano | findstr :{self.port}',
                shell=True, capture_output=True, text=True
            )
            return 'LISTENING' in result.stdout
        except Exception as e:
            print(f"앱 상태 확인 실패: {e}")
            return False
    
    def wait_for_app_ready(self, timeout=30):
        """앱 준비 완료 대기"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.check_app_health():
                print(f"✅ 앱이 준비되었습니다! http://localhost:{self.port}")
                return True
            time.sleep(1)
        return False
    
    def restart_app(self):
        """앱 재시작"""
        print("🔄 앱 재시작 중...")
        
        # 1. 기존 프로세스 정리
        self.kill_processes_on_port()
        self.kill_python_processes()
        
        # 2. 잠시 대기
        time.sleep(2)
        
        # 3. 구문 검사
        if not self.check_app_syntax():
            print("❌ 구문 오류로 인해 앱을 시작할 수 없습니다.")
            return False
        
        # 4. 앱 시작
        process = self.start_app()
        if not process:
            return False
        
        # 5. 앱 준비 대기
        if self.wait_for_app_ready():
            return True
        else:
            print("❌ 앱이 준비되지 않았습니다.")
            return False
    
    def run_with_auto_restart(self):
        """자동 재시작으로 앱 실행"""
        retry_count = 0
        
        while retry_count < self.max_retries:
            print(f"\n{'='*50}")
            print(f"시도 {retry_count + 1}/{self.max_retries}")
            print(f"{'='*50}")
            
            if self.restart_app():
                print("🎉 앱이 성공적으로 시작되었습니다!")
                print(f"🌐 브라우저에서 http://localhost:{self.port} 를 열어보세요.")
                print("\n앱을 종료하려면 Ctrl+C를 누르세요.")
                
                try:
                    # 앱이 실행 중인 동안 대기
                    while True:
                        if not self.check_app_health():
                            print("⚠️ 앱이 중단되었습니다. 재시작합니다...")
                            break
                        time.sleep(5)
                except KeyboardInterrupt:
                    print("\n👋 앱을 종료합니다.")
                    self.kill_processes_on_port()
                    break
            else:
                retry_count += 1
                if retry_count < self.max_retries:
                    print(f"⏳ {self.retry_delay}초 후 재시도합니다...")
                    time.sleep(self.retry_delay)
                else:
                    print("❌ 최대 재시도 횟수를 초과했습니다.")
                    break


def main():
    """메인 함수"""
    print("MAIC 앱 자동 재시작 시스템")
    print("=" * 50)
    
    app = AutoRestartApp(port=8501)
    app.run_with_auto_restart()


if __name__ == "__main__":
    main()
