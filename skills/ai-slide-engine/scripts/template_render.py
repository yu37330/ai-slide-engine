"""固定HTMLテンプレートをJSONで編集する。本番ではMarp不要。"""
import argparse
import hashlib
import html
import inspect
import json
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
import cover_art
from build import argsafe, figure_svg, svg_check
from figure_palette import adaptive_svg
from aws_assets import configure
from visual_assets import load_assets
ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/"templates"/"catalog.zip"
NAMES=("lightning","release","talk","update","webinar")
THEMES=("petrol","paper")
SHELL="html,body{margin:0;padding:0;background:#888}\nsvg[data-marpit-svg]{display:block;width:1280px;height:720px;margin:0 0 8px}"
def need(ok,msg):
    if not ok: raise ValueError(msg)
def read(z,name):
    return z.read(name)
def data(z,name):
    return json.loads(read(z,name))
def variant(z,name,theme):
    need(name in NAMES and theme in THEMES,"unknown template/theme")
    key=name+"-"+theme
    idx=data(z,key+"/index.json")
    need(idx["key"]==key,"catalog mismatch")
    return key,idx
def asset_canvas(raw):
    original=ET.fromstring(raw)
    vb=[float(v) for v in re.split(r"[\s,]+",original.get("viewBox","").strip())]
    need(len(vb)==4 and vb[0]==0 and vb[1]==0 and all(x.is_integer() and 0<x<=2400 for x in vb[2:]),"template asset has unsupported custom canvas")
    return tuple(int(x) for x in vb[2:])
def inspect_template(z,name,theme):
    key,idx=variant(z,name,theme)
    result=dict(idx)
    result["canvases"]={}
    for asset in idx["assets"]:
        try: result["canvases"][asset]=list(asset_canvas(read(z,key+"/"+asset)))
        except ValueError: result["canvases"][asset]=None
    return result
def spec(z,name,theme):
    key,idx=variant(z,name,theme)
    return {"version":1,"template":name,"theme":theme,"title":idx["title"],"author":idx["author"],
            "slots":{k:v["default"] for k,v in idx["slots"].items()},"notes":{},"sources":[],"claims":{},"figures":{}}
def cover_svg(cfg,out):
    need(isinstance(cfg,dict) and set(cfg)=={"title","operations"},"invalid cover art")
    allowed={"card","block","bar","link","dot"}
    parts=[]
    for op in cfg["operations"]:
        need(isinstance(op,dict) and set(op)<= {"component","args","kwargs"} and {"component","args"}<=set(op),"invalid operation")
        name=op["component"];need(name in allowed,"unsupported cover component")
        args,kwargs=op["args"],op.get("kwargs",{})
        for v in [*args,*kwargs.values()]: argsafe(v)
        fn=getattr(cover_art,name);inspect.signature(fn).bind(*args,**kwargs)
        parts.append(fn(*args,**kwargs))
    cover_art.save(out,cfg["title"],parts)
    raw=out.read_text(encoding="utf-8");svg_check(raw,560,720)
    return raw.encode()
