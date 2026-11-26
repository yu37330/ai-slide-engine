"""個人用Copilot Chatの公開対応形式から、原典のリソースを復元する。
ネットワーク接続・依存導入・組織の制限の回避は行わない。
"""
import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ALLOWED={".md",".txt",".json",".py",".js",".mjs"}
CSS={"html/themes/paper.css","html/themes/petrol.css"}
CAT="templates/catalog.zip"
CAT_JSON="templates/catalog.json"
MANIFEST="package-manifest.json"
MAX_FILE=8*1024*1024
MAX_TOTAL=32*1024*1024

def require(ok,message):
    if not ok:raise ValueError(message)
def sha(data):
    return hashlib.sha256(data).hexdigest()
def safe_name(name):
    require(isinstance(name,str) and re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*",name)
            and all(x not in (".","..") for x in name.split("/")),"unsafe relative path")
    return name
def read_local(root,name):
    safe_name(name)
    p=(root/name).resolve(strict=True)
    require(p.is_relative_to(root) and p.is_file(),"resource outside skill root")
    require(p.stat().st_size<=MAX_FILE,"resource too large")
    return p.read_bytes()
def catalog_member(name):
    return name=="catalog.json" or bool(re.fullmatch(r"(lightning|release|talk|update|webinar)-(petrol|paper)/(body\.html|theme\.css|index\.json|figs/[A-Za-z0-9_-]+\.svg)",name))
def restore_catalog(raw,out):
    """可読JSON内の公開テンプレートデータだけを復元する。ZIPメタデータは比較対象外。"""
    doc=json.loads(raw)
    require(set(doc)=={"version","members"} and doc["version"]==1 and isinstance(doc["members"],dict),"invalid catalog JSON")
    members=doc["members"]
    require(1<=len(members)<=250 and "catalog.json" in members,"invalid catalog member count")
    total=0
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,row in sorted(members.items()):
            require(catalog_member(safe_name(name)),"unsupported catalog member")
            require(isinstance(row,dict) and set(row)=={"sha256","text"} and isinstance(row["text"],str),"invalid catalog resource")
            data=row["text"].encode("utf-8");total+=len(data)
            require(len(data)<=MAX_FILE and total<=MAX_TOTAL and sha(data)==row["sha256"],"catalog resource integrity failure: "+name)
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data)
    with zipfile.ZipFile(out) as z:
        require(z.testzip() is None,"catalog CRC")
        for name in z.namelist():
            require(sha(z.read(name))==members[name]["sha256"],"restored catalog integrity failure")
        meta=json.loads(z.read("catalog.json"))
        expected={n+"-"+t for n in ("lightning","release","talk","update","webinar") for t in ("petrol","paper")}
        require({v["key"] for v in meta["variants"]}==expected and len(meta["variants"])==10
                and sum(v["pages"] for v in meta["variants"])==96,"catalog variant/page count mismatch")
        for key in expected:
            require(all(key+"/"+x in members for x in ("body.html","theme.css","index.json")),"catalog variant incomplete")
    return len(members)
