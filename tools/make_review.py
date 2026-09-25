"""產生 W1.4 逐頁審閱頁面：work/review.html

用途
    W1.4 要求全本逐頁過目。538 頁若逐一開檔比對，光是找檔案與記錄結果的成本就
    高過判讀本身。本腳本產生一份自足的 HTML，把影像、印刷頁碼、所屬 subsystem
    與 W1.3 的逐頁量測值併在一起顯示，並提供鍵盤翻頁與逐頁標記。

    審閱結果存於瀏覽器 localStorage，可匯出為 JSON。**匯出檔才是產物**，
    localStorage 隨時可能被清掉，看完一段就匯出一次。

用法
    python tools/make_review.py                      # → work/review.html
    python tools/make_review.py --out work/review.html --manifest work/scans.json

為什麼是內嵌資料的自足 HTML
    W1.4 尚未完成、影像尚未 commit，因此審閱只能在本機進行，頁面必須能以
    file:// 直接開啟。Chrome 會擋 file:// 的 fetch/XHR，故所有資料在產生時
    就內嵌進 HTML，執行期不讀取任何外部資料檔。影像則以相對路徑 ../scans/
    引用，img 標籤不受該限制。

注意
    本頁面是 W1.4 的拋棄式工具，不是網站的一部分，與 js/render/ 的凍結範圍無關。
    F3 掃描對照另由 W2.9 實作。
"""
import argparse
import json
import os

import yaml

META_DEFAULT = "data/meta.yaml"
MODULES_DEFAULT = "data/modules.yaml"
MANIFEST_DEFAULT = "work/scans.json"
OUT_DEFAULT = "work/review.html"

ROMAN = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
         (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]


def to_roman(n):
    out = ""
    for v, c in ROMAN:
        while n >= v:
            out += c
            n -= v
    return out


def from_roman(s):
    vals = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    total = peak = 0
    for ch in reversed(s.lower()):
        v = vals[ch]
        total += -v if v < peak else v
        peak = max(peak, v)
    return total


def printed_label(page_map, n):
    """由 page_map 推算印刷頁碼。回傳 None 表示該頁原文無頁碼，非漏填。"""
    for b in page_map:
        if b["pdf_start"] <= n < b["pdf_start"] + b["count"]:
            off = n - b["pdf_start"]
            fmt = b["label_format"]
            if fmt == "none":
                return None
            if fmt == "roman":
                return to_roman(from_roman(b["first_label"]) + off)
            return b.get("label_prefix", "") + str(int(b.get("first_label", 1)) + off)
    return None


def build_pages(meta, modules, manifest):
    by_page = {r["pdf_page"]: r for r in manifest}
    mods = {}
    for m in modules:
        a, b = m["pdf_pages"]
        for n in range(a, b + 1):
            mods[n] = f"{m['appendix']}{m['id']}　{m['name_en']}"

    exceptions = set(meta["scan_spec"]["exceptions"])
    bht = set(meta["license"].get("bht_original_pages") or [])

    pages = []
    for n in range(1, meta["document"]["pdf_pages"] + 1):
        r = by_page.get(n, {})
        flags = []
        if n in exceptions:
            flags.append("exception")
        if n in bht:
            flags.append("BHT")
        if r.get("orient_corr") is None:
            flags.append("方向未驗證")
        pages.append({
            "n": n,
            "label": printed_label(meta["page_map"], n),
            "mod": mods.get(n),
            "kb": round(r.get("bytes", 0) / 1024, 1),
            "ink": r.get("ink_ratio"),
            "corr": r.get("orient_corr"),
            "flags": flags,
        })
    return pages


