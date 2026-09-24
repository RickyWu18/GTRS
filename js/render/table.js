/* 資料表渲染　—— 渲染層（凍結介面）
 *
 * 依據：計畫書 5.6.1、6.2 F8　│　工項：WBS W2.x、W5.4
 *
 * 資料為 tables/*.csv 加上同名 *.meta.yaml（欄位意義、單位、來源頁碼）。
 * 日後增加排序與繪圖能力（F8）不違反凍結——它不要求任何 YAML 回填。
 */

export function renderTable(/* table, meta */) {
  throw new Error('未實作');
}
