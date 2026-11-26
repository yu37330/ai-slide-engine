"""JSONを正本にするCopilot Chat / ローカル共通エンジン。"""
import argparse
import hashlib
import html
import inspect
import json
import math
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from jfig import Fig, tw

OPS = {"T","R","C","L","A","icon","bubble","think","box","frame","card","tag",
       "head","num","ok","ng","warn","blocked","code"}
BODY = {"figure","text","table"}
KINDS = BODY | {"cover","section","closing"}
ID = re.compile(r"^[a-zA-Z0-9_-]+$")
COLOR = re.compile(r"^(#[0-9a-fA-F]{3,8}|[a-zA-Z]+)$")
NS = "{http://www.w3.org/2000/svg}"

def need(ok, message):
    if not ok:
        raise ValueError(message)

def fields(obj, required, optional=()):
    need(isinstance(obj,dict), "object required")
    need(set(required) <= obj.keys() <= set(required)|set(optional), "unexpected or missing fields")

def ident(s):
    need(isinstance(s,str) and ID.fullmatch(s), "invalid id")
    return s

def text(s, nonempty=False):
    need(isinstance(s,str) and (not nonempty or s.strip()), "invalid text")
    return s

def argsafe(v):
    if isinstance(v,(float,int)) and not isinstance(v,bool):
        need(math.isfinite(v) and abs(v)<=100000,"invalid number")
    elif isinstance(v,str):
        need(len(v)<=3000,"argument too long")
    elif isinstance(v,list):
        need(len(v)<=500,"array too long")
        for x in v: argsafe(x)
    else:
        need(v is None or isinstance(v,bool),"invalid argument")

def svg_check(svg,w,h):
    # 外部参照、コードの実行、基本図形の範囲外を拒否する。
    need("<!DOCTYPE" not in svg.upper() and "<!ENTITY" not in svg.upper(),"unsafe XML")
    root=ET.fromstring(svg)
    allowed={"svg","title","rect","text","tspan","circle","ellipse","g","path",
             "defs","marker","line","polyline","polygon"}
    def walk(e, transformed=False, definition=False):
        tag=e.tag.removeprefix(NS)
        need(e.tag.startswith(NS) and tag in allowed,"unsupported SVG element")
        for k,v in e.attrib.items():
            need(not k.lower().startswith("on") and "href" not in k.lower(),"unsafe attribute")
            need("url(" not in v or re.fullmatch(r"url\(#[a-zA-Z0-9_-]+\)",v),"external reference")
        transformed=transformed or "transform" in e.attrib
        definition=definition or tag in ("defs","marker")
        def n(k,d=0): return float(e.get(k,d))
        if not transformed and not definition:
            if tag=="rect":
                x,y,a,b=(n(k) for k in ("x","y","width","height"))
                need(x>=0 and y>=0 and a>=0 and b>=0 and x+a<=w+.01 and y+b<=h+.01,"rectangle outside canvas")
            elif tag=="circle":
                x,y,r=(n(k) for k in ("cx","cy","r"))
                need(r>=0 and x-r>=0 and y-r>=0 and x+r<=w and y+r<=h,"circle outside canvas")
            elif tag=="text":
                size=n("font-size")
                need(size>=16,"SVG text below 16 px")
                x,y=n("x"),n("y")
                for i,span in enumerate(list(e) or [e]):
                    if i: y+=float(span.get("dy","0"))
                    sx=float(span.get("x",x))
                    width=tw("".join(span.itertext()),size)
                    anchor=e.get("text-anchor","start")
                    left=sx-width/2 if anchor=="middle" else sx-width if anchor=="end" else sx
                    need(left>=-1 and left+width<=w+1 and y-size>=-2 and y+size*.25<=h+1,"text possibly outside canvas")
        for child in e: walk(child,transformed,definition)
    walk(root)