TEMPLATE = r"""<!doctype html>
<meta charset="utf-8">
<title>CR-166536 逐頁審閱 — W1.4</title>
<style>
  :root { --bg:#3a3a3a; --panel:#222; --ink:#eee; --dim:#999; --ok:#4c9; --bad:#e66; }
  * { box-sizing:border-box; }
  body { margin:0; height:100vh; display:flex; background:var(--bg); color:var(--ink);
         font:13px/1.5 system-ui, "Segoe UI", sans-serif; overflow:hidden; }
  #side { width:260px; flex:none; background:var(--panel); display:flex; flex-direction:column;
          border-right:1px solid #000; }
  #side header { padding:10px 12px; border-bottom:1px solid #000; }
  #list { overflow-y:auto; flex:1; }
  #list div { padding:3px 12px; cursor:pointer; display:flex; gap:6px; white-space:nowrap; }
  #list div:hover { background:#333; }
  #list div.cur { background:#0a4a6a; }
  #list .pg { width:38px; color:var(--dim); }
  #list .lb { width:56px; }
  #list .mk { width:14px; text-align:center; }
  #main { flex:1; display:flex; flex-direction:column; min-width:0; }
  #bar { padding:8px 14px; background:var(--panel); border-bottom:1px solid #000;
         display:flex; gap:14px; align-items:center; flex-wrap:wrap; }
  #bar b { font-size:15px; }
  #bar .dim { color:var(--dim); }
  #view { flex:1; overflow:auto; display:flex; align-items:flex-start; justify-content:center;
          padding:10px; }
  #view img { background:#fff; box-shadow:0 2px 14px #0008; }
  #view.fit img { max-height:calc(100vh - 150px); width:auto; }
  #view.full img { width:auto; height:auto; max-width:none; }
  #foot { padding:8px 14px; background:var(--panel); border-top:1px solid #000;
          display:flex; gap:10px; align-items:center; }
  button { background:#444; color:var(--ink); border:1px solid #666; border-radius:4px;
           padding:4px 10px; cursor:pointer; font:inherit; }
  button:hover { background:#555; }
  input[type=text] { background:#111; color:var(--ink); border:1px solid #555; border-radius:4px;
                     padding:4px 8px; font:inherit; }
  #note { flex:1; }
  .tag { background:#555; border-radius:3px; padding:1px 6px; font-size:11px; }
  .tag.exception { background:#a60; }
  kbd { background:#111; border:1px solid #555; border-radius:3px; padding:0 4px; font-size:11px; }
</style>

<div id="side">
  <header>
    <div><b>W1.4 逐頁審閱</b></div>
    <div class="dim" id="prog"></div>
  </header>
  <div id="list"></div>
</div>

<div id="main">
  <div id="bar">
    <b id="ttl"></b>
    <span class="dim" id="meta"></span>
    <span id="flags"></span>
  </div>
  <div id="view" class="fit"><img id="img" alt=""></div>
  <div id="foot">
    <button onclick="mark('ok')">✓ 無問題 <kbd>o</kbd></button>
    <button onclick="mark('bad')">✗ 有問題 <kbd>x</kbd></button>
    <button onclick="mark(null)">清除 <kbd>c</kbd></button>
    <input type="text" id="note" placeholder="備註（自動儲存）">
    <button onclick="zoom()">縮放 <kbd>z</kbd></button>
    <button onclick="exportJSON()">匯出 JSON</button>
    <label style="cursor:pointer">匯入<input type="file" id="imp" hidden accept=".json"></label>
  </div>
</div>

<script>
const PAGES = __PAGES__;
const KEY = "gtrs-w14-review";
let marks = {};
try { marks = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { marks = {}; }
let i = 0;

const $ = id => document.getElementById(id);
const pad = n => String(n).padStart(3, "0");
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(marks)); } catch (e) {} };

function buildList() {
  $("list").innerHTML = PAGES.map((p, k) =>
    `<div data-k="${k}"><span class="pg">${p.n}</span>` +
    `<span class="lb">${p.label ?? "—"}</span>` +
    `<span class="mk" id="mk${k}"></span></div>`).join("");
  $("list").onclick = e => {
    const d = e.target.closest("[data-k]");
    if (d) go(+d.dataset.k);
  };
}

function refreshMark(k) {
  const m = marks[PAGES[k].n];
  const el = $("mk" + k);
  if (!el) return;
  el.textContent = m ? (m.v === "ok" ? "✓" : m.v === "bad" ? "✗" : "") : "";
  el.style.color = m && m.v === "bad" ? "var(--bad)" : "var(--ok)";
}

function progress() {
  const done = PAGES.filter(p => marks[p.n] && marks[p.n].v).length;
  const bad = PAGES.filter(p => marks[p.n] && marks[p.n].v === "bad").length;
  $("prog").textContent = `${done} / ${PAGES.length} 已標記　${bad} 有問題`;
}

function go(k) {
  i = Math.max(0, Math.min(PAGES.length - 1, k));
  const p = PAGES[i];
  $("img").src = `../scans/p${pad(p.n)}.webp`;
  $("ttl").textContent = `pdf ${p.n}　印刷 ${p.label ?? "（無頁碼）"}`;
  $("meta").textContent =
    [p.mod, p.kb ? p.kb + " KB" : null,
     p.ink != null ? "墨色 " + p.ink.toFixed(4) : null,
     p.corr != null ? "方向 " + p.corr.toFixed(3) : null].filter(Boolean).join("　│　");
  $("flags").innerHTML = p.flags.map(f =>
    `<span class="tag ${f === "exception" ? "exception" : ""}">${f}</span>`).join(" ");
  $("note").value = (marks[p.n] && marks[p.n].note) || "";
  document.querySelectorAll("#list .cur").forEach(d => d.classList.remove("cur"));
  const row = document.querySelector(`[data-k="${i}"]`);
  if (row) { row.classList.add("cur"); row.scrollIntoView({ block: "nearest" }); }
  // 預載前後各一頁，翻頁時不必等解碼
  [i - 1, i + 1].forEach(j => {
    if (PAGES[j]) new Image().src = `../scans/p${pad(PAGES[j].n)}.webp`;
  });
}

function mark(v) {
  const n = PAGES[i].n;
  if (v === null) delete marks[n];
  else marks[n] = { v, note: $("note").value, at: new Date().toISOString() };
  save(); refreshMark(i); progress();
  if (v) go(i + 1);
}

$("note").oninput = () => {
  const n = PAGES[i].n;
  marks[n] = Object.assign({ v: null }, marks[n], { note: $("note").value });
  save();
};

function zoom() { $("view").classList.toggle("fit"); $("view").classList.toggle("full"); }

function exportJSON() {
  const rows = PAGES.filter(p => marks[p.n]).map(p => Object.assign(
    { pdf_page: p.n, printed_page: p.label }, marks[p.n]));
  const b = new Blob([JSON.stringify(rows, null, 1)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(b);
  a.download = "w14-review.json";
  a.click();
}

$("imp").onchange = e => {
  const f = e.target.files[0];
  if (!f) return;
  f.text().then(t => {
    JSON.parse(t).forEach(r => { marks[r.pdf_page] = { v: r.v, note: r.note, at: r.at }; });
    save(); PAGES.forEach((_, k) => refreshMark(k)); progress(); go(i);
  });
};

addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT") { if (e.key === "Escape") e.target.blur(); return; }
  const k = { ArrowRight: 1, ArrowLeft: -1, PageDown: 10, PageUp: -10 }[e.key];
  if (k) { go(i + k); e.preventDefault(); return; }
  if (e.key === "Home") go(0);
  else if (e.key === "End") go(PAGES.length - 1);
  else if (e.key === "o") mark("ok");
  else if (e.key === "x") mark("bad");
  else if (e.key === "c") mark(null);
  else if (e.key === "z") zoom();
  else if (e.key === "n") $("note").focus();
});

buildList();
PAGES.forEach((_, k) => refreshMark(k));
progress();
go(0);
</script>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", default=META_DEFAULT)
    ap.add_argument("--modules", default=MODULES_DEFAULT)
    ap.add_argument("--manifest", default=MANIFEST_DEFAULT)
    ap.add_argument("--out", default=OUT_DEFAULT)
    a = ap.parse_args()

    with open(a.meta, encoding="utf-8") as f:
        meta = yaml.safe_load(f)
    with open(a.modules, encoding="utf-8") as f:
        modules = yaml.safe_load(f)
    manifest = []
    if os.path.exists(a.manifest):
        with open(a.manifest, encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        print(f"（找不到 {a.manifest}，逐頁量測值留空）")

    pages = build_pages(meta, modules, manifest)
    html = TEMPLATE.replace("__PAGES__", json.dumps(pages, ensure_ascii=False))

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)

    labelled = sum(1 for p in pages if p["label"])
    print(f"{a.out}　{len(pages)} 頁　{len(html)/1024:.0f} KB")
    print(f"有印刷頁碼 {labelled} 頁，無頁碼 {len(pages)-labelled} 頁")
    print("以瀏覽器直接開啟（file:// 可用，資料已內嵌）")


if __name__ == "__main__":
    main()
