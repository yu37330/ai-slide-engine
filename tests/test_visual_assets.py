import base64,copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]/"skills/ai-slide-engine"
sys.path.insert(0,str(ROOT/"scripts"))
from visual_assets import load_assets
from build import figure_svg
from render_html import render
from figure_palette import adaptive_svg
from template_render import CATALOG,spec,render as render_template
from zipfile import ZipFile
NS="{http://www.w3.org/2000/svg}"
def fixture(directory):
    directory.mkdir(parents=True,exist_ok=True)
    png=directory/"screen.png";jpg=directory/"photo.jpg";svg=directory/"chart.svg"
    im=Image.new("RGB",(320,180),"#ffffff")
    draw=ImageDraw.Draw(im);draw.rectangle((20,20,300,160),fill="#2784af");draw.rectangle((40,40,130,100),fill="#f4b400")
    im.save(png);im.save(jpg,quality=95)
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180" width="320" height="180"><rect width="320" height="180" fill="#c9dde3"/><path d="M20 140 C90 10 220 160 300 20" fill="none" stroke="#2f6273" stroke-width="4"/></svg>',encoding="utf-8")
    entries=[{"id":p.stem,"file":p.name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"source":"Synthetic CI test fixture","rights":"generated"} for p in (png,jpg,svg)]
    return entries
def make_deck(directory,output):
    entries=fixture(directory)
    deck=json.loads((ROOT/"examples/sample.json").read_text(encoding="utf-8"))
    deck["assets"]=entries
    deck["slides"][1]["figure"]={"width":1160,"height":400,"alt":"画像素材の検証","operations":[
        {"component":"image","args":[25,70,340,230,"screen"]},
        {"component":"image","args":[410,70,340,230,"photo"],"kwargs":{"fit":"cover"}},
        {"component":"image","args":[795,70,340,230,"chart"]},
        {"component":"path","args":["M25 345 C300 300 800 380 1130 345"],"kwargs":{"stroke":"#4a8399","sw":3}}
    ]}
    output.write_text(json.dumps(deck,ensure_ascii=False),encoding="utf-8")
    return deck
class VisualAssetsTest(unittest.TestCase):
    def test_approved_assets_preserve_bytes_and_colors(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);deck=make_deck(p/"assets",p/"deck.json")
            entries=deck["assets"];approved=load_assets(entries,p/"assets")
            svg=figure_svg(deck["slides"][1]["figure"],assets=approved)
            refs=list(ET.fromstring(svg).iter(NS+"image"))
            self.assertEqual(len(refs),3)
            for ref,entry in zip(refs,entries):
                self.assertEqual(base64.b64decode(ref.attrib["href"].split(",",1)[1]),(p/"assets"/entry["file"]).read_bytes())
                self.assertIn("data-fixed-color",ref.attrib)
            paper=ET.fromstring(adaptive_svg(svg.encode()))
            self.assertEqual([r.attrib for r in refs],[r.attrib for r in paper.iter(NS+"image")])
            render(p/"deck.json",p/"out","paper",assets_dir=p/"assets")
            self.assertIn("data:image/png;base64",(p/"out/figures/s02.svg").read_text())
            with ZipFile(CATALOG) as z:
                cfg=spec(z,"update","petrol")
                idx=json.loads(z.read("update-petrol/index.json"))
                asset=next(n for n in idx["assets"] if n!="figs/cover-art.svg")
                v=ET.fromstring(z.read("update-petrol/"+asset)).get("viewBox").split()
                w,h=map(int,map(float,v[2:]))
            cfg["assets"]=entries
            cfg["figures"][asset]={"width":w,"height":h,"alt":"画像","operations":[{"component":"image","args":[0,0,w,h,"screen"]}]}
            render_template(CATALOG,cfg,p/"templated",assets_dir=p/"assets")
            self.assertIn("data:image/png;base64",(p/"templated"/asset).read_text())
    def test_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);entries=fixture(p)
            for patch in ({"sha256":"0"*64},{"file":"../screen.png"},{"rights":"unknown"},{"source":""},{"file":"photo.jpg"}):
                bad=copy.deepcopy(entries);bad[0].update(patch)
                with self.assertRaises((ValueError,FileNotFoundError)):load_assets(bad,p)
            with self.assertRaises(ValueError):load_assets(entries,None)
            evil=p/"evil.svg";evil.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><image href="https://example.com/x.png"/></svg>')
            bad=[{"id":"evil","file":"evil.svg","sha256":hashlib.sha256(evil.read_bytes()).hexdigest(),"rights":"owned","source":"fixture"}]
            with self.assertRaises(ValueError):load_assets(bad,p)
            with self.assertRaises(ValueError):figure_svg({"width":1160,"height":400,"alt":"x","operations":[{"component":"image","args":[0,0,100,100,"missing"]}]})
            with self.assertRaises(ValueError):figure_svg({"width":1160,"height":400,"alt":"x","operations":[{"component":"path","args":['M0 0" onload="x']}]})
if __name__=="__main__":
    if len(sys.argv)==3:make_deck(Path(sys.argv[1]),Path(sys.argv[2]))
    else:unittest.main()
