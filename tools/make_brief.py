"""產生符號表轉錄的 subagent 指示（W2.3）

為什麼需要這支腳本
    指示裡的 key 命名規約是手抄的，已兩次與 data/symbols.yaml 的規約脫節：
    一次漏抄 \\hat（規則二），一次漏抄 \\Delta 元組（規則七），兩次都導致
    agent 把合規的寫法誤標為 schema_gap，事後得逐筆撤銷。

    本腳本直接自 data/symbols.yaml 讀出規約區塊、自 data/modules.yaml 讀出頁碼，
    兩者皆為單一事實來源，手抄環節消失。

用法
    python tools/make_brief.py 8a 8b 8c 8d          # 一個 agent 承接四章
    python tools/make_brief.py 11 15 16 --out work/brief.md

    產出直接貼進 Agent 工具的 prompt。
"""
import argparse
import re
import sys

import yaml

SYMBOLS = 'data/symbols.yaml'
MODULES = 'data/modules.yaml'

# 各 subsystem 的方框摘要頁數。來源：2026-09-25 以 tools/strip_sheet.py 將附錄 A
# 全 282 頁頁首條帶拼版逐頁目視判別（見 docs/W2.2-schema壓力測試.md 第 4 節）。
# io_summary_pages 的前 N 頁為方框頁，其餘為符號表頁。
BOXED = {'1': 2, '2': 1, '3': 1, '4': 4, '5': 2, '6': 2, '7A': 2, '7B': 1, '8a': 2,
         '8b': 1, '8c': 1, '8d': 1, '9': 1, '10a': 3, '10b': 1, '10c': 1, '10d': 1,
         '10e': 1, '10f': 1, '11': 2, '12': 2, '13': 2, '14': 3, '15': 1, '16': 2,
         '17': 1, '18': 2, '19': 1, '20': 2}


def convention_block(path):
    """自 symbols.yaml 檔首取出規約區塊，去掉註解符號後原樣輸出。"""
    txt = open(path, encoding='utf-8').read()
    start = txt.find('# ── 5.4.2 的補充規約')
    end = txt.find('# ──────', txt.find('# 未涵蓋的形式不得自行類推'))
    if start < 0 or end < 0:
        sys.exit('找不到 symbols.yaml 的規約區塊——檔首格式可能已變更')
    body = txt[start:end]
    lines = [re.sub(r'^# ?', '', l) for l in body.splitlines()]
    return '\n'.join(lines).rstrip()


def quoting_block(path):
    txt = open(path, encoding='utf-8').read()
    start = txt.find('# ── YAML 引號規約')
    end = txt.find('# ──────', start + 10)
    if start < 0:
        return ''
    return '\n'.join(re.sub(r'^# ?', '', l) for l in txt[start:end].splitlines()).rstrip()


def targets(ids, mods):
    rows = []
    for i in ids:
        m = mods.get(i)
        if not m:
            sys.exit(f'modules.yaml 沒有 subsystem {i}')
        io = m['io_summary_pages']
        nb = BOXED[i]
        boxed, table = io[:nb], io[nb:]
        rows.append((i, m['name_en'], boxed, table))
    return rows