def figure_svg(fig):
    fields(fig,["width","height","alt","operations"])
    need(type(fig["width"]) is int and fig["width"]==1160 and type(fig["height"]) is int
         and 340<=fig["height"]<=420,"figure canvas must be 1160 x 340..420")
    f=Fig(fig["width"],fig["height"],title=text(fig["alt"],True))
    need(isinstance(fig["operations"],list) and 0<len(fig["operations"])<=300,"operations required")
    for op in fig["operations"]:
        fields(op,["component","args"],["kwargs"])
        name=op["component"]
        need(isinstance(name,str) and name in OPS,"unsupported component")
        a,k=op["args"],op.get("kwargs",{})
        need(isinstance(a,list) and isinstance(k,dict),"invalid args")
        for v in [*a,*k.values()]: argsafe(v)
        fn=getattr(f,name)
        p=inspect.signature(fn).bind(*a,**k).arguments
        need(not p.get("aws"),"offline official AWS assets not configured")
        for key in ("c","tc","fill","stroke"):
            if key in p and p[key] is not None:
                need(isinstance(p[key],str) and COLOR.fullmatch(p[key]),"invalid color")
        for key in ("z","sz","bz"):
            if p.get(key) is not None:
                need(type(p[key]) in (int,float) and p[key]>=16,"font size minimum 16 px")
        fn(*a,**k)
    result=f.svg()
    svg_check(result,fig["width"],fig["height"])
    return result

def validate(deck):
    fields(deck,["version","title","author","sources","slides"])
    need(type(deck["version"]) is int and deck["version"]==1,"version must be 1")
    text(deck["title"],True);text(deck["author"],True)
    need(isinstance(deck["sources"],list),"sources required")
    sources={}
    for src in deck["sources"]:
        fields(src,["id","label","locator"])
        sid=ident(src["id"])
        need(sid not in sources,"duplicate source")
        text(src["label"],True);text(src["locator"],True);sources[sid]=src
    need(isinstance(deck["slides"],list) and 0<len(deck["slides"])<=100,"slides required")
    seen=set();svgs={};body=figures=tables=0
    for s in deck["slides"]:
        fields(s,["id","kind","title","lead","claim_status","source_ids","notes"],["body","figure","table"])
        sid=ident(s["id"]);need(sid not in seen,"duplicate slide");seen.add(sid)
        kind=s["kind"];need(kind in KINDS,"unknown kind")
        title=text(s["title"],True);lead=text(s["lead"]);text(s["notes"])
        need(tw(title,40)<=1160 and tw(lead,25)<=1160 and "\n" not in title+lead,"title/lead too long")
        need("、" not in title,"title contains Japanese comma")
        need(s["claim_status"] in ("factual","illustrative","none"),"invalid claim status")
        ids=s["source_ids"]
        need(isinstance(ids,list) and all(isinstance(x,str) and x in sources for x in ids)
             and len(ids)==len(set(ids)),"unknown or duplicate source")
        need(s["claim_status"]!="factual" or ids,"factual slide needs source")
        if kind in BODY:
            body+=1;need(lead.strip() and s["claim_status"]!="none","body needs lead and claim status")
        payload=set(s)&{"figure","table","body"}
        if kind=="figure":
            need(payload=={"figure"},"figure slide requires figure only")
            svgs[sid]=figure_svg(s["figure"]);figures+=1
        elif kind=="table":
            need(payload=={"table"},"table slide requires table only")
            rows=s["table"]
            need(isinstance(rows,list) and 2<=len(rows)<=7 and isinstance(rows[0],list) and 1<=len(rows[0])<=5,"table size")
            need(all(isinstance(row,list) and len(row)==len(rows[0]) and
                     all(isinstance(c,str) and len(c)<=60 for c in row) for row in rows),"invalid rows")
            tables+=1
        elif kind=="text":
            need(payload=={"body"},"text slide requires body only")
            b=text(s["body"],True)
            need(len(b)<=260 and not any(re.match(r"^\s*([-*•]|\d+[.)])\s",x) for x in b.splitlines()),"no bullet-only slides")
        else: need(not payload,"cover/section/closing use title and lead")
    need(body>0 and figures*10>=body*6,"figure slides must be >=60% of body")
    need(tables*10<=body,"table slides must be <=10% of body")
    return svgs,{"slide_count":len(deck["slides"]),"body":body,"figure":figures,"table":tables}

