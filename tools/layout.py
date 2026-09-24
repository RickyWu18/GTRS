"""版面切割：把掃描頁切成區塊，輸出相對座標 bbox。

用途（W0.7／T2.1）
    來源無文字層，內容須由 VLM 逐塊判讀。整頁餵給 VLM 會被降採樣到長邊約 1568 px，
    等於只剩約 150 dpi，細下標與手寫符號會靜默掉字；切成區塊後每塊可放大到
    接近 600 dpi 原生解析度再判讀。切割同時產出 bbox，供 5.3.4 的掃描對照使用。

    本專案的掃描是乾淨的 1-bit 打字稿，用投影剖面即可切割，不需版面偵測模型
    （本機無 GPU）。確定性、可重跑，且不會如模型般「補全」不存在的區塊。

座標
    一律為相對值 [x1, y1, x2, y2]，原點左上，相對於整頁（非核心區），
    故不因 dpi 或日後改用不同解析度而失效（計畫書 5.3.4）。

用法
    python tools/layout.py --page 250 --out work/layout_250.json --overlay work/layout_250.png
"""
import argparse
import json
import os

import fitz
import numpy as np
from PIL import Image, ImageDraw

# 版面核心區：只排除掃描頁緣黑邊。裝訂孔另以 _mask_binder_holes 處理。
#
# 裝訂孔逐頁左右交替（左頁在 x≈0.04–0.07，右頁在 x≈0.94–0.96）。不處理的話，
# 孔洞黑點會把同高度所有區塊的 bbox 撐到頁緣，成為無聲的系統性偏差。
# 但固定切邊亦不可行：附錄 C 的數值表左欄（FORTRAN 變數名）起於 x≈0.06，
# 與左頁孔洞位置重疊，切掉孔就會一併切掉內容。故改為只遮去孔洞本身。
CORE = (0.020, 0.030, 0.980, 0.975)
HOLE_STRIP = 0.12   # 僅於左右各此比例的邊帶內尋找孔洞
HOLE_RUN = 0.012    # 連續墨色長度達此比例頁寬者視為孔洞（打字稿筆畫不會這麼長）
INK = 200          # 灰階門檻；細線在降採樣後會變淺灰，用 128 會整條消失
ROW_MIN = 0.002    # 一列視為「有內容」的最低墨色佔比
MIN_H = 0.004      # 區塊最小高度（相對整頁），濾除掃描雜點


def _mask_binder_holes(core, page_w):
    """把左右邊帶內的裝訂孔黑點抹去（就地修改）。

    孔為實心圓點，水平方向有長達約 0.022 頁寬的連續墨色；打字稿的筆畫不會如此，
    故以連續長度判別，不依賴孔的固定位置——本掃描的孔逐頁左右交替。
    """
    ch, cw = core.shape
    minrun = max(4, int(HOLE_RUN * page_w))
    strips = ((0, int(cw * HOLE_STRIP)), (int(cw * (1 - HOLE_STRIP)), cw))
    for s, e in strips:
        sub = core[:, s:e]
        for i in range(ch):
            row = sub[i]
            if not row.any():
                continue
            edges = np.flatnonzero(np.diff(np.concatenate(([0], row.view(np.int8), [0]))))
            for a_, b_ in zip(edges[0::2], edges[1::2]):
                if b_ - a_ >= minrun:
                    row[a_:b_] = False


def segment(page, dpi, gap_ratio):
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    H, W = a.shape
    y0, y1 = int(H * CORE[1]), int(H * CORE[3])
    x0, x1 = int(W * CORE[0]), int(W * CORE[2])
    core = a[y0:y1, x0:x1] < INK
    _mask_binder_holes(core, W)
    ch, cw = core.shape

    rowink = core.mean(axis=1)
    on = rowink > ROW_MIN
    if not on.any():
        return [], (H, W)

    # 先切出文字列帶
    edges = np.flatnonzero(np.diff(np.concatenate(([0], on.view(np.int8), [0]))))
    bands = list(zip(edges[0::2], edges[1::2]))
    heights = [b - a_ for a_, b in bands]
    line_h = float(np.median(heights)) if heights else 1.0

    # 列帶間距小於 gap_ratio × 行高者視為同一區塊
    # （公式的上下標會被切成數個列帶，須併回同一式）
    gap = max(2.0, gap_ratio * line_h)
    blocks = []
    cur = list(bands[0])
    for s, e in bands[1:]:
        if s - cur[1] <= gap:
            cur[1] = e
        else:
            blocks.append(tuple(cur))
            cur = [s, e]
    blocks.append(tuple(cur))

    out = []
    for bs, be in blocks:
        # 要求該欄至少有兩個墨色像素，濾除頁緣的孤立掃描雜點——
        # 用 any() 會讓單一雜點把 bbox 一路撐到頁緣
        xs = np.flatnonzero(core[bs:be].sum(axis=0) >= 2)
        if xs.size == 0:
            continue
        bx0, bx1 = int(xs[0]), int(xs[-1]) + 1
        rel = [round(float(x0 + bx0) / W, 4), round(float(y0 + bs) / H, 4),
               round(float(x0 + bx1) / W, 4), round(float(y0 + be) / H, 4)]
        if rel[3] - rel[1] < MIN_H:
            continue
        out.append({
            "bbox": rel,
            "lines": int(((rowink[bs:be] > ROW_MIN)[:-1] !=
                          (rowink[bs:be] > ROW_MIN)[1:]).sum() // 2 + 1),
            "ink": round(float(core[bs:be, bx0:bx1].mean()), 4),
            "centered": bool(abs(((bx0 + bx1) / 2) - cw / 2) < cw * 0.08),
        })
    return out, (H, W)


def overlay(page, blocks, dpi, path):
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples).convert("RGB")
    d = ImageDraw.Draw(img)
    for i, b in enumerate(blocks):
        x0, y0, x1, y1 = b["bbox"]
        box = (x0 * img.width, y0 * img.height, x1 * img.width, y1 * img.height)
        d.rectangle(box, outline=(220, 0, 0), width=2)
        d.text((box[0] + 3, box[1] + 2), str(i), fill=(0, 90, 220))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="source/CR-166536.pdf")
    ap.add_argument("--page", type=int, required=True, help="pdf 頁碼（1 起算）")
    ap.add_argument("--dpi", type=int, default=150, help="切割時的分析解析度")
    ap.add_argument("--gap-ratio", type=float, default=0.45,
                    help="列帶間距超過此倍行高才斷成新區塊。"
                         "1.1 會把整頁公式併成一塊；0.4–0.5 在 p250 可切出與人眼一致的 13 塊")
    ap.add_argument("--out")
    ap.add_argument("--overlay")
    a = ap.parse_args()

    doc = fitz.open(a.src)
    page = doc[a.page - 1]
    blocks, (H, W) = segment(page, a.dpi, a.gap_ratio)

    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump({"page": a.page, "dpi": a.dpi, "blocks": blocks},
                  open(a.out, "w"), indent=1)
    if a.overlay:
        overlay(page, blocks, 110, a.overlay)

    print("p%d：%d 個區塊" % (a.page, len(blocks)))
    for i, b in enumerate(blocks):
        print("  %2d %s lines=%-3d ink=%.3f %s"
              % (i, b["bbox"], b["lines"], b["ink"], "置中" if b["centered"] else ""))


if __name__ == "__main__":
    main()
