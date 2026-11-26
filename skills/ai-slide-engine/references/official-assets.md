# Approved asset workflow
## 原典テンプレート優先
5種類の原典（lightning/release/talk/update/webinar）×Petrol/Paperの固定HTMLカタログ `templates/catalog.zip` を使う。本番でMarpを動かさない。ユーザーの目的に合う雛形を選ぶ。
- `python scripts/template_render.py list` / `python scripts/template_render.py inspect update petrol` でスライドの構造・スロットID・SVG寸法を確認。
- `python scripts/template_render.py spec update petrol deck-template.json` でJSONを作る。slotsの文章を編集し、title/authorはメタデータも更新。事実はsourcesとclaimsへ。既存SVGはfiguresのasset pathをキーにし、原典viewBoxと同じwidth/height/alt/operationsで作り直す。表紙・裏表紙の共通の透明SVGはcover_art（title, operations）を原典のcard/block/bar/link/dotで作る。原典のCSS・構造をAIが自由に変更しない。
- `python scripts/template_render.py render deck-template.json output` → `node html/native.mjs output`。approved fontを利用できる場合は --fonts で原典と同じハッシュの3ファイルを指示する。フォントは同梱しない。原典5×2テーマ96ページについて同一Chromium・同一フォント条件でpixel差0を検証したが、新規内容・Office描画・フォント代替まで保証しない。
- AWS構成図では公式の配布ZIPを利用者が明示的に渡す。 `python scripts/aws_assets.py import ICON.zip aws-cache --source URL --sha256 SHA256`、 `python scripts/aws_assets.py find aws-cache bedrock`、JSONのcomponent=aws、args=[x,y,公式の一意なkey,表示ラベル]、kwargs={size:64}。renderに --aws-cache aws-cache を付ける。配布ZIP・フォント・会社データは外部送信/再配布しない。AWS名を推測せず、公式アイコンの色・形を変えない。未提供時は正式サービス名の箱にして代替を明記。
- 原典の全ページ構成を固定するため、任意のページ追加/並べ替えは未対応。必要な場合は次の汎用HTML経路。テンプレートの原典サンプル文や図を新しい事実として使わない。