def restore(source,destination):
    source=Path(source).resolve(strict=True);dest=Path(destination).resolve()
    require(source.is_dir() and source!=dest and not dest.is_relative_to(source),"use a new workspace outside the uploaded skill")
    require(not dest.exists() and dest.parent.is_dir(),"workspace must be new and parent must exist")
    manifest=json.loads(read_local(source,MANIFEST))
    require(set(manifest)=={"version","files","catalog_payload_only"} and manifest["version"]==1
            and manifest["catalog_payload_only"] is True,"invalid package manifest")
    rows=manifest["files"];require(isinstance(rows,list) and 1<=len(rows)<=100,"invalid manifest count")
    source_names=set();target_names=set();total=0;catalog_count=0
    with tempfile.TemporaryDirectory(prefix=".copilot-restore-",dir=dest.parent) as temp:
        stage=Path(temp)/"workspace";stage.mkdir()
        for row in rows:
            require(isinstance(row,dict) and set(row)=={"source","target","kind","sha256"},"invalid file descriptor")
            src=safe_name(row["source"]);target=safe_name(row["target"])
            require(src not in source_names and target not in target_names,"duplicate file mapping")
            source_names.add(src);target_names.add(target)
            require(PurePosixPath(src).suffix in ALLOWED and src!=MANIFEST,"unsupported uploaded file")
            kind=row["kind"];raw=read_local(source,src);total+=len(raw)
            require(total<=MAX_TOTAL and sha(raw)==row["sha256"],"resource integrity failure: "+src)
            p=stage/target;p.parent.mkdir(parents=True,exist_ok=True)
            if kind=="copy":
                require(src==target and PurePosixPath(target).suffix in ALLOWED,"invalid copy mapping")
                p.write_bytes(raw)
            elif kind=="css":
                require(target in CSS and src==target+".txt","invalid CSS mapping")
                raw.decode("utf-8");p.write_bytes(raw)
            elif kind=="catalog":
                require(src==CAT_JSON and target==CAT,"invalid catalog mapping")
                catalog_count=restore_catalog(raw,p)
            else:raise ValueError("unsupported resource kind")
        require({"SKILL.md",CAT,*CSS,"scripts/build.py","scripts/render_html.py",
                 "scripts/template_render.py","html/native.mjs","scripts/runtime_probe.mjs"}<=target_names,"incomplete restored engine")
        require(catalog_count>0,"catalog missing")
        # 入力や既存成果物を上書きしない。
        require(not dest.exists(),"workspace appeared during restore")
        shutil.move(str(stage),str(dest))
    return {"status":"RESTORED","files":len(rows),"catalog_members":catalog_count,
            "workspace":str(dest),"integrity":"SHA256_PASS","tenant":"NOT_TESTED"}
def probe(root):
    root=Path(root).resolve(strict=True)
    report={"python":sys.version.split()[0],"python_modules":{},"tools":{},
            "node_browser":{"status":"NOT_RUN"},"native_ready":False,"tenant":"NOT_TESTED","billing":"NOT_TESTED"}
    for name in ("pptx","PIL","numpy","cairosvg"):
        report["python_modules"][name]=importlib.util.find_spec(name) is not None
    for name in ("node","inkscape","soffice","pdftoppm"):
        report["tools"][name]=bool(shutil.which(name))
    if report["tools"]["node"]:
        try:
            r=subprocess.run([shutil.which("node"),str(root/"scripts/runtime_probe.mjs")],cwd=root,
                             capture_output=True,text=True,timeout=45)
            report["node_browser"]=json.loads(r.stdout)
            report["native_ready"]=r.returncode==0 and report["node_browser"].get("status")=="READY"
        except (OSError,ValueError,subprocess.TimeoutExpired) as e:
            report["node_browser"]={"status":"BLOCKED","reason":str(e)[:300]}
    report["svg_html_ready"]=all((root/n).is_file() for n in (CAT,*CSS,"scripts/build.py","scripts/render_html.py"))
    report["fallback_ready"]=report["python_modules"]["pptx"] and (report["tools"]["inkscape"] or report["python_modules"]["cairosvg"])
    report["pptx_review_ready"]=all(report["python_modules"][n] for n in ("PIL","numpy")) and report["tools"]["soffice"] and report["tools"]["pdftoppm"]
    return report
def main():
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path);p.add_argument("workspace",type=Path)
    p.add_argument("--restore-only",action="store_true",help="復元のみ。ブラウザや他プロセスは起動しない")
    a=p.parse_args()
    try:
        result=restore(a.source,a.workspace)
        if not a.restore_only:
            result["runtime"]=probe(a.workspace)
            (a.workspace/"runtime-report.json").write_text(json.dumps(result["runtime"],ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception as e:
        p.exit(1,"RESTORE_BLOCKED: "+str(e)+"\n")
if __name__=="__main__":main()
