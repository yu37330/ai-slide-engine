# Upstream feature parity / 初期段階

| 機能 | 状態 | 検証・次の実装 |
|---|---|---|
| ストーリー・日本語・図選択・配色・アップデート型 | 継承 | 原典参照・Copilot指示 |
| jfigの共通部品 | 原典移植 | JSON allowlist経由。AWSアイコンは未移植 |
| JSON正本・出典ID・SVG | MVP | 基本構造とページ比率、基本座標を検査 |
| CSSのPetrol/Paper | 原典保管 | 新PPTXテーマは簡易Petrol。全レイアウト/表紙移植は未 |
| PPTX出力・編集 | MVP | SVG原本埋込・PNG fallback。上流のSVG内部ネイティブDrawingML変換は未接続 |
| 表・本文・発表者ノート | MVP | レイアウトは簡易版 |
| SVG Editor・差分保存・履歴・プレゼンビュー | 未 | PowerPoint標準機能で部分代替、JSONへの反映は手動 |
| slides check・PPTX描画・見切れ/衝突・contact sheet | 部分 | 上流検査コードは参照保存。実描画と全要素衝突は未実装 |
| テーマ切替・全テンプレート・ギャラリー | 未 | 公開作例は上流URL参照。画像・フォント権利を確認して再構成 |
| Copilot Chatの個人Skills ZIP | 実装 | ZIP構造とローカル同等テスト、テナント登録は未 |
| Copilot in PowerPoint | 指示Skill | 別製品の実行環境と管理者設定。登録・編集は未検証 |
| クレジット | 未確認 | 実契約・利用モード・費用表示を確認。自動課金への切替は禁止 |

次: 1) JSON Schema厳格化・図形交差/全パスの検査・実レンダリング比較 2) 元のPPTX scene/DrawingMLへの変換アダプター 3) テンプレート・テーマ・編集差分同期 4) Copilot実テナント検証。
