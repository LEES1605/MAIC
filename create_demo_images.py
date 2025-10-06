#!/usr/bin/env python3
"""
데모용 이미지 생성 스크립트
로컬 이미지 파일들을 생성하여 외부 의존성 제거
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_demo_images():
    """데모용 이미지 파일들 생성"""
    
    # 이미지 디렉토리 생성
    os.makedirs("images", exist_ok=True)
    
    # 1. 캐러셀용 이미지들
    colors = [
        ("#5e6ad2", "Slide 1"),
        ("#7170ff", "Slide 2"), 
        ("#828fff", "Slide 3")
    ]
    
    for i, (color, text) in enumerate(colors, 1):
        # 400x200 이미지 생성
        img = Image.new('RGB', (400, 200), color)
        draw = ImageDraw.Draw(img)
        
        # 텍스트 추가
        try:
            # 기본 폰트 사용
            font = ImageFont.load_default()
        except:
            font = None
            
        # 텍스트 중앙에 그리기
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (400 - text_width) // 2
        y = (200 - text_height) // 2
        
        draw.text((x, y), text, fill='white', font=font)
        
        # 파일 저장
        img.save(f"images/carousel_{i}.png")
        print(f"[OK] 캐러셀 이미지 {i} 생성: images/carousel_{i}.png")
    
    # 2. 카드용 이미지들
    card_colors = [
        ("#5e6ad2", "Image 1"),
        ("#7170ff", "Image 2"),
        ("#828fff", "Image 3")
    ]
    
    for i, (color, text) in enumerate(card_colors, 1):
        # 300x200 이미지 생성
        img = Image.new('RGB', (300, 200), color)
        draw = ImageDraw.Draw(img)
        
        # 텍스트 추가
        try:
            font = ImageFont.load_default()
        except:
            font = None
            
        # 텍스트 중앙에 그리기
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (300 - text_width) // 2
        y = (200 - text_height) // 2
        
        draw.text((x, y), text, fill='white', font=font)
        
        # 파일 저장
        img.save(f"images/card_{i}.png")
        print(f"[OK] 카드 이미지 {i} 생성: images/card_{i}.png")
    
    # 3. 히어로 배경 이미지
    hero_img = Image.new('RGB', (1200, 400), "#1a1a1a")
    draw = ImageDraw.Draw(hero_img)
    
    # 그라데이션 효과 (간단한 패턴)
    for y in range(400):
        alpha = y / 400
        color_value = int(26 + (94 - 26) * alpha)  # 26에서 94로
        color = (color_value, color_value, color_value)
        draw.line([(0, y), (1200, y)], fill=color)
    
    # 텍스트 추가
    try:
        font = ImageFont.load_default()
    except:
        font = None
        
    draw.text((50, 150), "Linear Components", fill='white', font=font)
    draw.text((50, 180), "Modern UI Library", fill='#b0b0b0', font=font)
    
    hero_img.save("images/hero_bg.png")
    print("[OK] 히어로 배경 이미지 생성: images/hero_bg.png")
    
    print("\n[SUCCESS] 모든 데모 이미지 생성 완료!")
    print("[INFO] 생성된 파일들:")
    for file in os.listdir("images"):
        print(f"   - images/{file}")

if __name__ == "__main__":
    create_demo_images()
