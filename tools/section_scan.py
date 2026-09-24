"""附錄 A 頁型判別：找出各 subsystem 的方框摘要頁，即節界。

背景（W0.3／W0.4）
    附錄 A 的 282 頁依 subsystem 分節，每節的頁型固定輪替：

      1. 方框摘要頁 —— 外框為一組長橫線，框內為 subsystem 編號、名稱與
         Inputs/Outputs 清單。這是 modules.yaml（W5.2）的來源。
      2. 符號表頁 —— 頁首 `SUBSYSTEM NO. nn: <名稱>`，內文為
         `Symbol | Description | Units` 三欄。這是 W0.4 的標的。
      3. 公式頁 —— 頁首 `EQUATIONS` / `(CONTINUED)` / `(CONCLUDED)`
         ＋ `SUBSYSTEM nn--<名稱>`。

    先前嘗試以「相鄰頁頁首影像差異」找節界失敗：頁首首行會在
    EQUATIONS／(CONTINUED)／(CONCLUDED) 間變動，且三種頁型的頁首垂直位置不同，
    相鄰頁距離中位數達 0.40，無從設閾值。改以頁型本身的結構特徵判別——
    只有方框摘要頁含有橫貫版面的長橫線，偵測該特徵即可精確切出節界。

用法
    python tools/section_scan.py --pages 69-350 --out work/section_breaks.json
"""
import argparse
import json
import os

import fitz
import numpy as np
from PIL import Image

XRANGE = (0.10, 0.95)    # 排除左右頁緣的裝訂孔黑點
YRANGE = (0.04, 0.96)    # 排除掃描頁緣的黑邊——該黑邊會使每頁都出現滿版墨色列
INK = 200                # 灰階門檻。來源為 600 dpi 雙階，在 100 dpi 下一條細線
                         # 只覆蓋取樣格約三成，平均後灰階約 170——用 128 會整條消失。


BLOCKS = 8                   # 版面切成幾個直條
SLOPES = range(-3, 4)        # 每直條的縱向位移（像素），涵蓋約 ±1.9° 傾斜
SLACK = 2                    # 容許幾個直條落空（取第 SLACK+1 小的覆蓋率為分數）


def rule_score(page, dpi):
    """回傳該頁最「橫貫」的一條線的覆蓋率，以及達 0.85 的線條數。

    直接看單列會漏掉傾斜頁的橫線（實測方框頁 p253 單列最高僅 0.32）；
    縱向膨脹會把密排公式一併灌高；整頁錯切則因採樣橫跨多行文字，
    在文字密集處湊出約 0.7 的假覆蓋率。三者皆不可用。

    故改為分塊小型 Hough：版面切成 BLOCKS 個直條，各自算每列覆蓋率，
    再於數個斜率下取「各直條覆蓋率的最小值」。真橫線在每一直條都高，
    最小值因此高；文字列不可能在全部直條同時緻密，最小值必低。
    直條寬約 90 px，0.9° 傾斜在其中僅漂移約 1.4 px，可忽略。
    """
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    h, w = a.shape
    core = a[int(h * YRANGE[0]):int(h * YRANGE[1]),
             int(w * XRANGE[0]):int(w * XRANGE[1])] < INK
    ch, cw = core.shape

    bw = cw // BLOCKS
    cov = np.stack([core[:, b * bw:(b + 1) * bw].mean(axis=1) for b in range(BLOCKS)])

    rows = np.arange(ch)
    best = np.zeros(ch, dtype=np.float32)
    for s in SLOPES:
        aligned = np.stack([cov[b][np.clip(rows + s * (b - BLOCKS // 2), 0, ch - 1)]
                            for b in range(BLOCKS)])
        # 取各直條覆蓋率的第三小值：方框寬度小於版面寬度（實測約 86%），
        # 兩端的直條本就不會被線通過，用最小值會把真方框壓到 0.29。
        m = np.sort(aligned, axis=0)[SLACK]
        np.maximum(best, m, out=best)

    return float(best.max()), int((best > 0.85).sum()), first_line_span(core)


def first_line_span(core):
    """頁面上緣第一行文字的水平起訖（相對於版面核心區，0–1）。

    三種頁型的首行對齊方式不同，可據此分類而不需判讀文字：
      公式頁     首行 `EQUATIONS` 置中          → 起點約 0.35 以後
      符號表頁   首行 `SUBSYSTEM NO. nn:` 靠左  → 起點接近 0
      方框摘要頁 首行即方框上框線               → 由 rule_score 另行認出
    """
    ch, cw = core.shape
    band = core[int(ch * 0.02):int(ch * 0.30)]
    rowink = band.mean(axis=1)
    hit = np.flatnonzero(rowink > 0.004)
    if hit.size == 0:
        return None
    start = hit[0]
    end = start
    while end + 1 < len(rowink) and rowink[end + 1] > 0.004:
        end += 1
    colink = band[start:end + 1].any(axis=0)
    xs = np.flatnonzero(colink)
    if xs.size == 0:
        return None
    return [round(float(xs[0] / cw), 3), round(float(xs[-1] / cw), 3)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="source/CR-166536.pdf")
    ap.add_argument("--pages", required=True, help="如 69-350")
    ap.add_argument("--dpi", type=int, default=100)
    ap.add_argument("--threshold", type=float, default=0.80,
                    help="視為長橫線的列墨色佔比")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    lo, hi = (int(x) for x in a.pages.split("-"))
    doc = fitz.open(a.src)

    rows = []
    for n in range(lo, hi + 1):
        mx, cnt, span = rule_score(doc[n - 1], a.dpi)
        if mx >= a.threshold:
            kind = "boxed"                      # 方框摘要頁 ＝ 節界
        elif span is None:
            kind = "blank"
        elif span[0] < 0.15:
            kind = "left"                       # 靠左首行：符號表／敘述頁
        else:
            kind = "centered"                   # 置中首行：EQUATIONS 公式頁
        rows.append({"page": n, "rule": round(mx, 4), "rule_rows": cnt,
                     "first_line": span, "kind": kind})

    boxed = [r["page"] for r in rows if r["kind"] == "boxed"]
    counts = {}
    for r in rows:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump({"range": [lo, hi], "threshold": a.threshold,
               "pages": rows, "boxed_pages": boxed}, open(a.out, "w"), indent=1)

    print("頁數 %d" % len(rows))
    print("頁型分布:", counts)
    print("方框摘要頁（節界候選）%d 頁:" % len(boxed))
    print(boxed)


if __name__ == "__main__":
    main()
