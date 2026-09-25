"""逐頁影像指標量測（W1.4 階段 1）

用途
    W1.4 要求「含污損疊影／圖表之頁面已重點檢查」，但全本 538 頁中哪幾頁屬於
    這兩類，目前沒有任何資料可查。本腳本逐頁算出一組指標，用來**決定要看哪幾頁**
    ——判讀本身仍由目視完成。這與 P0 的作法一致：統計量只用於取樣，結論一律
    先看圖再下。

    指標本身不下判斷。閾值不寫死，改由全本 538 頁的實際分佈取百分位，
    因此不需要事先知道「多少算異常」。

用法
    python tools/page_audit.py                      # → work/page_audit.json
    python tools/page_audit.py --pages 1-60 --top 5

指標
    comp_count      連通元件數，約等於字元數
    speckle_count   面積 ≤ 2 px 的元件數 → 疊影、雜點
    max_bbox_frac   最大元件外接框佔頁面比例 → 圖版、方框
    max_comp_frac   最大元件的實際墨色像素佔全頁墨色比例 → 圖版、大面積污損
    h_p50 / h_p95   元件高度中位數與 95 百分位（已排除雜點）
    edge_ink        頁緣外圈的墨色比例（已扣除裝訂孔帶）→ 掃描邊界異常
    row_regularity  列投影剖面自相關的最大峰值 → 文字頁高、圖版頁低

限制
    指標把圖版與大方框混在一起，分不開（實測 max_comp_frac 會把帶框的 I/O 摘要頁
    列為圖版）。它們的作用是把 538 頁縮減到數十頁的待看清單，不是分類器。

    **不含手寫偵測。** 曾實作 tall_frac（高元件佔比）與網格局部筆畫寬異質兩種指標，
    對兩個已知真值頁各只命中一個，且誤報壓不下去，已移除。更根本的是該需求源自
    R9（二值化切除手寫），而本管線 binarize_algo 為 none、輸出與來源逐像素相同，
    R9 不成立。手寫屬 R3，由 P4 轉錄時以 status: draft 與 issues 承接。
    詳見 docs/W1.4-逐頁抽檢結果.md。
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

try:
    from scipy import ndimage
except ImportError:
    sys.exit("需要 scipy：uv pip install --python .venv/Scripts/python.exe scipy")

SCANS_DEFAULT = "scans"
OUT_DEFAULT = "work/page_audit.json"

WORK_LONG = 2200      # 量測用長邊像素（約 200 dpi）。原尺寸 33.6 MP 逐頁做連通元件過慢
SPECKLE_MAX_AREA = 2  # 200 dpi 下，句點約 7 px；≤2 者視為雜點
EDGE_BAND = 0.02      # 頁緣外圈厚度（相對）
HOLE_BAND = (0.03, 0.08)  # 裝訂孔所在的水平帶，左右各一，量 edge_ink 時排除


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


def load_ink(path):
    im = Image.open(path).convert("L")
    scale = WORK_LONG / max(im.size)
    if scale < 1:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    return np.asarray(im) < 128


def edge_ink(ink):
    """頁緣外圈墨色比例，排除裝訂孔所在的水平帶。

    孔洞黑點壓在頁緣（W0.6 實測墨界 0.000–0.998），不排除的話每頁都會超標，
    指標就失去分辨力。孔位逐頁左右交替，故左右兩側同一高度帶一併排除。
    """
    h, w = ink.shape
    t = max(1, round(h * EDGE_BAND))
    s = max(1, round(w * EDGE_BAND))
    mask = np.zeros_like(ink)
    mask[:t, :] = mask[-t:, :] = True
    mask[:, :s] = mask[:, -s:] = True
    y0, y1 = round(h * HOLE_BAND[0]), round(h * HOLE_BAND[1])
    mask[y0:y1, :] = False                      # 孔洞帶，左右皆排除
    mask[h - y1:h - y0, :] = False
    return float(ink[mask].mean()) if mask.any() else 0.0


def row_regularity(ink):
    """列投影剖面的自相關峰值。打字稿行距固定，峰值高；圖版無週期，峰值低。"""
    prof = ink.mean(axis=1)
    prof = prof - prof.mean()
    if prof.std() == 0:
        return 0.0
    ac = np.correlate(prof, prof, mode="full")[len(prof) - 1:]
    ac = ac / ac[0]
    lo, hi = 8, min(120, len(ac))               # 行距合理範圍（200 dpi 下約 20–60 px）
    return float(ac[lo:hi].max()) if hi > lo else 0.0


def audit(path):
    full = load_ink(path)
    row = {
        "comp_count": 0,
        "speckle_count": 0,
        "max_bbox_frac": 0.0,
        "max_comp_frac": 0.0,
        "h_p50": 0.0,
        "h_p95": 0.0,
        "edge_ink": round(edge_ink(full), 5),
        "row_regularity": round(row_regularity(full), 4),
    }

    # 連通元件一律在內縮後的版面上計算。掃描頁緣有一圈黑邊，它本身是一個
    # 繞行整頁的連通元件（實測填充率僅 0.009），不排除的話 max_bbox_frac
    # 會逐頁都逼近 1.0 而失去分辨力——與 W0.7 的裝訂孔撐爆 bbox 是同一類錯誤。
    t = max(1, round(full.shape[0] * EDGE_BAND))
    s = max(1, round(full.shape[1] * EDGE_BAND))
    ink = full[t:-t, s:-s]
    h, w = ink.shape
    lab, n = ndimage.label(ink)
    row["comp_count"] = int(n)
    if n == 0:
        return row

    areas = ndimage.sum_labels(ink, lab, index=np.arange(1, n + 1))
    boxes = ndimage.find_objects(lab)
    hs = np.array([s_.stop - s_.start for s_, _ in boxes], dtype=float)
    ws = np.array([s_.stop - s_.start for _, s_ in boxes], dtype=float)

    row["speckle_count"] = int((areas <= SPECKLE_MAX_AREA).sum())
    row["max_bbox_frac"] = round(float((hs * ws).max() / (h * w)), 5)
    row["max_comp_frac"] = round(float(areas.max() / areas.sum()), 5)

    real = areas > SPECKLE_MAX_AREA
    if real.any():
        rh = hs[real]
        row["h_p50"] = round(float(np.median(rh)), 1)
        row["h_p95"] = round(float(np.percentile(rh, 95)), 1)
    return row


def report(rows, top):
    """依全本分佈列出各指標的極端頁。閾值不寫死，就是取排序後的前幾名。"""
    def show(key, label, reverse=True, fmt="{:.4f}"):
        ordered = sorted(rows, key=lambda r: r[key], reverse=reverse)[:top]
        cells = "  ".join(f"p{r['pdf_page']:03d}=" + fmt.format(r[key]) for r in ordered)
        print(f"  {label:22s} {cells}")

    vals = {k: np.array([r[k] for r in rows], dtype=float)
            for k in ("speckle_count", "max_bbox_frac", "max_comp_frac",
                      "edge_ink", "row_regularity", "comp_count")}
    print("\n全本分佈（中位數 / 95 百分位）")
    for k, v in vals.items():
        print(f"  {k:16s} {np.median(v):12.4f} {np.percentile(v, 95):12.4f}")

    print(f"\n各指標的極端頁（前 {top} 名，供階段 3 取樣）")
    show("speckle_count", "雜點最多（疊影）", fmt="{:.0f}")
    show("max_bbox_frac", "最大外接框（圖版方框）")
    show("max_comp_frac", "最大元件墨量（圖版污損）")
    show("edge_ink", "頁緣墨色最高")
    show("row_regularity", "行距最不規律（圖版）", reverse=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scans", default=SCANS_DEFAULT)
    ap.add_argument("--pages", help="如 1-60 或 11,250")
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--top", type=int, default=12, help="各指標列出的極端頁數")
    a = ap.parse_args()

    pages = parse_pages(a.pages) if a.pages else sorted(
        int(f[1:4]) for f in os.listdir(a.scans) if f.endswith(".webp"))
    if not pages:
        sys.exit(f"{a.scans}/ 內沒有 webp，請先執行 tools/render_scans.py")

    rows = []
    for k, n in enumerate(pages, 1):
        row = audit(os.path.join(a.scans, f"p{n:03d}.webp"))
        row["pdf_page"] = n
        rows.append(row)
        if k % 25 == 0 or k == len(pages):
            print(f"  … {k}/{len(pages)}", flush=True)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"\n{len(rows)} 頁 → {a.out}")
    report(rows, a.top)


if __name__ == "__main__":
    main()
