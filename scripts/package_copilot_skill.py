"""個人用Chat Skillの対応拡張子だけのZIPを生成。原典コードは変更しない。"""
import argparse
import io
import json
import tempfile
import zipfile
from pathlib import Path
from package_skill import ROOT,package
from copilot_upload.bootstrap_copilot import ALLOWED,CSS,CAT,CAT_JSON,MANIFEST,catalog_member,sha

HERE=Path(__file__).resolve().parent
GUIDE="""## Copilot Chatでの初回セットアップ（登録専用ZIP）
CSSはUTF-8テキスト（*.css.txt）、テンプレートは各メンバーを読めるJSON（templates/catalog.json）で格納しています。公開資料由来のデータです。
- スクリプト実行とローカル作業フォルダ生成が組織のポリシー・契約で許可されていることを確認する。許可されない場合は停止。管理者設定や課金モードを回避しない。
- アップロード済みスキルの実際のルートと、書き込み可能な未作成の別フォルダを確認する。python scripts/bootstrap_copilot.py <skill-root> <new-workspace> を実行。workspaceの親フォルダは存在している必要がある。
- SHA256不一致・資産欠落時は停止し、再取得を案内する。以降のコマンドは復元したworkspaceを起点に実行。テンプレートの中身をモデルが再構築・省略しない。
- runtime-report.json の native_ready が true の場合にネイティブPPTX変換へ進む。falseなら理由を明示し、許可されたJSON/SVG/HTMLを返す。ユーザーの明示希望時だけ fallback_ready を確認して旧互換経路を使用する。同等品質とは報告しない。
- 追加依存導入、外部通信、外部AI API、従量課金モードへの自動切替は禁止。ランタイム診断は契約や課金の確認ではない。
- 初回は合成データ examples/sample.json で実行し、実際に生成・検査できたファイルと結果だけを返す。会社資料を投入するのは管理者承認と初回検証後。
"""
def encode_catalog(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=[n for n in z.namelist() if not n.endswith("/")]
        assert len(names)==len(set(names)) and z.testzip() is None
        members={}
        for name in sorted(names):
            assert catalog_member(name),name
            b=z.read(name)
            members[name]={"sha256":sha(b),"text":b.decode("utf-8")}
    return (json.dumps({"version":1,"members":members},ensure_ascii=False,separators=(",",":"))+"\n").encode("utf-8")
def make(output):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        canonical=package(Path(d)/"canonical.zip")
        with zipfile.ZipFile(canonical) as z:
            payload={n:z.read(n) for n in z.namelist()}
    title="# JSON / SVG first slide workflow"
    original=payload["SKILL.md"].decode("utf-8")
    assert original.count(title)==1
    payload["SKILL.md"]=original.replace(title,title+"\n\n"+GUIDE,1).encode("utf-8")
    assert len(payload["SKILL.md"].decode("utf-8"))<20000
    for name in ("bootstrap_copilot.py","runtime_probe.mjs"):
        payload["scripts/"+name]=(HERE/"copilot_upload"/name).read_text(encoding="utf-8").encode("utf-8")
    upload={};rows=[]
    for target,data in sorted(payload.items()):
        src=target;kind="copy"
        if target in CSS:src=target+".txt";kind="css";data.decode("utf-8")
        elif target==CAT:src=CAT_JSON;kind="catalog";data=encode_catalog(data)
        assert Path(src).suffix in ALLOWED and src not in upload,src
        upload[src]=data
        rows.append({"source":src,"target":target,"kind":kind,"sha256":sha(data)})
    upload[MANIFEST]=(json.dumps({"version":1,"files":rows,"catalog_payload_only":True},ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,raw in sorted(upload.items()):
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.create_system=0;info.external_attr=0o600<<16;info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,raw)
    print("COPILOT_UPLOAD_PACKAGE",json.dumps({"files":len(upload),"bytes":output.stat().st_size,"sha256":sha(output.read_bytes()),"extensions":sorted({Path(n).suffix for n in upload}),"catalog_json_bytes":len(upload[CAT_JSON])}))
    return output
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,default=ROOT/"dist/ai-slide-engine-copilot.zip")
    make(p.parse_args().output)
