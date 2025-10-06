#!/usr/bin/env python3
"""SRM 테스트 결과 검증"""

from src.runtime.sequential_release import create_sequential_manager
import os

def test_srm():
    """SRM 테스트 결과 검증"""
    print("[INFO] SRM 테스트 결과 검증 시작")
    
    # GitHub 토큰 확인
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("[ERROR] GITHUB_TOKEN이 설정되지 않았습니다.")
        return False
    
    try:
        # 매니저 생성 및 테스트
        manager = create_sequential_manager('LEES1605', 'MAIC', token)
        print("[OK] 매니저 생성 성공")
        
        # 최신 릴리스 찾기
        latest = manager.find_latest_by_number('index')
        if latest:
            print(f"[OK] 최신 릴리스 발견: {latest.get('tag_name')}")
            print(f"   릴리스 ID: {latest.get('id')}")
            print(f"   에셋 수: {len(latest.get('assets', []))}")
            
            # 에셋 정보
            assets = latest.get('assets', [])
            if assets:
                asset = assets[0]
                print(f"   에셋명: {asset.get('name')}")
                print(f"   크기: {asset.get('size')} bytes")
                print(f"   다운로드 횟수: {asset.get('download_count')}")
                print(f"   다운로드 URL: {asset.get('browser_download_url')}")
            
            # 릴리스 메타데이터
            print(f"   생성일: {latest.get('created_at')}")
            print(f"   발행일: {latest.get('published_at')}")
            print(f"   릴리스명: {latest.get('name')}")
            
            return True
        else:
            print("[ERROR] 최신 릴리스를 찾을 수 없습니다.")
            return False
            
    except Exception as e:
        print(f"[ERROR] 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    success = test_srm()
    print("[OK] 테스트 완료" if success else "[ERROR] 테스트 실패")
