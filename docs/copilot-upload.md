# Microsoft 365 Copilot Chat 専用ZIP

通常の開発・ローカル用 `releases/ai-slide-engine.zip` と、個人用Chat Skillの登録専用 `releases/ai-slide-engine-copilot.zip` を区別する。後者は Microsoft Learn の公開対応形式（MD/TXT/JSON/PY/JS/MJS）だけで構成する。CSSはUTF-8テキスト、原典カタログは各メンバーの可読テキストとSHA256からなるJSON。内部ZIPをそのまま隠して送ることはしない。復元後のカタログは圧縮形式・メタデータが変わる可能性があるが、全メンバーの内容は同じ。AWS素材、フォント、会社データ、資格情報、node_modulesは同梱しない。

## 使用方法
1. Copilot Premiumと組織の利用許可を確認。Agents > More agents > Add > Upload skill で専用ZIPを登録する。情報バリア等の制約がある場合は管理者に確認し、迂回しない。
2. スキルを明示選択し、アップロードしたファイルの存在を確認する。SKILL.mdに従い `python scripts/bootstrap_copilot.py <skill-root> <new-workspace>` を実行。復元時にSHA256・固定パス・ファイル数等を検査する。workspaceは書き込み可能で未作成の別フォルダを指定する。
3. runtime-report.jsonで native_ready を確認。Node/JSZip/PptxGenJS/Playwright/Chromiumが実際に利用可能な場合のみネイティブ経路へ進む。未確認・不足時はJSON/SVG/HTMLの許可された範囲のみ返し、追加インストールや課金モードを自動選択しない。明示希望時のみ旧PPTX画像埋込を別経路として利用。
4. 最初に合成サンプルで検証。会社の資料は管理者承認と契約・情報管理要件確認後に使用。

## 確認範囲
公式対応拡張子の検査、復元後の原典ファイル内容一致、全カタログメンバーの一致、復元版の描画/PPTX回帰をCIで実施。個人Chat Skillのファイル数/サイズの具体的なホスト上限は公式ページでは未確認。実テナントのアップロード、ライブラリ、PowerPoint実機、課金、npm High脆弱性2件は別課題。SHA256は転送・復元時の整合性確認であり、信頼済み配布元と企業のセキュリティ検査の代わりではない。

公式: https://learn.microsoft.com/en-us/plugins/build-copilot-chat-skills
実行環境: https://learn.microsoft.com/en-us/plugins/declarative-agent-skills