def render(catalog,config,out,fonts=None,assets_dir=None):
    out=Path(out)
    need(not out.exists() or (out.is_dir() and not any(out.iterdir())),"output must be new or empty")
    need(isinstance(config,dict) and config.get("version")==1 and set(config)<={"version","template","theme","title","author","slots","notes","sources","claims","figures","cover_art","assets"},"invalid template spec")
    approved=load_assets(config.get("assets",[]),assets_dir)
    with zipfile.ZipFile(catalog) as z:
        cat=data(z,"catalog.json")
        key,idx=variant(z,config["template"],config["theme"])
        title=config.get("title",idx["title"]);author=config.get("author",idx["author"])
        need(isinstance(title,str) and title.strip() and isinstance(author,str) and author.strip(),"invalid title or author")
        supplied=config.get("slots",{})
        need(isinstance(supplied,dict) and set(supplied)<=set(idx["slots"]) and all(isinstance(x,str) and len(x)<=8000 for x in supplied.values()),"invalid slot")
        values={k:supplied.get(k,v["default"]) for k,v in idx["slots"].items()}
        if author!=idx["author"]:
            for k,v in idx["slots"].items():
                if k not in supplied and v["role"]=="author":
                    values[k]=values[k].replace(idx["author"],author)
        body=read(z,key+"/body.html").decode()
        # 一度の置換だけにし、挿入されたテキストをHTML/スロットとして再解釈しない。
        body=re.sub(r"__JINNO_(S\d{5})__",lambda m:html.escape(values[m[1]],quote=False),body)
        css=read(z,key+"/theme.css").decode()
        need(not re.search(r"data:font/",css,re.I),"catalog must not contain font files")
        assets=idx["assets"];overrides=config.get("figures",{})
        need(isinstance(overrides,dict) and set(overrides)<=set(assets),"unknown figure asset")
        sources=config.get("sources",[]);notes=config.get("notes",{});claims=config.get("claims",{})
        ids=[s["id"] for s in idx["slides"]]
        need(isinstance(notes,dict) and set(notes)<=set(ids) and all(isinstance(x,str) for x in notes.values()),"invalid notes")
        need(isinstance(claims,dict) and set(claims)<=set(ids),"unknown claim slide")
        source_ids=set()
        for s in sources:
            need(isinstance(s,dict) and set(s)=={"id","label","locator"} and all(isinstance(v,str) and v.strip() for v in s.values()) and s["id"] not in source_ids,"invalid source")
            source_ids.add(s["id"])
        deck_slides=[]
        for i,s in enumerate(idx["slides"]):
            c=claims.get(s["id"],{"status":"illustrative","source_ids":[]})
            need(isinstance(c,dict) and set(c)=={"status","source_ids"} and c["status"] in ("factual","illustrative","none") and isinstance(c["source_ids"],list) and set(c["source_ids"])<=source_ids and (c["status"]!="factual" or c["source_ids"]),"invalid claim")
            note=notes.get(s["id"],"\n".join(idx["comments"][i] or []) if i<len(idx["comments"]) else "")
            deck_slides.append({"id":s["id"],"kind":s["kind"],"title":"".join(values[k] for k in s["slots"] if idx["slots"][k]["role"]=="title"),"lead":"".join(values[k] for k in s["slots"] if idx["slots"][k]["role"]=="lead"),"notes":note,"claim_status":c["status"],"source_ids":c["source_ids"],"images":s["images"]})
        out.mkdir(parents=True,exist_ok=True)
        asset_names=["deck.html","theme.css"]
        for name in assets:
            need(re.fullmatch(r"figs/[A-Za-z0-9_-]+\.svg",name),"unsafe template asset")
            raw=read(z,key+"/"+name)
            if name in overrides:
                raw=figure_svg(overrides[name],canvas=asset_canvas(raw),assets=approved).encode("utf-8")
            p=out/name;p.parent.mkdir(parents=True,exist_ok=True)
            if name=="figs/cover-art.svg" and "cover_art" in config:
                need(name not in overrides,"cover art and figure override conflict")
                raw=cover_svg(config["cover_art"],p)
            if config["theme"]=="paper" and (name in overrides or (name=="figs/cover-art.svg" and "cover_art" in config)):
                raw=adaptive_svg(raw)
            p.write_bytes(raw);asset_names.append(name)
        if fonts:
            fontdir=out/"themes/assets";fontdir.mkdir(parents=True)
            for name,digest in cat["fonts"].items():
                need(re.fullmatch(r"NotoSansJP-(?:Book450|Bold|Regular)\.woff2",name),"unexpected font")
                raw=(Path(fonts)/name).read_bytes()
                need(hashlib.sha256(raw).hexdigest()==digest,"original font SHA256 mismatch: "+name)
                (fontdir/name).write_bytes(raw);asset_names.append("themes/assets/"+name)
        (out/"theme.css").write_text(css,encoding="utf-8")
        (out/"deck.html").write_text('<!doctype html><html><head><meta charset="utf-8"><title>'+html.escape(title)+'</title><link rel="stylesheet" href="theme.css"><style>'+SHELL+'</style></head><body>'+body+'</body></html>',encoding="utf-8")
        deck={"version":2,"title":title,"author":author,"sources":sources,"slides":deck_slides,"assets":config.get("assets",[])}
        manifest={"version":2,"template":key,"theme":config["theme"],"font_mode":"approved_assets" if fonts else "system_fallback_unverified","slides":ids,"assets":asset_names,"upstream":cat["upstream"]}
        for name,obj in (("deck.json",deck),("manifest.json",manifest),("template-spec.json",config)):
            (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return manifest
def main():
    p=argparse.ArgumentParser();p.add_argument("--catalog",type=Path,default=CATALOG);sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("list")
    i=sub.add_parser("inspect");i.add_argument("template",choices=NAMES);i.add_argument("theme",choices=THEMES)
    s=sub.add_parser("spec");s.add_argument("template",choices=NAMES);s.add_argument("theme",choices=THEMES);s.add_argument("output",type=Path)
    b=sub.add_parser("render");b.add_argument("spec",type=Path);b.add_argument("output",type=Path);b.add_argument("--fonts",type=Path);b.add_argument("--aws-cache",type=Path);b.add_argument("--assets-dir",type=Path)
    a=p.parse_args()
    if a.command in ("list","spec","inspect"):
        with zipfile.ZipFile(a.catalog) as z:
            if a.command=="list":print(json.dumps(data(z,"catalog.json")["variants"],ensure_ascii=False,indent=2))
            elif a.command=="inspect":print(json.dumps(inspect_template(z,a.template,a.theme),ensure_ascii=False,indent=2))
            else:a.output.write_text(json.dumps(spec(z,a.template,a.theme),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    else:
        if a.aws_cache:configure(a.aws_cache)
        print(json.dumps(render(a.catalog,json.loads(a.spec.read_text(encoding="utf-8")),a.output,a.fonts,a.assets_dir),ensure_ascii=False,indent=2))
if __name__=="__main__":main()
