# PowerPoint 描画回帰（#9）

原典5テンプレート×2テーマの全96ページについて、独立した固定上流Marp→PPTXと、現在のJSON→HTML→PPTXを比較する。PPTXは同一LibreOffice/Popplerで1280×720へ再描画。上流のフォントをCIにのみインストールし、同一条件を保つ。比較対象は原典の公開サンプルだけ。フォント、会社データ、PDF、PPTXは配布しない。

- HTMLと新PPTX: 絶対差。RGBの差分pixel数、32超の差分pixel数、MAE (0–255)、明度8×8非重複ブロックSSIMを測る。
- HTMLと元PPTX: 原典変換自体の差を測る。
- 元PPTXと新PPTX: 移植差を測る。
- OOXML: XML構文、CRC、ページ数、16:9、図形ID、参照先、画像だけのページ、ネイティブ図形/文字run/表/画像/グループ、正規化テキスト、変換座標を検査。
- 回帰ゲート: 全96ページの出力、構造・編集性の数と文字保持、各ページのMAEが原典より0.1/255超悪化しない、SSIM8が0.001超悪化しない。相対pixel差0と絶対pixel差0は別々に記録し、許容差合格を完全同一とは呼ばない。元の品質検査で停止したケースも失敗として計上する。
- 実機Officeのレンダラーとは異なる。実際のOfficeでの編集・再描画は未確認。

利用者の許可済み実行環境にLibreOffice、Poppler、numpy、Pillowが既にあれば、生成済みPPTXとHTMLのpagesフォルダを使って `python scripts/pptx_render_review.py output/deck-native.pptx output/pages output/pptx-review` で測定できる。未導入なら自動導入せず未実査とする。
