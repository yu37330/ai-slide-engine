# ai-slide-engine

Microsoft 365 Copilot Chatでストーリー・JSON・SVGを作り、同じSkillsの実行環境でPPTXへ変換。PowerPoint Copilotで仕上げる。ローカルは同一コードの予備経路。**追加のAI APIを必要としない設計**（Microsoft 365側の利用料金・上限は実テナントで確認）。

Jinno Slide KitのMIT作図部品・制作ルール・描画/検査処理の参照実装を継承。Marpは実行要件から除外し、JSONを正本にする。

## Copilot 365
1. [Copilot登録用ZIP](https://github.com/yu37330/ai-slide-engine/raw/main/releases/ai-slide-engine.zip) を直接取得（または `python scripts/package_skill.py`）。Actions Artifact容量に依存しない。ZIPの中身とソースの一致をCIで確認する。
2. Microsoft 365 Copilot Chat（Premium・管理者設定による）の Agents > More agents > Upload skill から中身のZIPを登録。SKILL.mdがZIP直下にある。
3. Skillsを明示選択し「サンプルJSONからSVGとPPTXを生成して検査して」。スクリプトが実行できない、従量課金になる場合は自動で別モードへ切り替えない。
4. PPTXを開き、PowerPoint Copilotに `skills/ai-slide-finisher/SKILL.md` を別途登録できる環境では明示選択。図解を勝手に置き換えず仕上げる。
5. 変更点はJSONに反映し再生成。正本、SVG、PPTX、レビューを同時に保管。会社データは会社の許可された環境でのみ扱う。

## ローカル予備経路
Python 3.10+、python-pptx、InkscapeまたはCairoSVG。依存の導入はローカルで明示的に許可した場合のみ。
```sh
python -m pip install -r requirements-local.txt
python -m unittest discover -s tests -v
python skills/ai-slide-engine/scripts/build.py validate skills/ai-slide-engine/examples/sample.json
python skills/ai-slide-engine/scripts/build.py build skills/ai-slide-engine/examples/sample.json output
python scripts/package_skill.py
```
出力: JSON、SVG、PNGフォールバック、PPTX、HTMLプレビュー、review.json。タイトル、リード、表、ノートはネイティブ。図解はSVG埋め込み（PNG互換フォールバック）で内部図形のネイティブ編集は今後の課題。HTMLはPPTXの描画結果ではない。

## 現在の段階
MVP。実テナントのSkill登録・実行・課金・PowerPoint実画面は未確認。上流機能の同等性は[差分表](docs/parity.md)で管理。MIT著作権表記は[LICENSE](LICENSE)、[UPSTREAM.md](UPSTREAM.md)。

## Microsoft公式仕様
- https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/build-copilot-chat-skills
- https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/declarative-agent-skills
- https://support.microsoft.com/en-us/powerpoint/copilot/copilot-in-powerpoint-skills
