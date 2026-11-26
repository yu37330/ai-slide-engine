"""承認済みローカル画像の検証と、再描画しないSVGへの配置。通信なし。"""
import base64
import hashlib
import html
import io
import math
import re
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET
from aws_assets import safe_css

NS="{http://www.w3.org/2000/svg}"
MAX_BYTES=8*1024*1024
MAX_TOTAL=24*1024*1024
TAGS={"svg","title","desc","g","path","rect","circle","ellipse","line","polyline","polygon",
      "defs","marker","linearGradient","radialGradient","stop","clipPath","mask","use","symbol",
      "text","tspan","style","pattern"}
RIGHTS={"owned","licensed","public_domain","generated"}
MIME={".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",".svg":"image/svg+xml"}
def need(ok,msg):
    if not ok: raise ValueError(msg)
def num(v):
    need(type(v) in (int,float) and math.isfinite(v) and abs(v)<=100000,"invalid number")
    return v
def svg_source(raw):
    need(not re.search(rb"<!DOCTYPE|<!ENTITY|<\?(?!xml\s)",raw,re.I),"unsafe SVG document")
    root=ET.fromstring(raw)
    need(root.tag==NS+"svg","SVG root required")
    vb=[float(v) for v in re.split(r"[\s,]+",root.get("viewBox","").strip())]
    need(len(vb)==4 and all(math.isfinite(v) for v in vb) and 0<vb[2]<=10000 and 0<vb[3]<=10000,"invalid SVG viewBox")
    ids=set()
    for e in root.iter():
        need(e.tag.startswith(NS) and e.tag[len(NS):] in TAGS,"unsupported imported SVG element")
        if "id" in e.attrib:
            need(e.get("id") not in ids,"duplicate SVG ID")
            ids.add(e.get("id"))
        for k,v in e.attrib.items():
            name=k.rsplit("}",1)[-1].lower()
            need(not name.startswith("on") and name not in {"base","src"},"unsafe SVG attribute")
            if name=="href": need(re.fullmatch(r"#[A-Za-z0-9_.:-]+",v),"external SVG reference")
            if name=="style" or "url" in v.lower(): safe_css(v)
            need(not re.search(r"javascript\s*:",v,re.I),"unsafe URI")
        if e.tag==NS+"style": safe_css(e.text or "")
    return vb[2],vb[3]
def load_assets(entries, directory):
    need(isinstance(entries,list) and len(entries)<=100,"assets must be an array")
    if not entries: return {}
    need(directory is not None,"--assets-dir required for approved local assets")
    root=Path(directory).resolve(strict=True)
    need(root.is_dir(),"assets directory required")
    result={};total=0
    for item in entries:
        need(isinstance(item,dict) and set(item)=={"id","file","sha256","source","rights"},"asset fields: id,file,sha256,source,rights")
        key=item["id"];name=item["file"]
        need(isinstance(key,str) and re.fullmatch(r"[A-Za-z0-9_-]+",key) and key not in result,"invalid asset id")
        need(isinstance(name,str) and re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*",name),"relative asset path required")
        rel=PurePosixPath(name)
        need(not rel.is_absolute() and all(x not in (".","..") for x in name.split("/")) and rel.suffix.lower() in MIME,"invalid asset path/type")
        need(isinstance(item["source"],str) and item["source"].strip() and item["rights"] in RIGHTS,"explicit source and user-declared rights required")
        need(isinstance(item["sha256"],str) and re.fullmatch(r"[a-fA-F0-9]{64}",item["sha256"]),"expected SHA256 required")
        p=root.joinpath(*rel.parts).resolve(strict=True)
        need(p.is_relative_to(root) and p.is_file(),"asset outside approved directory")
        size=p.stat().st_size
        total+=size
        need(0<size<=MAX_BYTES and total<=MAX_TOTAL,"asset size limit exceeded")
        raw=p.read_bytes()
        need(hashlib.sha256(raw).hexdigest()==item["sha256"].lower(),"asset SHA256 mismatch")
        mime=MIME[rel.suffix.lower()]
        if mime=="image/svg+xml":
            w,h=svg_source(raw)
        else:
            from PIL import Image
            with Image.open(io.BytesIO(raw)) as im:
                need(im.format==("PNG" if mime=="image/png" else "JPEG"),"image content/type mismatch")
                w,h=im.size
                need(0<w<=10000 and 0<h<=10000 and w*h<=25000000 and getattr(im,"n_frames",1)==1,"unsupported image dimensions/animation")
                im.verify()
        uri="data:"+mime+";base64,"+base64.b64encode(raw).decode("ascii")
        result[key]={"uri":uri,"width":w,"height":h,"mime":mime}
    return result
def image_fragment(assets,x,y,w,h,asset,fit="contain"):
    need(isinstance(asset,str) and asset in assets,"unknown approved asset")
    x,y,w,h=map(num,(x,y,w,h))
    need(x>=0 and y>=0 and w>0 and h>0 and fit in ("contain","cover"),"invalid image geometry/fit")
    par="xMidYMid meet" if fit=="contain" else "xMidYMid slice"
    return (f'<image x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" '
            f'preserveAspectRatio="{par}" data-fixed-color="" href="{assets[asset]["uri"]}"/>')
def free_path(d,fill="none",stroke="#545b64",sw=1.6):
    need(isinstance(d,str) and re.fullmatch(r"[MmLlHhVvCcSsQqTtAaZz0-9eE+.,\s-]+",d) and re.match(r"^\s*[Mm]",d),"invalid SVG path")
    for c in (fill,stroke):
        need(isinstance(c,str) and re.fullmatch(r"#[0-9a-fA-F]{3,8}|[A-Za-z]+",c),"invalid path color")
    need(0<=num(sw)<=100,"invalid stroke width")
    return f'<path d="{html.escape(d,quote=True)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw:g}"/>'
