"""掃描批次轉檔：source/CR-166536.pdf → scans/pNNN.webp（W1.2 探針／W1.3 量產）

用途
    來源 PDF 的 538 頁中，536 頁內嵌的就是 1-bit 雙階 PNG（6600×5088，恰為 600 dpi，
    以旋轉矩陣置於直向頁），另 2 頁為 300 dpi 8-bit RGB JPEG。因此本腳本**不做渲染**，
    只把內嵌影像原樣抽出、轉正、以 webp-lossless 重新封裝。抽出結果與來源逐像素相同
    （已由 --check 驗證），不經過任何重新取樣。

    不可改走 page.get_pixmap(dpi=600)：該路徑輸出 5100×6600，帶有輕微縮放
    （頁寬 610.56 pt ＝ 8.48 in，600 dpi 應為 5088 px），不是逐像素等同來源。

用法
    python tools/render_scans.py --pages 250,251,492   # W1.2 探針，先轉幾頁
    python tools/render_scans.py --all                 # W1.3 全本，約 8 分鐘
    python tools/render_scans.py --all --manifest work/scans.json

「轉正」與 scan_spec.rotate: none 不衝突
    scan_spec 的 rotate 指的是**內容方向**的校正（例如把橫向印刷的圖表轉成可閱讀），
    該項為 none，即一律保留原文印刷方向不動。本腳本所做的旋轉是還原 PDF 的影像置放
    矩陣——內嵌影像以橫向儲存、由 PDF 的 transform 轉成直向頁，抽出時必須自行套用同一
    個轉換，否則得到的是躺著的頁面。兩者是不同的事。

ROTATE_90 與 ROTATE_270 的自動判別
    兩者產出尺寸完全相同（5088×6600），用錯會得到上下顛倒的整本書。W0.6 報告記載
    「這類錯誤沒有任何數值特徵可供自動偵測，只能靠目視」——實際上有：page.get_pixmap()
    會套用 PDF 的置放矩陣，其方向必然正確，故可用一張 50 dpi 的低解析度渲染當基準，
    與兩個旋轉候選比相關係數。實測 pdf 250 為 ROTATE_90 +0.90、ROTATE_270 +0.003，
    區別極大，不存在誤判空間。本腳本逐頁執行此檢查，不通過即中止。
"""
import argparse
import hashlib
import io
import json
import os
import sys

import fitz
import numpy as np
import yaml
from PIL import Image

SRC_DEFAULT = "source/CR-166536.pdf"
META_DEFAULT = "data/meta.yaml"
OUT_DEFAULT = "scans"

# 本腳本實作的 scan_spec。與 data/meta.yaml 不符即中止——G1 已凍結這些欄位，
# 不符代表規格被改動而腳本未跟上，此時繼續執行會產生與規格不一致的影像。
SPEC_IMPLEMENTED = {
    "method": "bilevel-from-source",
    "dpi": 600,
    "format": "webp-lossless",
    "binarize_algo": "none",
    "deskew": False,
    "crop": "none",
    "rotate": "none",
}

ORIENT_DPI = 50        # 方向檢查用的基準渲染解析度，僅供比對，不進輸出
ORIENT_MIN_CORR = 0.50  # 實測正確者 +0.90、錯誤者 +0.003，門檻取中間


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


def check_spec(meta_path):
    """核對 data/meta.yaml 的 scan_spec 與本腳本實作一致。"""
    with open(meta_path, encoding="utf-8") as f:
        spec = yaml.safe_load(f)["scan_spec"]
    bad = {k: (v, spec.get(k)) for k, v in SPEC_IMPLEMENTED.items() if spec.get(k) != v}
    if bad:
        for k, (want, got) in bad.items():
            print(f"scan_spec.{k}：腳本實作 {want!r}，meta.yaml 為 {got!r}", file=sys.stderr)
        sys.exit("scan_spec 與本腳本實作不符，已中止。G1 凍結欄位若確有變更，須同步改本腳本。")
    if not spec.get("decided_by"):
        sys.exit("scan_spec.decided_by 未填 → G1 尚未通過，不得批次轉檔（WBS W1.3）。")
    return spec


def reference(page):
    """低解析度基準渲染。get_pixmap 會套用 PDF 的置放矩陣，方向必然正確。"""
    pix = page.get_pixmap(dpi=ORIENT_DPI, colorspace=fitz.csGRAY)
    return np.asarray(
        Image.frombytes("L", (pix.width, pix.height), pix.samples), dtype=float
    )


def correlation(img, ref):
    small = img.convert("L").resize((ref.shape[1], ref.shape[0]), Image.LANCZOS)
    a = np.asarray(small, dtype=float)
    if a.std() == 0 or ref.std() == 0:
        return None          # 全黑或全白頁（如 pdf 11）無從比對方向
    return float(np.corrcoef(a.ravel(), ref.ravel())[0, 1])


