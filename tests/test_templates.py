import copy,json,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"skills/ai-slide-engine"
sys.path.insert(0,str(ROOT/"scripts"))
from template_render import CATALOG,render,spec,inspect_template
from xml.etree import ElementTree as ET
class TemplateTest(unittest.TestCase):
    def test_all_variants_and_counts(self):
        with zipfile.ZipFile(CATALOG) as z:
            c=json.loads(z.read("catalog.json"))
            self.assertEqual(len(c["variants"]),10)
            self.assertEqual(sum(v["pages"] for v in c["variants"]),96)
            self.assertFalse(any(n.lower().endswith((".woff2",".ttf",".otf")) for n in z.namelist()))
            self.assertTrue(all(v["slots"] for v in c["variants"]))
    def test_custom_cover_title_and_nonstandard_canvas(self):
        with tempfile.TemporaryDirectory() as tmp,zipfile.ZipFile(CATALOG) as z:
            cfg=spec(z,"update","petrol");idx=inspect_template(z,"update","petrol")
            title=next(k for k,v in idx["slots"].items() if v["role"]=="title")
            cfg["slots"][title]="<AI> 構成図"
            cfg["cover_art"]={"title":"Custom cover","operations":[{"component":"card","args":[60,120,200,120]},{"component":"block","args":[300,300,170,140]}]}
            asset=next(p for p,v in idx["canvases"].items() if v and p!="figs/cover-art.svg")
            w,h=idx["canvases"][asset]
            cfg["figures"][asset]={"width":w,"height":h,"alt":"Custom figure","operations":[{"component":"R","args":[10,10,w-20,h-20],"kwargs":{"fill":"white","stroke":"#4a8399"}}]}
            out=Path(tmp)/"out";m=render(CATALOG,cfg,out)
            html=(out/"deck.html").read_text(encoding="utf-8")
            self.assertIn("&lt;AI&gt;",html);self.assertNotIn("<AI>",html)
            self.assertGreaterEqual(html.count("figs/cover-art.svg"),2)
            self.assertIn("Custom cover",(out/"figs/cover-art.svg").read_text(encoding="utf-8"))
            self.assertEqual(ET.parse(out/asset).getroot().get("viewBox"),f"0 0 {w} {h}")
            self.assertEqual(m["font_mode"],"system_fallback_unverified")
            self.assertEqual(len(m["slides"]),8)
if __name__=="__main__":unittest.main()
