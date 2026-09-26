"""產生資料比對頁面：左側資料、右側掃描原件（W2.3 起各轉錄工項共用）

用途
    轉錄產出的 YAML 需要人眼逐筆對照掃描原件才能由 draft 升為 reviewed（計畫書 9.5）。
    本腳本把資料與對應的頁面影像並排，左側點選一筆即在右側顯示其來源頁。

    設計為通用：任何「一筆資料對應某些頁面」的 YAML 皆可用。目前支援
      symbols.yaml   —— 無 pdf_page 欄位，以 scope 經 modules.yaml 解析出該
                        subsystem 的符號表頁範圍（計畫書 5.4 未定義頁碼欄位）
      equations/*.yaml —— 直接使用 pdf_page／pdf_pages（5.3.1）

用法
    python tools/make_data_review.py work/w23/*.yaml --out work/review-w23.html
    python tools/make_data_review.py data/symbols.yaml

為什麼是內嵌資料的自足 HTML
    與 tools/make_review.py 同理：Chrome 會擋 file:// 的 fetch/XHR，故資料在產生時
    即內嵌。影像以相對路徑 ../scans/ 引用，img 標籤不受該限制。KaTeX 由 CDN 載入，
    與 index.html 同一來源。

注意
    產出置於 work/（未進版控），可隨時重建。本頁面是比對工具，不是網站的一部分，
    與 js/render/ 的凍結範圍無關。
"""
import argparse
import glob
import json
import os
import sys

import yaml

MODULES_DEFAULT = 'data/modules.yaml'
OUT_DEFAULT = 'work/data-review.html'


def load_modules(path):
    with open(path, encoding='utf-8') as f:
        mods = yaml.safe_load(f)
    return {m['id']: m for m in mods}


def resolve_pages(rec, mods):
    """回傳該筆資料對應的頁碼清單。優先用 pdf_page，否則由 scope 推。"""
    if rec.get('pdf_pages'):
        return list(rec['pdf_pages'])
    if rec.get('pdf_page'):
        return [rec['pdf_page']]
    m = mods.get(str(rec.get('scope', '')))
    if m:
        return list(m.get('io_summary_pages') or [])
    return []


def build(paths, mods_path, out):
    mods = load_modules(mods_path)
    recs = []
    for p in paths:
        with open(p, encoding='utf-8') as f:
            data = yaml.safe_load(f) or []
        for r in data:
            pages = resolve_pages(r, mods)
            scope = str(r.get('scope', ''))
            m = mods.get(scope)
            recs.append({
                'id': r.get('key') or r.get('id') or '',
                'scope': scope,
                'scope_name': (m or {}).get('name_en', ''),
                'latex': r.get('latex', ''),
                'name': r.get('name_en') or r.get('text', {}).get('en', '') if isinstance(r.get('text'), dict) else r.get('name_en', ''),
                'units': r.get('units', ''),
                'status': r.get('status', ''),
                'notes': r.get('notes', ''),
                'issues': [{'kind': i.get('kind', ''), 'note': i.get('note', '')}
                           for i in (r.get('issues') or [])],
                'pages': pages,
                'src': os.path.basename(p),
            })

    html = TEMPLATE.replace('__RECS__', json.dumps(recs, ensure_ascii=False))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(html)

    scopes = sorted({r['scope'] for r in recs}, key=lambda s: (len(s), s))
    kinds = {}
    for r in recs:
        for i in r['issues']:
            kinds[i['kind']] = kinds.get(i['kind'], 0) + 1
    print(f'{out}　{len(recs)} 筆　{len(html)/1024:.0f} KB')
    print(f'scope：{", ".join(scopes)}')
    print(f'issues：{kinds or "無"}')
    print('以瀏覽器開啟（file:// 可用；KaTeX 由 CDN 載入，需連線）')


