# MAIC 프로젝트 테스트 프로세스

## 🎯 테스트 순서 (필수)

### 1단계: 로컬 PR 테스트
```bash
# 1. 코드 변경사항 확인
git status

# 2. Import 테스트
python -c "from src.ui.ops.indexing_panel import render_admin_indexing_panel; print('Import test successful')"

# 3. 문법 오류 확인
python -m py_compile src/ui/ops/indexing_panel.py
python -m py_compile src/ui/header.py

# 4. 린트 검사 (선택사항)
python -m ruff check src/ui/ops/indexing_panel.py src/ui/header.py
```

### 2단계: Playwright 앱 실행 테스트
```bash
# 1. Streamlit 앱 실행 확인
netstat -an | findstr :8501

# 2. Playwright 테스트 실행
python simple_playwright_test.py

# 3. 결과 분석 및 보고
```

## 📋 체크리스트

### ✅ 로컬 PR 테스트
- [ ] Git 상태 확인
- [ ] Import 테스트 통과
- [ ] 문법 오류 없음
- [ ] 린트 검사 통과 (선택사항)

### ✅ Playwright 테스트
- [ ] Streamlit 앱 실행 중
- [ ] Playwright 테스트 성공
- [ ] 스크린샷 저장 확인
- [ ] 결과 분석 완료

## 🚨 오류 발생 시 대응

### Import 오류
```bash
# 의존성 확인
python -c "import streamlit; print('Streamlit OK')"
python -c "import playwright; print('Playwright OK')"
```

### 문법 오류
```bash
# 파일별 문법 검사
python -m py_compile [파일명]
```

### Playwright 오류
```bash
# 브라우저 재설치
playwright install chromium
```

## 📊 테스트 결과 보고 형식

### 성공 시
```
✅ 테스트 완료
- 로컬 PR 테스트: 통과
- Playwright 테스트: 성공
- 스크린샷: [파일명].png
- 상태: 정상 작동
```

### 실패 시
```
❌ 테스트 실패
- 로컬 PR 테스트: [상태]
- Playwright 테스트: [오류 내용]
- 해결 방안: [제안사항]
```

## 🔄 자동화 스크립트

### test_local.py
```python
#!/usr/bin/env python3
"""로컬 PR 테스트 자동화"""

import subprocess
import sys

def test_imports():
    """Import 테스트"""
    try:
        from src.ui.ops.indexing_panel import render_admin_indexing_panel
        from src.ui.header import render
        print("✅ Import 테스트 통과")
        return True
    except Exception as e:
        print(f"❌ Import 테스트 실패: {e}")
        return False

def test_syntax():
    """문법 테스트"""
    files = ["src/ui/ops/indexing_panel.py", "src/ui/header.py"]
    for file in files:
        try:
            subprocess.run([sys.executable, "-m", "py_compile", file], check=True)
            print(f"✅ {file} 문법 검사 통과")
        except subprocess.CalledProcessError:
            print(f"❌ {file} 문법 오류")
            return False
    return True

if __name__ == "__main__":
    print("🧪 로컬 PR 테스트 시작")
    success = test_imports() and test_syntax()
    print("✅ 테스트 완료" if success else "❌ 테스트 실패")
```

### test_playwright.py
```python
#!/usr/bin/env python3
"""Playwright 테스트 자동화"""

import asyncio
import subprocess
from playwright.async_api import async_playwright

async def test_app():
    """앱 실행 테스트"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            await page.goto("http://localhost:8501")
            await page.wait_for_timeout(5000)
            await page.screenshot(path="test_result.png")
            print("✅ Playwright 테스트 성공")
            return True
        except Exception as e:
            print(f"❌ Playwright 테스트 실패: {e}")
            return False
        finally:
            await browser.close()

if __name__ == "__main__":
    print("🎭 Playwright 테스트 시작")
    result = asyncio.run(test_app())
    print("✅ 테스트 완료" if result else "❌ 테스트 실패")
```

## 📝 기록 규칙

1. **모든 테스트는 이 순서를 따라야 함**
2. **로컬 PR 테스트 실패 시 Playwright 테스트 중단**
3. **테스트 결과는 반드시 보고**
4. **오류 발생 시 해결 방안 제시**
5. **성공 시 다음 단계 안내**

## 🔗 관련 파일

- `TESTING_PROCESS.md`: 이 문서
- `test_local.py`: 로컬 테스트 자동화
- `test_playwright.py`: Playwright 테스트 자동화
- `simple_playwright_test.py`: 기본 Playwright 테스트
