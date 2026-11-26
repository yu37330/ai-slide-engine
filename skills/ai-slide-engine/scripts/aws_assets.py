"""AWS公式配布ZIPの明示的なオフライン取込み。外部ネットワーク・再配布なし。"""
import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

import jfig

SVG="{http://www.w3.org/2000/svg}"
TAGS={"svg","title","desc","g","path","rect","circle","ellipse","line","polyline","polygon",
      "defs","linearGradient","radialGradient","stop","clipPath","mask","use","symbol","style"}
MAX_PACKAGE=300*1024*1024
MAX_SVG=1024*1024
def check(ok,msg):
    if not ok:
        raise ValueError(msg)
def digest(data):
    return hashlib.sha256(data).hexdigest()
def valid_source(url):
    p=urlsplit(url)
    return p.scheme=="https" and p.hostname and p.hostname.endswith(".awsstatic.com") and not p.username and not p.password and not p.port and p.path.lower().endswith(".zip")
def local_ref(s):
    return bool(re.fullmatch(r"#[A-Za-z0-9_.:-]+",s))
def safe_css(s):
    check(not re.search(r"@|javascript\s*:|expression\s*\(|-moz-binding|behavior\s*:|\\",s,re.I),"unsafe SVG CSS")
    for m in re.finditer(r"url\s*\(\s*([^)]*)\)",s,re.I):
        check(local_ref(m.group(1).strip().strip("'\"")),"external SVG CSS URL")
def safe_svg(raw):
    check(len(raw)<=MAX_SVG and not re.search(rb"<!DOCTYPE|<!ENTITY",raw,re.I),"unsafe SVG XML")
    root=ET.fromstring(raw)
    check(root.tag==SVG+"svg" and root.get("viewBox"),"SVG namespace/viewBox required")
    vals=re.split(r"[\s,]+",root.get("viewBox").strip())
    check(len(vals)==4 and all(re.fullmatch(r"-?\d+(?:\.\d+)?",x) for x in vals) and float(vals[2])>0 and float(vals[3])>0,"invalid viewBox")
    for e in root.iter():
        check(e.tag.startswith(SVG) and e.tag[len(SVG):] in TAGS,"unsupported SVG element: "+e.tag)
        for k,v in e.attrib.items():
            name=k.rsplit("}",1)[-1].lower()
            check(not name.startswith("on") and name not in {"base","src"},"unsafe SVG attribute")
            if name=="href": check(local_ref(v),"external SVG reference")
            if name=="style" or "url" in v.lower(): safe_css(v)
            check(not re.search(r"javascript\s*:",v,re.I),"unsafe SVG URI")
        if e.tag==SVG+"style": safe_css(e.text or "")
    return root
def import_zip(archive,cache,source,expected):
    archive,cache=Path(archive),Path(cache)
    check(valid_source(source),"use the AWS official https://*.awsstatic.com/...zip URL")
    check(re.fullmatch(r"[0-9a-fA-F]{64}",expected),"expected SHA256 required")
    check(archive.stat().st_size<=MAX_PACKAGE,"archive too large")
    package_hash=digest(archive.read_bytes())
    check(package_hash==expected.lower(),"package SHA256 mismatch")
    check(not cache.exists(),"cache must be new (immutable import)")
    cache.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache.parent) as temp:
        stage=Path(temp)/"cache"; icons=stage/"icons";icons.mkdir(parents=True)
        index=[];rejected=[];seen=set();total=0
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                rel=PurePosixPath(info.filename)
                if info.is_dir() or rel.suffix.lower()!=".svg" or "__MACOSX" in rel.parts or rel.name.startswith("."): continue
                check(not rel.is_absolute() and ".." not in rel.parts and "\\" not in info.filename and ":" not in info.filename,"unsafe ZIP path")
                check(info.filename not in seen,"duplicate ZIP path");seen.add(info.filename)
                check((info.external_attr>>16)&0o170000!=0o120000,"ZIP symlink")
                total+=info.file_size
                check(total<=MAX_PACKAGE and info.file_size<=MAX_SVG,"SVG archive limits exceeded")
                raw=z.read(info)
                try:
                    safe_svg(raw)
                    # 原典jfigのSVG読込み仕様に適合するファイルだけを登録する。
                    check(b'viewBox="' in raw,"original jfig requires a quoted viewBox")
                except (ValueError,ET.ParseError) as exc:
                    rejected.append({"path":info.filename,"reason":str(exc)});continue
                kind=next((k for prefix,k in [("Architecture-Service-Icons","service"),("Resource-Icons","resource"),("Architecture-Group-Icons","group"),("Category-Icons","category")] if any(p.startswith(prefix) for p in rel.parts)), "other")
                dest=icons.joinpath(*rel.parts);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
                index.append({"key":rel.stem,"file":rel.as_posix(),"kind":kind,"sha256":digest(raw)})
        check(index,"no safe SVG files")
        index.sort(key=lambda e:(e["key"],e["file"]))
        (icons/"index.json").write_text(json.dumps(index,ensure_ascii=True),encoding="utf-8")
        report={"source":source,"package_sha256":package_hash,"count":len(index),"rejected_count":len(rejected),"rejected":rejected}
        (stage/"current.json").write_text(json.dumps(report,ensure_ascii=True,indent=2),encoding="utf-8")
        shutil.move(str(stage),str(cache))
    return report
def configure(cache):
    """キャッシュの出典・全登録ファイルの整合性を確認して原典jfigへ渡す。"""
    root=Path(cache).resolve()
    report=json.loads((root/"current.json").read_text(encoding="utf-8"))
    check(valid_source(report["source"]) and re.fullmatch(r"[a-f0-9]{64}",report["package_sha256"]),"invalid cache provenance")
    icons=(root/"icons").resolve()
    index=json.loads((icons/"index.json").read_text(encoding="utf-8"))
    check(len(index)==report["count"] and len(index)>0,"index count mismatch")
    for e in index:
        path=(icons/e["file"]).resolve()
        check(path.is_relative_to(icons) and path.is_file() and digest(path.read_bytes())==e["sha256"],"icon content mismatch")
    jfig._AWS=(icons,index)
    return report
def require_icon(name):
    check(jfig._AWS is not None,"official AWS icon cache must be explicitly configured")
    # あいまいな検索では別のサービスのアイコンを使わない。
    exact=[e for e in jfig._AWS[1] if e["key"]==name]
    check(len(exact)==1,"use an exact unique icon key from aws_assets.py find")
    p=jfig.aws_path(name)
    safe_svg(p.read_bytes())
    return p
def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="command",required=True)
    a=sub.add_parser("import");a.add_argument("archive",type=Path);a.add_argument("cache",type=Path);a.add_argument("--source",required=True);a.add_argument("--sha256",required=True)
    f=sub.add_parser("find");f.add_argument("cache",type=Path);f.add_argument("words",nargs="+")
    a=p.parse_args()
    if a.command=="import": print(json.dumps(import_zip(a.archive,a.cache,a.source,a.sha256),ensure_ascii=False))
    else:
        configure(a.cache);words=[jfig._norm(w) for w in a.words]
        hits=[e for e in jfig._AWS[1] if all(w in jfig._norm(e["key"]) for w in words)]
        print(json.dumps([{k:e[k] for k in ("key","kind","sha256")} for e in hits[:100]],ensure_ascii=False,indent=2))
if __name__=="__main__":main()