TEMPLATE = r"""<!doctype html>
<meta charset="utf-8">
<title>CR-166536 資料比對</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<style>
  :root { --bg:#2e2e2e; --panel:#1f1f1f; --line:#3a3a3a; --ink:#e8e8e8; --dim:#9a9a9a;
          --accent:#4aa3d0; --warn:#e0a030; --bad:#e06666; }
  * { box-sizing:border-box; }
  body { margin:0; height:100vh; display:flex; background:var(--bg); color:var(--ink);
         font:13px/1.5 system-ui,"Segoe UI",sans-serif; overflow:hidden; }

  #left { width:46%; min-width:420px; display:flex; flex-direction:column;
          background:var(--panel); border-right:1px solid #000; }
  #bar { padding:8px 10px; border-bottom:1px solid var(--line); display:flex;
         gap:6px; flex-wrap:wrap; align-items:center; }
  #bar select, #bar input { background:#111; color:var(--ink); border:1px solid #555;
                            border-radius:4px; padding:3px 6px; font:inherit; }
  #bar input { flex:1; min-width:120px; }
  #count { color:var(--dim); font-size:12px; }

  #list { overflow-y:auto; flex:1; }
  #foot { padding:7px 10px; border-top:1px solid var(--line); display:flex; gap:6px;
          align-items:center; flex-wrap:wrap; }
  #foot input { flex:1; min-width:110px; background:#111; color:var(--ink);
                border:1px solid #555; border-radius:4px; padding:3px 6px; font:inherit; }
  .rec .mk { font-weight:bold; margin-right:4px; }
  .rec .mk.ok { color:#5c9; }
  .rec .mk.bad { color:var(--bad); }
  .rec { padding:7px 10px; border-bottom:1px solid var(--line); cursor:pointer; }
  .rec:hover { background:#272727; }
  .rec.cur { background:#123away; background:#12354a; }
  .rec .top { display:flex; gap:8px; align-items:baseline; }
  .rec .k { font-family:ui-monospace,Consolas,monospace; color:var(--accent); }
  .rec .tex { margin-left:auto; background:#fff; color:#000; padding:1px 6px;
              border-radius:3px; }
  .rec .nm { color:var(--dim); font-size:12px; margin-top:2px; }
  .rec .meta { font-size:11px; color:#777; margin-top:2px; }
  .tag { border-radius:3px; padding:0 5px; font-size:11px; margin-right:4px; }
  .tag.ocr_uncertain { background:#5a4510; color:#ffd782; }
  .tag.suspected_typo { background:#5a2a10; color:#ffb782; }
  .tag.schema_gap { background:#4a1030; color:#ff9ad0; }
  .tag.sc { background:#333; color:#bbb; }
  .note { font-size:11px; color:#c9a; margin-top:3px; white-space:pre-wrap; }

  #right { flex:1; display:flex; flex-direction:column; min-width:0; }
  #rbar { padding:8px 12px; background:var(--panel); border-bottom:1px solid #000;
          display:flex; gap:10px; align-items:center; }
  #rbar b { font-size:15px; }
  #view { flex:1; overflow:auto; display:flex; justify-content:center;
          align-items:flex-start; padding:8px; background:#3a3a3a; }
  #view img { background:#fff; box-shadow:0 2px 12px #0008; }
  #view.fit img { max-height:calc(100vh - 110px); width:auto; }
  #view.full img { width:auto; height:auto; max-width:none; }
  button { background:#444; color:var(--ink); border:1px solid #666; border-radius:4px;
           padding:3px 9px; cursor:pointer; font:inherit; }
  button:hover { background:#555; }
  button:disabled { opacity:.35; cursor:default; }
  kbd { background:#111; border:1px solid #555; border-radius:3px; padding:0 4px; font-size:11px; }
</style>

<div id="left">
  <div id="bar">
    <select id="fscope"></select>
    <select id="fissue">
      <option value="">全部</option>
      <option value="*">僅有 issues</option>
      <option value="ocr_uncertain">ocr_uncertain</option>
      <option value="suspected_typo">suspected_typo</option>
      <option value="schema_gap">schema_gap</option>
    </select>
    <input id="q" placeholder="搜尋 key／描述">
    <span id="count"></span>
  </div>
  <div id="list"></div>
  <div id="foot">
    <button onclick="mark('ok')">✓ 與原件相符 <kbd>o</kbd></button>
    <button onclick="mark('bad')">✗ 有問題 <kbd>x</kbd></button>
    <button onclick="mark(null)">清除 <kbd>c</kbd></button>
    <input id="rnote" placeholder="覆核備註（自動儲存）">
    <button onclick="exportJSON()">匯出</button>
    <label style="cursor:pointer;padding:3px 6px">匯入<input type="file" id="imp" hidden accept=".json"></label>
    <span id="prog" style="color:var(--dim)"></span>
  </div>
</div>

<div id="right">
  <div id="rbar">
    <b id="ptitle">—</b>
    <span id="pinfo" style="color:var(--dim)"></span>
    <span style="margin-left:auto"></span>
    <button id="prev">← 前頁</button>
    <button id="next">後頁 →</button>
    <button onclick="zoom()">縮放 <kbd>z</kbd></button>
    <span style="color:var(--dim);font-size:11px">滾輪翻頁</span>
  </div>
  <div id="view" class="fit"><img id="img" alt=""></div>
</div>

<script>
const RECS = __RECS__;
const $ = id => document.getElementById(id);
const pad = n => String(n).padStart(3,'0');
let view = [], cur = 0, pageIdx = 0, curPage = null;

// scope 下拉
{
  const order = [...new Set(RECS.map(r=>r.scope))].sort((a,b)=>a.length-b.length||a.localeCompare(b));
  $('fscope').innerHTML = '<option value="">全部 scope</option>' +
    order.map(s=>{
      const n = RECS.filter(r=>r.scope===s).length;
      const nm = (RECS.find(r=>r.scope===s)||{}).scope_name||'';
      return `<option value="${s}">${s} — ${nm.slice(0,28)} (${n})</option>`;
    }).join('');
}

function tex(el, s){
  if(!s){ el.textContent=''; return; }
  try { katex.render(s, el, {throwOnError:false, displayMode:false}); }
  catch(e){ el.textContent = s; }
}

function filter(){
  const sc = $('fscope').value, is = $('fissue').value, q = $('q').value.trim().toLowerCase();
  view = RECS.filter(r =>
    (!sc || r.scope===sc) &&
    (!is || (is==='*' ? r.issues.length : r.issues.some(i=>i.kind===is))) &&
    (!q || r.id.toLowerCase().includes(q) || (r.name||'').toLowerCase().includes(q)));
  render();
}

function render(){
  $('count').textContent = `${view.length} / ${RECS.length}`;
  $('list').innerHTML = view.map((r,i)=>`
    <div class="rec" data-i="${i}">
      <div class="top">
        <span class="mk" id="mk${i}"></span>
        <span class="k">${r.id}</span>
        <span class="tag sc">${r.scope}</span>
        <span class="tex" id="tex${i}"></span>
      </div>
      <div class="nm">${(r.name||'').replace(/</g,'&lt;')}</div>
      <div class="meta">${r.units?`units ${r.units}　`:''}${r.status||''}　<span style="color:#666">${r.src}</span>
        ${r.issues.map(x=>`<span class="tag ${x.kind}">${x.kind}</span>`).join('')}</div>
      ${r.issues.map(x=>`<div class="note">${(x.note||'').replace(/</g,'&lt;')}</div>`).join('')}
      ${r.notes?`<div class="note" style="color:#8aa">${r.notes.replace(/</g,'&lt;')}</div>`:''}
    </div>`).join('');
  view.forEach((r,i)=>{ tex($('tex'+i), r.latex); refreshMark(i); });
  progress();
  if(view.length) go(0);
  else { $('img').removeAttribute('src'); $('ptitle').textContent='—'; $('pinfo').textContent=''; }
}

function go(i){
  cur = Math.max(0, Math.min(view.length-1, i));
  // 目前顯示的頁若仍落在新符號的頁範圍內就留著——依序覆核時不必每筆重新翻頁。
  const ps = view[cur] ? view[cur].pages : [];
  const keep = ps.indexOf(curPage);
  pageIdx = keep >= 0 ? keep : 0;
  document.querySelectorAll('.rec.cur').forEach(e=>e.classList.remove('cur'));
  const el = document.querySelector(`.rec[data-i="${cur}"]`);
  if(el){ el.classList.add('cur'); el.scrollIntoView({block:'nearest'}); }
  const r = view[cur];
  $('rnote').value = (r && marks[mkey(r)]?.note) || '';
  showPage();
}

function showPage(){
  const r = view[cur]; if(!r) return;
  const ps = r.pages;
  if(!ps.length){ $('img').removeAttribute('src'); curPage = null;
                  $('ptitle').textContent = r.id;
                  $('pinfo').textContent = '（無對應頁碼）'; return; }
  const p = ps[Math.max(0,Math.min(ps.length-1,pageIdx))];
  curPage = p;
  $('img').src = `../scans/p${pad(p)}.webp`;
  $('ptitle').textContent = `pdf ${p}`;
  $('pinfo').textContent = `${r.id}　scope ${r.scope}　第 ${pageIdx+1}/${ps.length} 頁`;
  $('prev').disabled = pageIdx<=0;
  $('next').disabled = pageIdx>=ps.length-1;
  [pageIdx-1,pageIdx+1].forEach(j=>{ if(ps[j]) new Image().src=`../scans/p${pad(ps[j])}.webp`; });
}

// ── 覆核標記 ───────────────────────────────────────────────
// 標記存於 localStorage，匯出檔才是產物；localStorage 隨時可能被清掉。
// 鍵為 scope + key，跨 scope 的同名符號不會互相覆蓋。
const MK = 'gtrs-data-review';
let marks = {};
try { marks = JSON.parse(localStorage.getItem(MK) || '{}'); } catch(e) { marks = {}; }
const mkey = r => r.scope + '::' + r.id;
const save = () => { try { localStorage.setItem(MK, JSON.stringify(marks)); } catch(e) {} };

function refreshMark(i){
  const r = view[i]; if(!r) return;
  const m = marks[mkey(r)], el = $('mk'+i); if(!el) return;
  el.textContent = m && m.v ? (m.v==='ok' ? '✓' : '✗') : '';
  el.className = 'mk ' + (m && m.v ? m.v : '');
}
function progress(){
  const done = RECS.filter(r=>marks[mkey(r)]?.v).length;
  const bad  = RECS.filter(r=>marks[mkey(r)]?.v==='bad').length;
  $('prog').textContent = `已覆核 ${done}/${RECS.length}　有問題 ${bad}`;
}
function mark(v){
  const r = view[cur]; if(!r) return;
  const k = mkey(r);
  if(v === null) delete marks[k];
  else marks[k] = {v, note: $('rnote').value, at: new Date().toISOString()};
  save(); refreshMark(cur); progress();
  if(v) go(cur+1);
}
$('rnote').oninput = () => {
  const r = view[cur]; if(!r) return;
  const k = mkey(r);
  marks[k] = Object.assign({v:null}, marks[k], {note: $('rnote').value});
  save();
};
function exportJSON(){
  const rows = RECS.filter(r=>marks[mkey(r)]).map(r=>Object.assign(
    {scope:r.scope, key:r.id, src:r.src}, marks[mkey(r)]));
  const b = new Blob([JSON.stringify(rows,null,1)], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(b);
  a.download = 'data-review.json';
  a.click();
}
$('imp').onchange = e => {
  const f = e.target.files[0]; if(!f) return;
  f.text().then(t=>{
    JSON.parse(t).forEach(x=>{ marks[x.scope+'::'+x.key] = {v:x.v, note:x.note, at:x.at}; });
    save(); view.forEach((_,i)=>refreshMark(i)); progress();
  });
};

// 滾輪翻頁。放大模式下滾輪要用來捲動影像，故僅在 fit 模式生效。
$('view').addEventListener('wheel', e => {
  if(!$('view').classList.contains('fit')) return;   // 放大中：交給瀏覽器捲動
  e.preventDefault();
  const step = e.deltaY > 0 ? 1 : -1;
  const ps = view[cur] ? view[cur].pages : [];
  const nxt = pageIdx + step;
  if(nxt >= 0 && nxt < ps.length){ pageIdx = nxt; showPage(); }
}, {passive:false});

$('list').onclick = e => { const d=e.target.closest('[data-i]'); if(d) go(+d.dataset.i); };
$('prev').onclick = () => { pageIdx--; showPage(); };
$('next').onclick = () => { pageIdx++; showPage(); };
$('fscope').onchange = $('fissue').onchange = filter;
$('q').oninput = filter;
function zoom(){ $('view').classList.toggle('fit'); $('view').classList.toggle('full'); }

addEventListener('keydown', e=>{
  if(e.target.tagName==='INPUT'){ if(e.key==='Escape') e.target.blur(); return; }
  if(e.key==='ArrowDown'){ go(cur+1); e.preventDefault(); }
  else if(e.key==='ArrowUp'){ go(cur-1); e.preventDefault(); }
  else if(e.key==='ArrowRight'){ if(!$('next').disabled){ pageIdx++; showPage(); } }
  else if(e.key==='ArrowLeft'){ if(!$('prev').disabled){ pageIdx--; showPage(); } }
  else if(e.key==='z') zoom();
  else if(e.key==='o') mark('ok');
  else if(e.key==='x') mark('bad');
  else if(e.key==='c') mark(null);
  else if(e.key==='n'){ $('rnote').focus(); e.preventDefault(); }
  else if(e.key==='/'){ $('q').focus(); e.preventDefault(); }
});

filter();
</script>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+', help='YAML 檔（可用 glob）')
    ap.add_argument('--modules', default=MODULES_DEFAULT)
    ap.add_argument('--out', default=OUT_DEFAULT)
    a = ap.parse_args()
    files = []
    for p in a.paths:
        files.extend(sorted(glob.glob(p)) or [p])
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        sys.exit('找不到任何 YAML 檔')
    build(files, a.modules, a.out)


if __name__ == '__main__':
    main()