def svg_png(svg,png):
    # Copilotの標準搭載Inkscapeを優先。ローカルでは導入済みCairoSVGも利用可。
    exe=shutil.which("inkscape")
    if exe:
        subprocess.run([exe,str(svg),"--export-type=png",f"--export-filename={png}","--export-width=2320"],
                       check=True,timeout=90,capture_output=True)
    else:
        try: import cairosvg
        except ImportError as exc: raise RuntimeError("Inkscape or CairoSVG required; no auto-install") from exc
        cairosvg.svg2png(url=str(svg),write_to=str(png),output_width=2320)
    need(png.is_file() and png.stat().st_size>0,"PNG fallback missing")

def pptx_build(deck,out,svgs):
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.opc.package import Part
    from pptx.opc.packuri import PackURI
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    from pptx.oxml import parse_xml
    from pptx.enum.shapes import MSO_SHAPE
    p=Presentation()
    px=lambda v: Inches(v/96)
    p.slide_width=px(1280);p.slide_height=px(720)
    p.core_properties.title=deck["title"];p.core_properties.author=deck["author"]
    def txt(slide,s,x,y,w,h,z,c="232F3E",bold=False):
        sh=slide.shapes.add_textbox(px(x),px(y),px(w),px(h))
        tf=sh.text_frame;tf.clear();tf.word_wrap=True
        tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0
        par=tf.paragraphs[0];par.text=s;par.font.name="Noto Sans JP"
        par.font.size=Pt(z*.75);par.font.bold=bold;par.font.color.rgb=RGBColor.from_string(c)
        return sh
    sources={x["id"]:x for x in deck["sources"]};media={}
    for i,s in enumerate(deck["slides"],1):
        slide=p.slides.add_slide(p.slide_layouts[6])
        slide.background.fill.solid();slide.background.fill.fore_color.rgb=RGBColor.from_string("FFFFFF")
        special=s["kind"] not in BODY
        txt(slide,s["title"],60,120 if special else 44,1160,75,40,bold=True)
        txt(slide,s["lead"],60,220 if special else 132,1160,68,25,"545B64")
        if s["kind"]=="figure":
            svg=out/"figures"/(s["id"]+".svg");png=svg.with_suffix(".png")
            svg.write_text(svgs[s["id"]],encoding="utf-8");svg_png(svg,png)
            h=s["figure"]["height"]
            pic=slide.shapes.add_picture(str(png),px(60),px(220+(420-h)/2),px(1160),px(h))
            pic._element.nvPicPr.cNvPr.set("descr",s["figure"]["alt"])
            # Office SVG原本とPNGフォールバックを同一Pictureとして保持。
            raw=svg.read_bytes();sha=hashlib.sha256(raw).hexdigest()
            if sha not in media:
                media[sha]=Part(PackURI("/ppt/media/fig-"+sha+".svg"),"image/svg+xml",p.part.package,raw)
            rid=slide.part.relate_to(media[sha],RT.IMAGE)
            pic._element.blipFill.blip.append(parse_xml('<a:extLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:ext uri="{96DAC541-7B7A-43D3-8B79-37D633B846F1}"><asvg:svgBlip xmlns:asvg="http://schemas.microsoft.com/office/drawing/2016/SVG/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:embed="'+rid+'"/></a:ext></a:extLst>'))
        elif s["kind"]=="table":
            rows=s["table"]
            table=slide.shapes.add_table(len(rows),len(rows[0]),px(60),px(220),px(1160),px(380)).table
            for a,row in enumerate(rows):
                for b,v in enumerate(row):
                    cell=table.cell(a,b);cell.text=v
                    cell.fill.solid();cell.fill.fore_color.rgb=RGBColor.from_string("EDF4F6" if a==0 else "FFFFFF")
                    for par in cell.text_frame.paragraphs:
                        par.font.name="Noto Sans JP";par.font.size=Pt(17);par.font.bold=(a==0)
        elif s["kind"]=="text": txt(slide,s["body"],60,230,1160,380,27)
        else:
            bar=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,px(60),px(340),px(1160),px(4))
            bar.fill.solid();bar.fill.fore_color.rgb=RGBColor.from_string("4A8399");bar.line.fill.background()
            txt(slide,deck["author"],60,400,1160,60,25,"2F6273")
        txt(slide,f'{i:02d} | '+("説明用・仮定" if s["claim_status"]=="illustrative" else ", ".join(s["source_ids"])),60,675,1160,24,15,"5F6B76")
        slide.notes_slide.notes_text_frame.text=s["notes"]+"\n"+"\n".join(sources[x]["label"]+": "+sources[x]["locator"] for x in s["source_ids"])
    p.save(out/"deck.pptx")

