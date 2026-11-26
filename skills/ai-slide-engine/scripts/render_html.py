"""Copilot JSON -> SVG -> 原典CSSに従うHTML。Marpを実行しない。"""
import argparse
import html
import json
import shutil
from pathlib import Path
from build import validate, need
from figure_palette import adaptive_svg

ROOT = Path(__file__).resolve().parents[1]
def esc(s):
    return html.escape(s, quote=True)
def lines(s):
    return esc(s).replace("\n", "<br>")
def render(deck_file, output, theme="petrol", fonts=None):
    deck=json.loads(Path(deck_file).read_text(encoding="utf-8"))
    svgs,counts=validate(deck)
    need(theme in ("petrol","paper"),"unsupported theme")
    out=Path(output)
    need(not out.exists() or (out.is_dir() and not any(out.iterdir())),"output must be new or empty")
    out.mkdir(parents=True,exist_ok=True)
    (out/"figures").mkdir()
    (out/"themes").mkdir()
    for name in ("petrol.css","paper.css"):
        css=(ROOT/"html/themes"/name).read_text(encoding="utf-8")
        if name=="paper.css":
            css=css.replace("@import 'petrol';","")
        (out/"themes"/name).write_text(css,encoding="utf-8")
    # フォントファイルは配布しない。許可済みのローカル資産を明示指定した場合のみ使用。
    names=("NotoSansJP-Book450.woff2","NotoSansJP-Bold.woff2","NotoSansJP-Regular.woff2")
    if fonts:
        src=Path(fonts)
        need(all((src/n).is_file() for n in names),"all three approved font files required")
        (out/"themes/assets").mkdir()
        for n in names: shutil.copyfile(src/n,out/"themes/assets"/n)
    else:
        p=out/"themes/petrol.css"
        css=p.read_text(encoding="utf-8")
        css="\n".join(line for line in css.splitlines() if not line.startswith("@font-face"))
        p.write_text(css,encoding="utf-8")
    pages=[]
    for i,s in enumerate(deck["slides"],1):
        kind=s["kind"];sid=s["id"];cls={"cover":"cover cover-centered","section":"divider","closing":"closing"}.get(kind,"")
        title="<h1>"+lines(s["title"])+"</h1>"
        lead='<p class="lead">'+lines(s["lead"])+"</p>" if s["lead"] else ""
        block=""
        if kind=="figure":
            svg=svgs[sid].encode("utf-8")
            if theme=="paper": svg=adaptive_svg(svg)
            (out/"figures"/(sid+".svg")).write_bytes(svg)
            block='<div class="blocks is-visual"><p class="image-block"><img src="figures/'+sid+'.svg" alt="'+esc(s["figure"]["alt"])+'" style="height:'+str(s["figure"]["height"])+'px"></p></div>'
        elif kind=="table":
            rows=s["table"]
            block='<div class="blocks"><table><thead><tr>'+''.join("<th>"+esc(c)+"</th>" for c in rows[0])+'</tr></thead><tbody>'+''.join("<tr>"+''.join("<td>"+esc(c)+"</td>" for c in row)+"</tr>" for row in rows[1:])+"</tbody></table></div>"
        elif kind=="text": block='<div class="blocks"><p>'+lines(s["body"])+'</p></div>'
        elif kind in ("cover","closing"):
            block='<div class="blocks"><p class="who">'+esc(deck["author"])+'</p></div>'
        page_no=str(i) if kind not in ("cover","closing","section") else ""
        pages.append('<section id="'+sid+'" class="'+cls+'" data-marpit-pagination="'+page_no+'">'+title+lead+block+'</section>')
    paper='<link rel="stylesheet" href="themes/paper.css">' if theme=="paper" else ""
    shell='<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\' data:; style-src \'self\' \'unsafe-inline\'; font-src \'self\' data:; script-src \'none\'"><title>'+esc(deck["title"])+'</title><link rel="stylesheet" href="themes/petrol.css">'+paper+'<style>html,body{margin:0;padding:0;background:#888}section[id]{display:flex;width:1280px;height:720px;margin:0 0 8px}</style></head><body>'+"\n".join(pages)+"</body></html>"
    (out/"deck.html").write_text(shell,encoding="utf-8")
    (out/"deck.json").write_text(json.dumps(deck,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    manifest={"version":1,"theme":theme,"font_mode":"approved_assets" if fonts else "system_fallback_unverified","slides":[s["id"] for s in deck["slides"]],"counts":counts}
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return manifest

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("deck",type=Path);p.add_argument("output",type=Path)
    p.add_argument("--theme",choices=["petrol","paper"],default="petrol")
    p.add_argument("--fonts",type=Path)
    a=p.parse_args()
    print(json.dumps(render(a.deck,a.output,a.theme,a.fonts),ensure_ascii=False,indent=2))
