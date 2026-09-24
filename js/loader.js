/* YAML 載入與快取
 *
 * 依據：計畫書 4.3、4.2 約束三　│　工項：WBS W2.6
 *
 * 約束三（凍結範圍）：載入 YAML 時遇到 schema 未定義的欄位，一律靜默略過，
 * 不得報錯或中止。此規則使「日後新增選填欄位」永遠不構成破壞性變更。
 */

export function loadYaml(/* path */) {
  throw new Error('未實作：WBS W2.6');
}
