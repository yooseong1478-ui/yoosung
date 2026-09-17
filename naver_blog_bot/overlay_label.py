#!/usr/bin/env python3
"""사진 위에 '착용 전' / '착용 후' 같은 라벨을 넣는다 (상위노출 글 패턴).
사용: python3 overlay_label.py 사진.jpg "착용 전" [출력파일]"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = ["/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", "C:/Windows/Fonts/malgunbd.ttf",
                   "/System/Library/Fonts/AppleSDGothicNeo.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]


def label(src, text, dst=None):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    size = max(40, w // 9)
    font = None
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            font = ImageFont.truetype(f, size)
            break
    font = font or ImageFont.load_default()
    d = ImageDraw.Draw(im)
    tw, th = d.textbbox((0, 0), text, font=font)[2:]
    x, y = (w - tw) // 2, (h - th) // 2
    pad = size // 3
    d.rectangle([x - pad, y - pad, x + tw + pad, y + th + pad], fill=(20, 20, 20))
    d.text((x, y), text, fill="white", font=font)
    dst = dst or str(Path(src).with_name(Path(src).stem + "_label" + Path(src).suffix))
    im.save(dst, quality=90)
    return dst


if __name__ == "__main__":
    print(label(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))
