"""
BS Textile — PWA иконки генератор
Запусти этот файл ОДИН РАЗ в папке проекта:
    python setup_pwa.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

os.makedirs('static', exist_ok=True)

def make_icon(size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    r = int(size * 0.22)
    draw.rounded_rectangle([0, 0, size-1, size-1], radius=r, fill=(30, 74, 84, 255))
    pad = int(size * 0.08)
    draw.ellipse([pad, pad, size-pad, size-pad], fill=(42, 100, 110, 180))

    font_size = int(size * 0.38)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()

    text = "bs"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1] - int(size * 0.02)
    draw.text((x+2, y+2), text, font=font, fill=(0, 0, 0, 60))
    draw.text((x, y), text, font=font, fill=(232, 224, 213, 255))
    return img

print("Генерация иконок...")
for size in [192, 512]:
    make_icon(size).save(f'static/icon-{size}.png', 'PNG')
    print(f"  ✓ static/icon-{size}.png")

make_icon(180).save('static/apple-touch-icon.png', 'PNG')
print("  ✓ static/apple-touch-icon.png")

print("\nГотово! Перезапусти сервер: python app.py")
