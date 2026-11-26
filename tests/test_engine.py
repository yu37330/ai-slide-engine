import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/"skills"/"ai-slide-engine"
sys.path.insert(0,str(SKILL/"scripts"))
sys.path.insert(0,str(ROOT/"scripts"))
from build import validate,build
from package_skill import package
from pptx import Presentation

class EngineTest(unittest.TestCase):
    def setUp(self):
        self.deck=json.loads((SKILL/"examples/sample.json").read_text(encoding="utf-8"))
    def test_valid_and_structural_gate(self):
        svg,counts=validate(self.deck)
        self.assertEqual(counts["figure"],3)
        self.assertEqual(len(svg),3)
        for change in ("id","source","outside","unsafe"):
            with self.subTest(change=change):
                d=copy.deepcopy(self.deck)
                if change=="id": d["slides"][1]["id"]="../oops"
                elif change=="source": d["slides"][1]["claim_status"]="factual"
                elif change=="outside": d["slides"][1]["figure"]["operations"].append({"component":"R","args":[1150,0,100,100]})
                else: d["slides"][1]["figure"]["operations"].append({"component":"__getattribute__","args":["parts"]})
                with self.assertRaises(ValueError): validate(d)
    def test_build_and_svg_embedding(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"out"
            report=build(SKILL/"examples/sample.json",out)
            self.assertEqual(report["status"],"STRUCTURAL_PASS_VISUAL_REVIEW_REQUIRED")
            prs=Presentation(out/"deck.pptx")
            self.assertEqual(len(prs.slides),5)
            self.assertIn("需要変動",prs.slides[1].shapes[0].text)
            with ZipFile(out/"deck.pptx") as z:
                self.assertEqual(sum(x.endswith(".svg") for x in z.namelist()),3)
                self.assertIn(b"svgBlip",z.read("ppt/slides/slide2.xml"))
            self.assertTrue((out/"figures/s02.svg").is_file())
    def test_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            zpath=package(Path(tmp)/"skill.zip")
            with ZipFile(zpath) as z:
                self.assertIn("SKILL.md",z.namelist())
                self.assertIn("scripts/jfig.py",z.namelist())
                self.assertIn("references/LICENSE.txt",z.namelist())
                self.assertNotIn("ai-slide-engine/SKILL.md",z.namelist())

if __name__=="__main__":
    unittest.main()
