"""頁尾左下角報告編號掃描：判定每頁源自 BHT 原報告或 STI 改寫。

依據（W0.2）
    原文正文（印刷頁 2 ＝ pdf 16）自述：

      "All pages from the original BHT mathematical model report (Ref. 1) which
       remain unchanged are presented in this report with the Bell report number,
       301-099-001, located in the lower left-hand corner. New or corrected pages
       are identified by the STI report number, TR-1195-2."

    故每頁左下角的編號即該頁的來源標記，不需憑目視搜尋版權符號。
    三種編號字數差異明顯（`TR-1195-2` 9 字、`301-099-001` 11 字、
    `TR-1195-2 (Rev. A)` 18 字），可先以文字塊寬度分群，再抽樣目視確認。

    本腳本只量寬度並分群，不判讀內容；判讀仍由人／VLM 對影像為之。

用法
    python tools/footer_scan.py --out work/footer.json
"""
import argparse
import json
import os
import sys

import fitz
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout import CORE, INK, _mask_binder_holes   # noqa: E402

FOOTER = (0.84, 0.990)   # 頁尾搜尋範圍（相對整頁）；實測頁尾位置逐頁浮動。
                         # 頁緣黑邊亦落在此範圍內，靠下方的 LEFT_MAX 濾除。
ROW_MIN = 0.002
GROUP_GAP = 0.030        # 欄位間距超過此比例頁寬即視為不同文字塊
LEFT_MAX = 0.25          # 頁尾編號必起於版面左側；據此排除誤選的內容列
MIN_W = 0.030            # 文字塊最小寬度。未達者多為殘留的裝訂孔碎點——
                         # 它位在左側又在頁面最下方，不濾掉就會蓋住真正的頁尾

# 原文為打字稿等寬字體，單字元寬實測 ≈ 0.0096 頁寬，故字串寬度即字數。
# 三種編號的實測寬度（見 W0.2）：
LABELS = [
    ((0.076, 0.096), "TR-1195-2",          "STI"),   #  9 字
    ((0.096, 0.115), "301-099-001",        "BHT"),   # 11 字　← 原 BHT 報告未改動之頁
    ((0.160, 0.190), "TR-1195-2 (Rev. A)", "STI"),   # 18 字
]


def footer_left(page, dpi):
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    H, W = a.shape
    x0 = int(W * CORE[0])
    core = a[int(H * FOOTER[0]):int(H * FOOTER[1]), x0:int(W * CORE[2])] < INK
    _mask_binder_holes(core, W)
    ch, cw = core.shape

    on = core.mean(axis=1) > ROW_MIN
    if not on.any():
        return None
    edges = np.flatnonzero(np.diff(np.concatenate(([0], on.view(np.int8), [0]))))
    bands = list(zip(edges[0::2], edges[1::2]))
    gap = max(3, int(GROUP_GAP * W))

    # 由下往上取第一條「起於版面左側」的文字帶＝頁尾；
    # 內容列可能延伸到頁尾範圍內，但不會貼著左邊界起始。
    for bs, be in reversed(bands):
        cols = np.flatnonzero(core[bs:be].sum(axis=0) >= 2)
        if cols.size == 0:
            continue
        start = float(x0 + cols[0]) / W
        if start > LEFT_MAX:
            continue
        split = np.flatnonzero(np.diff(cols) > gap)
        end = cols[split[0]] if split.size else cols[-1]
        w = float(end - cols[0]) / W
        if w < MIN_W:
            continue
        label = source = None
        for (lo, hi), text, src in LABELS:
            if lo <= w < hi:
                label, source = text, src
        return {
            "y": round(float(int(H * FOOTER[0]) + bs) / H, 4),
            "x0": round(start, 4),
            "w": round(w, 4),
            "label": label,
            "source": source,
        }
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="source/CR-166536.pdf")
    ap.add_argument("--pages", default="1-538")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    lo, hi = (int(x) for x in a.pages.split("-"))
    doc = fitz.open(a.src)

    rows = []
    for n in range(lo, hi + 1):
        f = footer_left(doc[n - 1], a.dpi)
        rows.append({"page": n, **(f or {"y": None, "x0": None, "w": None,
                                         "label": None, "source": None})})
        if (n - lo + 1) % 100 == 0:
            print("...", n, file=sys.stderr, flush=True)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(rows, open(a.out, "w"), indent=1)

    ws = [r["w"] for r in rows if r["w"] is not None]
    print("有頁尾編號的頁數 %d / %d" % (len(ws), len(rows)))

    from collections import Counter
    c = Counter(r["label"] for r in rows)
    for k, v in c.most_common():
        print("  %-20s %4d 頁" % (k if k else "（未分類／無頁尾）", v))

    bht = [r["page"] for r in rows if r["source"] == "BHT"]
    print("\nBHT 原件頁（301-099-001）共 %d 頁:" % len(bht))
    print(bht)

    unknown = [r["page"] for r in rows if r["w"] is not None and r["label"] is None]
    print("\n有頁尾但寬度不落在三類之內 %d 頁（需人工確認）:" % len(unknown))
    print(unknown[:60])


if __name__ == "__main__":
    main()
