/* 全文檢索（F4）
 *
 * 依據：計畫書 6.1 F4、7.1　│　工項：WBS W2.10
 *
 * 單頁應用採 hash 路由時，瀏覽器原生 Ctrl+F 僅能搜尋當前渲染內容，
 * 故站內檢索是必要功能而非加分項。
 *
 * 索引由離線腳本（tools/）產生為 generated/search-index.json 並 commit，
 * 前端只負責載入既成索引，不於瀏覽器端重建。索引須同時涵蓋中英兩種敘述欄位。
 */

export function search(/* query */) {
  throw new Error('未實作：WBS W2.10');
}