TEMPLATE = """為 NASA CR-166536 數位化專案轉錄符號表。純轉錄，不做推導或補全。

## 環境
- 倉庫 `D:/Documents/github/rickywu18/GTRS`，所有指令在此執行
- Python `./.venv/Scripts/python.exe`（已裝 pillow、PyYAML）
- 掃描影像 `scans/pNNN.webp`，5088×6600 的 1-bit 影像

## 標的：{n} 個 subsystem，共 {pages} 個符號表頁

{table}

方框摘要頁只有 From/To Subsystem 與 Symbol、無描述與單位，**不轉錄**，但要讀來核對筆數。
符號表頁頁首為 `SUBSYSTEM NO. n: ...`，內文是 `Symbol | Description | Units` 三欄。

**不要碰 `data/symbols.yaml`。**

## ⚠ 做完一個 subsystem 就立刻寫檔

**不要等全部做完才一次寫出。** 本任務先前曾有 agent 因 API 用量上限中途被砍，
未寫檔者產出全部遺失。逐一寫檔可確保已完成的部分保得住。

## 讀影像
```
PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe -c "
from PIL import Image
im=Image.open('scans/p{first}.webp').convert('L'); w,h=im.size
im.crop((int(w*.06), int(h*.08), int(w*.95), int(h*.50))).save('work/w23/t.png')
"
```
再用 Read 讀 `work/w23/t.png`。

**每頁必須讀滿整個高度**（表格約在 y 0.08–0.92）。分三段並**刻意重疊**
（例如 0.06–0.40 / 0.37–0.68 / 0.65–0.95），確認段界的符號在相鄰兩段都出現。
**漏行是本任務最常見的錯誤。**

**完整性核對**：每章與其方框摘要頁的 Inputs/Outputs 清單比對筆數，結果寫進回報。

為節省用量：同一頁的分段裁切一次做完再逐一讀，不要反覆回頭放大。

## 最重要的兩條原則

**一、不做推論。判讀不確定就照原樣寫下並標記，不要依語意推斷「應該是什麼」。**

**本書字體的小寫 l 與數字 1 已實測確認無法區分。** 兩個 agent 各自以 5 倍放大逐像素
比對（主符號 vs 同列下標中確定的數字 1 vs 單位 `ft-lb` 中確定的字母 l），三者字形
完全相同：同樣的左上旗標、同樣的等寬底襯線。這是字體性質，不是個別字元漫漶。

因此遇到 l/1 **不要嘗試由字形判定，也不要依語意推斷**。照你採用的讀法寫下，
標 `ocr_uncertain`，並在 note 寫出另一種讀法。

**單位欄的 `lb`／`ft-lb`／`1/deg` 等受同一限制，但不要逐筆標記**——那會讓幾乎每筆
都帶標記而失去鑑別力。改在檔頭註解統一說明。這是本專案已定的作法：系統性、影響
全書的字形限制記檔頭；個別、可分辨的疑義才逐筆標。

原文疑似有誤時照抄，標 `suspected_typo`。**字形比對是證據，語意推斷不是。**

**二、規約未涵蓋的形式不得自行類推**，照實填占位 key 並標 `schema_gap`，
note 說明原文形式。**但先確認規約真的沒涵蓋**——以下規約為完整版，自
`data/symbols.yaml` 檔首直接取出，勿憑印象判斷。

## key 命名規約（完整，取自 data/symbols.yaml）

基本規則（計畫書 5.4.2）：一律採 LaTeX 風格，去除反斜線與大括號。
`C_T` -> `C_T`；`\\rho` -> `rho`；`\\Omega` -> `Omega`；`\\theta_{{75}}` -> `theta_75`；
多層下標以底線串接、順序照原文由左至右：`C_{{L_w}}` -> `C_L_w`；`V_\\infty` -> `V_inf`。
**大小寫具意義，不得正規化。禁止為消歧而造原文沒有的 key。**

{convention}

## YAML 引號規約

{quoting}

## 輸出格式

```yaml
- key: X_H
  scope: "{example_scope}"
  latex: 'X_H'
  name_en: Description 欄原文照抄
  units: 'lb'
  source: nomenclature
  status: draft
  notes: '原文以元組並列：(X,Y,Z)_H'
```

- `name_en` 照抄，不改寫不翻譯
- `units` 照抄；上標平方寫 `ft^2`；無因次原文常寫 `ND`
- 每筆都要有 `status: draft`
- 需要時加 `issues`（`kind` 限 `ocr_uncertain`／`suspected_typo`／`schema_gap`）
- 每個檔案開頭加註解：轉錄了哪幾頁、每頁幾列、展開後幾筆、l/1 字體限制的統一說明

## 回報

先對各檔跑 `yaml.safe_load` 確認可解析、key 無重複、`latex` 解析後與字面相同、
無控制字元。

回報要簡短：每個 subsystem 的頁數／原文列數／輸出筆數、與方框頁的核對結果、
各類 `issues` 的數量與清單、判讀不確定處。**不要把 YAML 內容貼回來。**
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ids', nargs='+', help='subsystem id，如 8a 8b 8c')
    ap.add_argument('--symbols', default=SYMBOLS)
    ap.add_argument('--modules', default=MODULES)
    ap.add_argument('--out')
    a = ap.parse_args()

    mods = {m['id']: m for m in yaml.safe_load(open(a.modules, encoding='utf-8'))}
    rows = targets(a.ids, mods)

    head = '| subsystem | 名稱 | 方框摘要頁（不轉錄，供核對） | **符號表頁（你的標的）** | 輸出檔 |\n'
    head += '|---|---|---|---|---|\n'
    for i, name, boxed, table in rows:
        b = '–'.join(map(str, [boxed[0], boxed[-1]])) if len(boxed) > 1 else str(boxed[0])
        t = '–'.join(map(str, [table[0], table[-1]])) if len(table) > 1 else str(table[0])
        head += f'| {i} | {name} | {b} | **{t}** | `work/w23/s{i}.yaml` |\n'
    head += '\n`scope` 分別為 ' + '、'.join(f'`"{i}"`' for i, *_ in rows) + '。'

    txt = TEMPLATE.format(
        n=len(rows),
        pages=sum(len(t) for *_, t in rows),
        table=head,
        first=f'{rows[0][3][0]:03d}',
        convention=convention_block(a.symbols),
        quoting=quoting_block(a.symbols),
        example_scope=rows[0][0],
    )

    if a.out:
        open(a.out, 'w', encoding='utf-8', newline='\n').write(txt)
        print(f'{a.out}　{len(txt)} 字元　{len(rows)} 章 / {sum(len(t) for *_, t in rows)} 頁')
    else:
        print(txt)


if __name__ == '__main__':
    main()
