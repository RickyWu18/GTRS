/* 公式渲染　—— 渲染層（凍結）
 *
 * 依據：計畫書 4.2 約束二、5.3.2　│　工項：WBS W2.7
 *
 * 對外介面：renderEquation(eq) → HTMLElement
 *
 * 約束二：本檔不得寫入任何版面相關的 CSS class 或容器結構。
 * 由外殼層決定置於何處、如何排列。
 *
 * 須支援 kind 之四種值：single | piecewise | system | definition
 * latex 永遠是一條完整可渲染的字串，渲染層只吃這個欄位。
 */

export function renderEquation(/* eq */) {
  throw new Error('未實作：WBS W2.7');
}
