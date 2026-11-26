# Upstream feature parity

| 機能 | 状態 | 証拠・残り |
|---|---|---|
| 原典制作ルール・jfig | 移植 | 原典ハッシュ一致。未接続部品は個別に検証 |
| Petrol/Paper | HTML接続 | 5種類×2テーマの固定HTMLでpixel差0 |
| 全5テンプレート・表紙/裏表紙/章扉/stage | 固定HTML実装 | 48ページ×2テーマ=96/96ピクセル完全一致。JSONスロット/図解差し替え。任意ページ追加・並び替え未対応 |
| 原典の描画回帰 | 96/96 | [CI 45887002218](https://github.com/yu37330/ai-slide-engine/actions/runs/45887002218/job/140140082103)、固定カタログの独立再比較を必須化 |
| AWS公式アイコン | オフライン対応 | [CI 45887094180](https://github.com/yu37330/ai-slide-engine/actions/runs/45887094180/job/140140390630)：公式ZIP 1852点、S3/Bedrock/Lambda、Paper色保持。素材の同梱なし |
| SVG→PPTX native | 基本検証済み | 旧画像埋込はfallback。Office実描画・全テンプレートのPPTX比較は未検証 |
| DOM/SVG QA | 実装 | 元の検査と範囲外geometry。原典作例にも警告はあり得る |
| フォント | 原典ハッシュ検査 | 素材は配布せず利用者が明示供給。代替時のpixel同一性は未確認 |
| SVG Editor・差分同期・履歴 | 未 | PPT編集からJSONへの自動反映は未実装 |
| Copilot Skills | ZIP実装 | テナント実行・契約/クレジットは未確認 |
