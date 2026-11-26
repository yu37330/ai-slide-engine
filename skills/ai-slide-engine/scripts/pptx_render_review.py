"""PPTXの再描画品質。LibreOffice/Popplerによる独立測定でありOffice実機の代替認証ではない。"""
import argparse
import json
import posixpath
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

P="http://schemas.openxmlformats.org/presentationml/2006/main"
A="http://schemas.openxmlformats.org/drawingml/2006/main"
R="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL="http://schemas.openxmlformats.org/package/2006/relationships"
def q(ns,tag):return "{"+ns+"}"+tag
def require(ok,msg):
    if not ok:raise ValueError(msg)
def text_normalized(s):
    return "".join(unicodedata.normalize("NFKC",s).split())
def inspect_pptx(path):
    """OOXML構造、参照整合性、ページ単位の編集可能オブジェクトを測定。"""
    with zipfile.ZipFile(path) as z:
        names=set(z.namelist())
        require(z.testzip() is None,"PPTX CRC error")
        require(len(names)==len(z.namelist()),"duplicate ZIP member")
        xml={}
        for name in names:
            if name.endswith((".xml",".rels")):
                raw=z.read(name)
                require(not re.search(rb"<!DOCTYPE|<!ENTITY",raw,re.I),"unsafe XML")
                xml[name]=ET.fromstring(raw)
        order=sorted((name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml",name)),key=lambda n:int(re.search(r"(\d+)\.xml$",n)[1]))
        require(order,"no PPTX slides")
        require(len(xml["ppt/presentation.xml"].find(q(P,"sldIdLst")))==len(order),"presentation page count mismatch")
        size=xml["ppt/presentation.xml"].find(q(P,"sldSz"))
        require(size is not None and int(size.get("cx"))>0 and int(size.get("cy"))>0,"invalid slide size")
        require(abs(int(size.get("cx"))/int(size.get("cy"))-16/9)<.002,"slide aspect ratio mismatch")
        rows=[]
        for name in order:
            root=xml[name];tree=root.find(".//"+q(P,"spTree"))
            require(tree is not None,"missing shape tree: "+name)
            ids=[e.get("id") for e in tree.iter(q(P,"cNvPr"))]
            require(all(ids) and len(ids)==len(set(ids)),"duplicate shape id: "+name)
            relname=posixpath.join(posixpath.dirname(name),"_rels",posixpath.basename(name)+".rels")
            relationships={e.get("Id"):e for e in xml.get(relname,[])}
            for e in root.iter():
                for k,v in e.attrib.items():
                    if k not in (q(R,"embed"),q(R,"id"),q(R,"link")):continue
                    require(v in relationships,"missing relationship: "+name+" "+v)
                    rel=relationships[v]
                    if rel.get("TargetMode")=="External":
                        require(rel.get("Type","").endswith("/hyperlink"),"external non-hyperlink relationship")
                        continue
                    target=rel.get("Target","")
                    resolved=target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(posixpath.dirname(name),target))
                    require(resolved in names,"missing relationship target: "+resolved)
            counts={k:len(list(tree.iter(q(ns,tag)))) for k,ns,tag in [
                ("shapes",P,"sp"),("text_runs",A,"t"),("tables",A,"tbl"),("images",P,"pic"),("groups",P,"grpSp")]}
            text="".join(e.text or "" for e in tree.iter(q(A,"t")))
            require(counts["shapes"]+counts["tables"]>0 or counts["images"]==0,"image-only slide: "+name)
            # XML bytesではなく各図形の計算済み幾何を比較できるようにする。
            geometry=[]
            for e in tree.iter(q(A,"xfrm")):
                geometry.append({"attrs":dict(e.attrib),"children":[(c.tag.split("}")[-1],dict(c.attrib)) for c in e]})
            rows.append({**counts,"text":text_normalized(text),"geometry":geometry})
        return {"slides":len(rows),"size":dict(size.attrib),"pages":rows}
def render_pptx(pptx,out):
    pptx=Path(pptx).resolve();out=Path(out).resolve()
    require(pptx.is_file(),"PPTX missing")
    require(not out.exists() or not any(out.iterdir()),"render output must be empty")
    out.mkdir(parents=True,exist_ok=True)
    soffice=shutil.which("soffice") or shutil.which("libreoffice")
    ppm=shutil.which("pdftoppm")
    require(soffice and ppm,"preinstalled LibreOffice and Poppler are required; no automatic install")
    with tempfile.TemporaryDirectory(prefix="slide-review-") as temp:
        profile=Path(temp,"profile").as_uri()
        r=subprocess.run([soffice,"-env:UserInstallation="+profile,"--headless","--norestore","--nodefault","--nolockcheck","--convert-to","pdf","--outdir",str(out),str(pptx)],capture_output=True,text=True,timeout=150)
        pdf=out/(pptx.stem+".pdf")
        require(r.returncode==0 and pdf.is_file() and pdf.stat().st_size>0,"LibreOffice failed: "+r.stdout[-1000:]+r.stderr[-1000:])
    subprocess.run([ppm,"-png","-scale-to-x","1280","-scale-to-y","720",str(pdf),str(out/"page")],check=True,capture_output=True,timeout=120)
    pages=sorted(out.glob("page-*.png"),key=lambda p:int(p.stem.rsplit("-",1)[1]))
    require(pages,"PDF contains no rendered pages")
    return pages
def image_metrics(a,b):
    """同一1280x720のRGB差。SSIMは明度の8x8非重複ブロック平均（定義を固定）。"""
    import numpy as np
    from PIL import Image
    with Image.open(a) as im:
        x=np.asarray(im.convert("RGB"),dtype=np.float32)
    with Image.open(b) as im:
        y=np.asarray(im.convert("RGB"),dtype=np.float32)
    require(x.shape==y.shape==(720,1280,3),f"image size mismatch: {x.shape}/{y.shape}")
    d=np.abs(x-y);mx=d.max(axis=2)
    def lum(x):return (x[...,0]*.299+x[...,1]*.587+x[...,2]*.114).reshape(90,8,160,8).transpose(0,2,1,3).reshape(-1,64)
    lx,ly=lum(x),lum(y);ux,uy=lx.mean(1),ly.mean(1);vx,vy=lx.var(1),ly.var(1)
    cov=((lx-ux[:,None])*(ly-uy[:,None])).mean(1);c1=(.01*255)**2;c2=(.03*255)**2
    ssim=((2*ux*uy+c1)*(2*cov+c2)/((ux*ux+uy*uy+c1)*(vx+vy+c2))).mean()
    return {"pixels":int(mx.size),"different":int((mx>0).sum()),"different_gt32":int((mx>32).sum()),"mae":float(d.mean()),"ssim8":float(ssim)}
def review(pptx,html_pages,output,baseline=None):
    """基準PPTXがあれば相対比較も実施。絶対差がゼロでない限り完全再現とは呼ばない。"""
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    target=inspect_pptx(pptx)
    shots=sorted(Path(html_pages).glob("*.png"))
    images=render_pptx(pptx,output/"candidate")
    require(len(shots)==len(images)==target["slides"],"HTML/PPTX/PDF page count mismatch")
    ref=inspect_pptx(baseline) if baseline else None
    base_images=render_pptx(baseline,output/"baseline") if baseline else []
    if ref:require(len(base_images)==len(shots)==ref["slides"],"baseline page count mismatch")
    result={"status":"MEASURED_REVIEW_REQUIRED","renderer":"LibreOffice + Poppler (not Microsoft PowerPoint)",
            "native":target,"pages":[],"baseline":ref}
    for i,(html,png) in enumerate(zip(shots,images)):
        row={"page":i+1,"html_candidate":image_metrics(html,png)}
        if ref:
            row["html_baseline"]=image_metrics(html,base_images[i])
            row["baseline_candidate"]=image_metrics(base_images[i],png)
            t,b=target["pages"][i],ref["pages"][i]
            row["native_equal"]={k:t[k]==b[k] for k in ("shapes","text_runs","tables","images","groups","text","geometry")}
        result["pages"].append(row)
    (output/"review-pptx.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument("pptx",type=Path);p.add_argument("html_pages",type=Path);p.add_argument("output",type=Path);p.add_argument("--baseline",type=Path)
    a=p.parse_args();r=review(a.pptx,a.html_pages,a.output,a.baseline)
    print(json.dumps({"status":r["status"],"renderer":r["renderer"],"pages":len(r["pages"]),
                      "mean_html_mae":sum(x["html_candidate"]["mae"] for x in r["pages"])/len(r["pages"]),
                      "exact_html_pages":sum(x["html_candidate"]["different"]==0 for x in r["pages"])},ensure_ascii=False))
if __name__=="__main__":main()
