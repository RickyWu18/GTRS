"""條帶拼版：把多頁的同一橫帶（頁尾頁碼／頁首標題）裁下疊成一張圖。

用途（W0.3／W0.4／W0.5）
    來源 PDF 無文字層，印刷頁碼與頁首 subsystem 名稱只能靠目視取得。逐頁開圖
    成本過高，故將每頁只有數百像素高的關鍵橫帶裁出、依序疊成一張拼版圖，
    一次可判讀十餘頁。每列左側印上 pdf_page，使判讀結果不會錯位。

用法
    python tools/strip_sheet.py --pages 1-16 --band footer --out work/sheet_001.png
    python tools/strip_sheet.py --pages 60-75 --band header --out work/hdr_060.png
    python tools/strip_sheet.py --pages 60-75 --y0 0.10 --y1 0.20 --out work/custom.png

備註
    橫帶座標為相對值（原點左上），與 5.3.4 的 bbox 慣例一致，不因 dpi 變更失效。
"""
import argparse
import os

import fitz
from PIL import Image, ImageDraw

SRC_DEFAULT = "source/CR-166536.pdf"

# 相對座標 (x0, y0, x1, y1)，原點左上
BANDS = {
    "footer": (0.05, 0.86, 0.80, 0.95),   # 頁尾：報告編號 ＋ 印刷頁碼
    "header": (0.10, 0.04, 0.95, 0.16),   # 頁首：章節／SUBSYSTEM 標題
}


def parse_pages(spec):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def build(src, pages, box, dpi, width, out, rotate=0):
    doc = fitz.open(src)
    rows = []
    for n in pages:
        page = doc[n - 1]
        r = page.rect
        clip = fitz.Rect(
            r.x0 + box[0] * r.width, r.y0 + box[1] * r.height,
            r.x0 + box[2] * r.width, r.y0 + box[3] * r.height,
        )
        pix = page.get_pixmap(dpi=dpi, clip=clip, colorspace=fitz.csGRAY)
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        if rotate:
            # 原文的圖表為橫向印刷，須轉正才能判讀圖說
            img = img.rotate(rotate, expand=True)
        h = max(1, round(img.height * width / img.width))
        rows.append((n, img.resize((width, h), Image.LANCZOS)))

    label_w = 64
    gap = 6
    total_h = sum(im.height + gap for _, im in rows) + gap
    sheet = Image.new("L", (label_w + width, total_h), 255)
    draw = ImageDraw.Draw(sheet)
    y = gap
    for n, im in rows:
        sheet.paste(im, (label_w, y))
        draw.text((6, y + im.height // 2 - 6), f"p{n}", fill=0)
        draw.line((label_w - 2, y, label_w - 2, y + im.height), fill=160)
        y += im.height + gap
        draw.line((0, y - gap // 2, sheet.width, y - gap // 2), fill=200)

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sheet.save(out)
    print(f"{out}  {sheet.width}x{sheet.height}  {len(rows)} 頁")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC_DEFAULT)
    ap.add_argument("--pages", required=True, help="如 1-16 或 3,7,11")
    ap.add_argument("--band", choices=sorted(BANDS), default="footer")
    ap.add_argument("--y0", type=float), ap.add_argument("--y1", type=float)
    ap.add_argument("--x0", type=float), ap.add_argument("--x1", type=float)
    ap.add_argument("--dpi", type=int, default=600, help="裁切時的渲染解析度")
    ap.add_argument("--width", type=int, default=780, help="拼版中每列的寬度（像素）")
    ap.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270],
                    help="裁切後的旋轉角度（逆時針）。圖表頁為橫向印刷，多半需要 90")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    x0, y0, x1, y1 = BANDS[a.band]
    box = (a.x0 if a.x0 is not None else x0, a.y0 if a.y0 is not None else y0,
           a.x1 if a.x1 is not None else x1, a.y1 if a.y1 is not None else y1)
    build(a.src, parse_pages(a.pages), box, a.dpi, a.width, a.out, a.rotate)


if __name__ == "__main__":
    main()
