#!/usr/bin/env python3
"""
이미지를 Base64로 인코딩하여 HTML에 직접 삽입할 수 있도록 변환
"""

import base64
import os

def create_base64_images():
    """이미지 파일들을 Base64로 인코딩"""
    
    # 이미지 파일들
    image_files = [
        "carousel_1.png", "carousel_2.png", "carousel_3.png",
        "card_1.png", "card_2.png", "card_3.png", "hero_bg.png"
    ]
    
    base64_images = {}
    
    for img_file in image_files:
        img_path = f"images/{img_file}"
        if os.path.exists(img_path):
            with open(img_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                base64_images[img_file] = f"data:image/png;base64,{encoded_string}"
                print(f"[OK] {img_file} -> Base64 인코딩 완료")
        else:
            print(f"[ERROR] {img_file} 파일이 없습니다.")
    
    return base64_images

if __name__ == "__main__":
    images = create_base64_images()
    print(f"\n[SUCCESS] 총 {len(images)}개 이미지 Base64 인코딩 완료!")