def upright(img, page):
    """把抽出的影像轉成頁面的印刷方向，並回報所用的旋轉與相關係數。"""
    ref = reference(page)
    if img.width <= img.height:
        # 直向儲存，未經置放旋轉（pdf 1、537 的 JPEG 屬此類）
        return img, "none", correlation(img, ref)

    scored = []
    for name, op in (("ROTATE_90", Image.ROTATE_90), ("ROTATE_270", Image.ROTATE_270)):
        cand = img.transpose(op)
        scored.append((correlation(cand, ref), name, cand))

    if scored[0][0] is None:
        # 無紋理可比（pdf 11 整頁全黑）。此時兩個方向的輸出在內容上無差異，
        # 取 ROTATE_90 以與其餘各頁一致，並在 manifest 標明未經驗證。
        return img.transpose(Image.ROTATE_90), "ROTATE_90", None

    scored.sort(key=lambda t: -t[0])
    corr, name, cand = scored[0]
    if corr < ORIENT_MIN_CORR:
        sys.exit(f"方向檢查未通過：最佳候選 {name} 相關係數僅 {corr:+.4f}"
                 f"（門檻 {ORIENT_MIN_CORR}）。請勿採用本次輸出。")
    return cand, name, corr


def render(doc, n, out_dir, check_roundtrip):
    page = doc[n - 1]
    imgs = page.get_images(full=True)
    if len(imgs) != 1:
        sys.exit(f"pdf {n}：內嵌影像數為 {len(imgs)}，非預期的 1，本腳本不處理此情形。")

    data = doc.extract_image(imgs[0][0])
    img = Image.open(io.BytesIO(data["image"]))
    img, rot, corr = upright(img, page)

    buf = io.BytesIO()
    img.save(buf, format="WEBP", lossless=True, quality=100, method=4)
    blob = buf.getvalue()

    if check_roundtrip:
        back = Image.open(io.BytesIO(blob))
        src = np.asarray(img.convert("RGB"))
        if not np.array_equal(src, np.asarray(back.convert("RGB"))):
            sys.exit(f"pdf {n}：webp 往返不是逐像素相同，format 宣稱 lossless 但實際有損。")

    path = os.path.join(out_dir, f"p{n:03d}.webp")
    with open(path, "wb") as f:
        f.write(blob)

    gray = np.asarray(img.convert("L"))
    return {
        "pdf_page": n,
        "file": os.path.basename(path),
        "width": img.width,
        "height": img.height,
        "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "src_ext": data["ext"],
        "src_bpc": data.get("bpc"),
        "rotation": rot,
        "orient_corr": None if corr is None else round(corr, 4),
        # 墨色比例：W1.4 用以定位異常頁。pdf 11 為全本唯一的 1.0，其餘中位數約 0.028
        "ink_ratio": round(float((gray < 128).mean()), 4),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC_DEFAULT)
    ap.add_argument("--meta", default=META_DEFAULT)
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--pages", help="如 250,251 或 69-80")
    ap.add_argument("--all", action="store_true", help="全本，等同 --pages 1-<總頁數>")
    ap.add_argument("--manifest", help="逐頁結果寫入此 JSON（建議放 work/，未進版控）")
    ap.add_argument("--no-check", action="store_true",
                    help="略過 webp 往返的逐像素比對（省時，但放棄無損的唯一驗證手段）")
    a = ap.parse_args()

    if not (a.pages or a.all):
        sys.exit("需指定 --pages 或 --all。")

    spec = check_spec(a.meta)
    doc = fitz.open(a.src)
    pages = list(range(1, doc.page_count + 1)) if a.all else parse_pages(a.pages)
    os.makedirs(a.out, exist_ok=True)

    rows, total = [], 0
    for n in pages:
        row = render(doc, n, a.out, not a.no_check)
        rows.append(row)
        total += row["bytes"]
        flag = ""
        if n in spec["exceptions"]:
            flag = "  ← scan_spec.exceptions"
        corr = "  corr=—" if row["orient_corr"] is None else f"  corr={row['orient_corr']:+.3f}"
        print(f"p{n:03d}  {row['width']}x{row['height']}  {row['bytes']/1024:7.1f} KB  "
              f"{row['rotation']:10s}{corr}  ink={row['ink_ratio']:.3f}{flag}")

    print(f"\n{len(rows)} 頁　{total/1024/1024:.1f} MB　平均 {total/len(rows)/1024:.1f} KB/頁")

    unverified = [r["pdf_page"] for r in rows if r["orient_corr"] is None]
    if unverified:
        print(f"方向未經驗證（無紋理可比）：{unverified} —— 須目視確認")

    if a.manifest:
        os.makedirs(os.path.dirname(os.path.abspath(a.manifest)), exist_ok=True)
        with open(a.manifest, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print(f"manifest → {a.manifest}")


if __name__ == "__main__":
    main()
