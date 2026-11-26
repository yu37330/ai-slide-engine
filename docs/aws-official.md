# AWS公式アイコン
[公式配布ページ](https://aws.amazon.com/architecture/icons/)から利用者自身が取得する。アイコン集は再配布しない。ZIPの取得元とSHA256を記録してからオフライン取込み。Copilot内部のスクリプトはネット接続せず、承認済みキャッシュを参照する。

```sh
python skills/ai-slide-engine/scripts/aws_assets.py import Icon-package.zip aws-cache --source 'https://d1.awsstatic.com/.../Icon-package_....zip' --sha256 '取得したZIPのSHA256'
python skills/ai-slide-engine/scripts/aws_assets.py find aws-cache s3
python skills/ai-slide-engine/scripts/render_html.py deck.json output --aws-cache aws-cache
```
JSON: component=aws, args=[x,y,公式indexの一意なkey,ラベル], kwargs={size:64}。frameのawsも同じkey。曖昧な名前・未設定・改変キャッシュは拒否。公式原本は色・形・縦横比を変更せずjfigに渡す。SVGの危険な要素/外部参照は除外し、取り込めなかった件数と理由を記録。原典と同じdata-fixed-colorをPaperでも維持する。自作ロゴへの自動代替は禁止。