def build(deck_path,out):
    deck=json.loads(deck_path.read_text(encoding="utf-8"));svgs,counts=validate(deck)
    need(not out.exists() or (out.is_dir() and not any(out.iterdir())),"output must be new or empty")
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent,prefix=".slide-build-") as d:
        stage=Path(d)/"result";stage.mkdir();(stage/"figures").mkdir()
        pptx_build(deck,stage,svgs)
        (stage/"deck.json").write_text(json.dumps(deck,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        pages=[]
        for s in deck["slides"]:
            if s["kind"]=="figure":
                content='<img src="figures/'+s["id"]+'.svg" alt="'+html.escape(s["figure"]["alt"],quote=True)+'">'
            elif s["kind"]=="table":
                content="<table>"+"".join("<tr>"+"".join("<td>"+html.escape(c)+"</td>" for c in row)+"</tr>" for row in s["table"])+"</table>"
            else: content="<p>"+html.escape(s.get("body",""))+"</p>"
            pages.append("<section><h1>"+html.escape(s["title"])+"</h1><p>"+html.escape(s["lead"])+"</p>"+content+"</section>")
        (stage/"preview.html").write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\'; style-src \'unsafe-inline\'"><title>Preview</title><style>body{font-family:"Noto Sans JP",sans-serif;background:#ddd}section{box-sizing:border-box;width:1280px;height:720px;background:white;margin:20px;padding:44px 60px;overflow:hidden}h1{font-size:40px;margin:0 0 35px}p{font-size:25px}img{width:1160px;max-height:420px;object-fit:contain}td{border:1px solid #aaa;padding:12px}</style>'+"\n".join(pages),encoding="utf-8")
        report={"status":"STRUCTURAL_PASS_VISUAL_REVIEW_REQUIRED","counts":counts,
          "checks":{"structure":"PASS","svg_basic_bounds":"PASS","pptx_generated":"PASS",
          "fact_verification":"NOT_RUN","visual_overlap":"NOT_RUN","powerpoint_render":"NOT_RUN",
          "tenant_execution":"NOT_RUN","credit_usage":"NOT_RUN"},
          "limitations":["SVG interior is a vector picture, not native editable shapes",
                         "Path/transform overlap and actual font metrics require visual review",
                         "HTML preview is not the PowerPoint renderer"]}
        (stage/"review.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        if out.exists(): out.rmdir()
        shutil.move(str(stage),str(out))
    return report

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest="command",required=True)
    v=sub.add_parser("validate");v.add_argument("deck",type=Path)
    b=sub.add_parser("build");b.add_argument("deck",type=Path);b.add_argument("output",type=Path)
    a=p.parse_args()
    try:
        result=validate(json.loads(a.deck.read_text(encoding="utf-8")))[1] if a.command=="validate" else build(a.deck,a.output)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception as exc: p.exit(1,f"ERROR: {exc}\n")
if __name__=="__main__": main()
