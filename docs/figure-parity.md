# SVG generation parity
原典のjfig.py/marks.py/cover_art.pyは変更しない。JSONディスパッチで原典部品を呼び出す。原典6デモを独立checkoutのPythonで実行し、トップレベル操作をJSON化して再生成する。全20のFigメソッド・facts/steps、旧marks、全線画アイコン、表紙5部品をPetrol/Paper双方で比較する。SVGのバイト一致とChromiumのRGBA pixel差0をゲートとする。AWSデモには公式ZIPを使用。原典にないpathおよび画像配置は別の新機能として検証する。

## 画像の配置
```json
{
  "assets": [{"id":"screen","file":"screen.png","sha256":"実際の64桁のハッシュ","source":"本人の画面キャプチャ","rights":"owned"}],
  "operations": [{"component":"image","args":[40,50,520,300,"screen"],"kwargs":{"fit":"contain"}}]
}
```
assetsはdeckまたはtemplate JSONのトップレベル、operationsはfigure内。PNG/JPEG/静的SVGを明示指定したルート内のローカルファイルから読み、SHA256、サイズ、実フォーマット、SVG安全性を検査する。権利は利用者の申告であり、実際の権利確認を代替しない。--assets-dir で入力フォルダを指定。SVGにdata URIとして埋め込む。技術図形はネイティブ変換、写真は画像のまま（ピクセルを編集可能な図形に変換する意味ではない）。CSPとオフライン制約を維持。任意のSVG機能のOffice再現性、GUI編集、自動画像生成、Copilotテナント、課金は未検証。
