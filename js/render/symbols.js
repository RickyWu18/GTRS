/* 符號提示與交叉追溯（F1、F2）　—— 渲染層（凍結）
 *
 * 依據：計畫書 6.1 F1/F2、5.4.1　│　工項：WBS W2.1（路徑驗證）、W2.8（實作）
 *
 * F1 為最高優先功能，其價值超過其餘所有功能總和。
 *
 * 實作路徑：來源字串標註（不是渲染後掃描 DOM）
 *   1. 以 symbols.yaml 之 latex 欄位建立比對表，依長度由長至短排序
 *   2. 對公式 latex 字串做最長匹配取代，包成 \htmlData{sym=C_T}{C_T}
 *   3. 交由 KaTeX 渲染（需開啟 trust 選項以允許 \htmlData）
 *   4. 渲染結果中帶 data-sym 屬性的元素即為互動掛載點
 *
 * 兩處陷阱：取代時必須避開巨集名稱（\rho 中的 rho）與 \text{} 內容。
 * 作法為先以正規表示式切出巨集與文字區塊加以保護，僅對其餘部分取代。
 *
 * scope 解析順序：公式所屬 module 的 scope → scope: global → 視為未定義並報錯
 */

export function annotateSymbols(/* latex, symbolTable */) {
  throw new Error('未實作：WBS W2.1');
}
