import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from package_copilot_skill import make
from package_skill import package
from copilot_upload.bootstrap_copilot import ALLOWED,CAT,CSS,restore

def payload(z):
    with zipfile.ZipFile(z) as f:
        assert f.testzip() is None
        return {n:f.read(n) for n in f.namelist() if not n.endswith("/")}
class CopilotPackageTest(unittest.TestCase):
    def test_supported_types_and_exact_restore(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);z=make(root/"skill.zip");canonical=package(root/"original.zip")
            up=payload(z);original=payload(canonical)
            self.assertIn("SKILL.md",up)
            self.assertTrue(all(Path(n).suffix in ALLOWED for n in up))
            self.assertFalse(any(n.endswith((".css",".zip",".woff2")) for n in up))
            self.assertTrue(all(n+".txt" in up for n in CSS))
            data=json.loads(up["templates/catalog.json"])
            self.assertTrue(all("text" in row for row in data["members"].values()))
            source=root/"upload";source.mkdir()
            with zipfile.ZipFile(z) as f:f.extractall(source)
            result=restore(source,root/"restored")
            for name,raw in original.items():
                if name=="SKILL.md":self.assertIn(raw.decode("utf-8").split("## 原則",1)[1],(root/"restored"/name).read_text(encoding="utf-8"));continue
                if name==CAT:continue
                self.assertEqual((root/"restored"/name).read_bytes(),raw,name)
            with zipfile.ZipFile(canonical) as f: (root/"catalog-original.zip").write_bytes(f.read(CAT))
            self.assertEqual(payload(root/"catalog-original.zip"),payload(root/"restored"/CAT))
            self.assertEqual(result["integrity"],"SHA256_PASS")
            print("COPILOT_RESTORE_EXACT",json.dumps({"engine_files":len(original)-2,"catalog_members":result["catalog_members"],"modified_instructions":1,"catalog_member_bytes_equal":True}))
    def test_tamper_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);z=make(root/"skill.zip");source=root/"upload";source.mkdir()
            with zipfile.ZipFile(z) as f:f.extractall(source)
            p=source/"html/themes/petrol.css.txt";raw=p.read_bytes();p.write_bytes(raw+b"tampered")
            with self.assertRaises(ValueError):restore(source,root/"bad")
            self.assertFalse((root/"bad").exists())
            p.write_bytes(raw)
            m=source/"package-manifest.json";doc=json.loads(m.read_text())
            doc["files"][0]["target"]="../escape";m.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):restore(source,root/"bad2")
            self.assertFalse((root/"escape").exists());self.assertFalse((root/"bad2").exists())
if __name__=="__main__":unittest.main()
