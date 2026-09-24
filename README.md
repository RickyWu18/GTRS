# GTRS — NASA CR-166536 數位化

將 NASA CR-166536《A Mathematical Model for Real Time Flight Simulation of a
Generic Tilt-Rotor Aircraft》（Ferguson, 1988）由掃描 PDF 轉為**可全文檢索、
可交叉追溯**的靜態網站。

原始文件為 1988 年產出的掃描影像，約 300 餘頁、逾 30 MB、無文字層。三個實際障礙：
符號在前段定義而在後段使用、公式無法複製或交叉連結、模組耦合關係隱含於各章敘述之中。
本專案的目標是消除這些查閱摩擦，使讀者能有效率地**理解**此數學模型。

## 專案狀態

**初始化中。** 目錄骨架已建立，內容尚未開始轉錄。

進度請見 `docs/CR-166536-WBS-checklist.md`。

## 明確排除

- **不實作模擬器**——不產出 MATLAB/Simulink 或 Python 可執行模型
- **不進行數值驗證**——由於不實作模擬器，無法以配平計算反向驗證轉錄正確性
- **不重新推導或修正原文**——原文若有錯漏，以 `issues` 標記，不逕行更改

原文本身缺乏完整推導描述且部分變數定義不清（見 McVicar 1993），故「讀懂模型」的
上限不由數位化品質決定。原文未交代之處會被系統性標記而非默默略過——這份
「原文哪裡講不清楚」的清單在原始 PDF 中並不存在。

## 架構

核心決策是**內容與呈現解耦**：

```
掃描頁 ──OCR/轉錄──▶ 結構化資料層 ──▶ ┌─ 靜態網站
                        (YAML/CSV)      ├─ 相依關係圖（自動生成）
                                        └─ 全文檢索索引（自動生成）
```

渲染層寫一次即凍結，之後所有內容工作僅為向 `data/` 新增檔案。解耦後，任何時間點
停工，已完成部分皆為可用成品。

純前端，無建置流程：YAML 於瀏覽器端以 js-yaml 解析，新增一章內容直接 commit 即生效。
`generated/` 下的檢索索引與檢查結果由 CI 重建，貢獻者無須感知其存在。

## 目錄結構

| 路徑 | 內容 |
|---|---|
| `data/` | 結構化資料：公式、符號、常數、模組、覆蓋率台帳 |
| `js/render/` | **渲染層（凍結）**——變更需回頭修改全部 YAML |
| `js/app.js`, `js/home.js` | 外殼層——首頁與版面，隨時可重寫 |
| `css/tokens.css` | 設計代幣，視覺調整不觸及結構 |
| `scans/` | 逐頁 WebP 影像（Git LFS） |
| `notes/` | 中文譯註，與原文嚴格分離 |
| `generated/` | 離線腳本產出，經 CI 重建後 commit |
| `tools/` | 離線工具鏈（Python）：OCR 管線、檢查腳本、索引產生 |
| `docs/` | 專案計畫書與 WBS 檢核清單 |

原始 PDF 與掃描灰階母本**不在此 repo 內**（見 `.gitignore`），位置記於
`data/meta.yaml` 的 `scan_spec.master_location`。

## 技術選型

原生 ES modules（不使用框架）、KaTeX（數學排版）、js-yaml、MiniSearch（檢索）、
Cytoscape.js（相依圖）、GitHub Pages 經 Actions 部署。

## 授權

程式碼採 MIT（見 `LICENSE`）。

`data/`、`scans/`、`notes/` 為 NASA CR-166536 之轉錄與衍生內容。NASA Contractor
Report 一般標示為 "Work of the US Gov. Public Use Permitted."，惟本報告係由 Bell
Helicopter 承包商人員撰寫，**實際授權標示待查驗**（WBS W0.2）。查驗結論將回填
`data/meta.yaml` 之 `license` 區塊並更新本節，在此之前不以通則推定。

## 參考文件

| 編號 | 標題 | 用途 |
|---|---|---|
| CR-166536 | A Mathematical Model for Real Time Flight Simulation of a Generic Tilt-Rotor Aircraft (Ferguson, 1988) | 本專案標的 |
| CR-166535 | Generic Tilt-Rotor Simulation User's and Programmer's Guide (Hanson & Ferguson, 1988) | 副程式架構、COMMON block 變數 |
| CR-166537 | Development and Validation of a Simulation for a Generic Tilt-Rotor Aircraft (Ferguson, 1989) | 驗證資料與背景 |
| CR-114614 | V/STOL Tilt Rotor Study, Vol. V (Harendra et al., 1973) | 前代模型 |
| — | A Generic Tilt-Rotor Simulation Model with Parallel Implementation (McVicar, Glasgow, 1993) | 後續實作者之獨立詮釋 |
