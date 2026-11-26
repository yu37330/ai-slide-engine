# 原典テンプレート回帰
固定上流 b5814e92b1c4bcc6d78f1c357ebe05de9030f5e2 の lightning/release/talk/update/webinar をPetrol/Paper両方でコンパイルする。開発時のコンパイルにのみMarpを使う。HTML DOMのテキストノードをJSONスロットへ変換し、原典の全レイアウト、表紙・裏表紙、章扉、stage、表、対話、箇条書き、コードブロックとSVG資産を固定カタログに保持。フォントは同梱しない。原典と同じハッシュのフォントを利用者が用意した場合のみピクセル同等性を検証できる。

```sh
python skills/ai-slide-engine/scripts/template_render.py list
python skills/ai-slide-engine/scripts/template_render.py spec update petrol deck-template.json
# JSONのslotsを編集（原典の構造は維持）。cover_artで表裏の透明SVGを原典部品から生成可能。
python skills/ai-slide-engine/scripts/template_render.py render deck-template.json output --fonts /approved/fonts
node skills/ai-slide-engine/html/native.mjs output
```

比較は同一Chromium 1280x720、同一フォント・SVG・テーマ。原典は毎回別にMarpで生成し、候補はチェックイン済みcatalogからPythonで作る。全ページで差分pixel数0をゲートにする。新規の文章・図・レイアウトやOffice実機についての完全同一性を保証するものではない。固定テンプレートは構造を保持して編集するため、任意のページ追加や自由なレイアウト変更には別経路が必要。原典作例の警告・構成比は別途レビューする。
