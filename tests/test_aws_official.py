"""実際のAWS配布原本が渡された場合だけ、正規アイコンの結合を検証する。"""
import copy,json,os,sys,tempfile,unittest
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]/"skills/ai-slide-engine"
sys.path.insert(0,str(ROOT/"scripts"))
import jfig
from aws_assets import configure, require_icon, safe_svg
from build import figure_svg
from figure_palette import adaptive_svg
class OfficialTest(unittest.TestCase):
    @unittest.skipUnless(os.getenv("OFFICIAL_AWS_CACHE"),"official package not supplied")
    def test_three_services(self):
        report=configure(os.environ["OFFICIAL_AWS_CACHE"])
        print("AWS_OFFICIAL",report["source"],report["package_sha256"],"safe",report["count"],"rejected",report["rejected_count"])
        keys=[]
        for wanted in ["amazonsimplestorageservices3","amazonbedrock","awslambda"]:
            hits=[e for e in jfig._AWS[1] if e["kind"]=="service" and e["key"].endswith("_64") and jfig._norm(e["key"]) in (jfig._norm(wanted),wanted)]
            if not hits:
                terms={"amazonsimplestorageservices3":["s3","simplestorageservice"],"amazonbedrock":["bedrock"],"awslambda":["lambda"]}[wanted]
                hits=[e for e in jfig._AWS[1] if e["kind"]=="service" and e["key"].endswith("_64") and any(jfig._norm(e["key"])==t for t in terms)]
            self.assertTrue(hits,wanted)
            keys.append(hits[0]["key"])
        ops=[{"component":"aws","args":[160+i*410,100,key,["Amazon S3","Amazon Bedrock","AWS Lambda"][i]],"kwargs":{"size":64}} for i,key in enumerate(keys)]
        ops += [{"component":"A","args":[220,140,480,140]},{"component":"A","args":[630,140,890,140]}]
        svg=figure_svg({"width":1160,"height":400,"alt":"AWS architecture","operations":ops})
        ns="{http://www.w3.org/2000/svg}"
        original=ET.fromstring(svg)
        paper=ET.fromstring(adaptive_svg(svg.encode()))
        for key in keys:
            p=require_icon(key);safe_svg(p.read_bytes())
            a=next(e for e in original.iter(ns+"svg") if e.get("data-aws-icon")==key)
            b=next(e for e in paper.iter(ns+"svg") if e.get("data-aws-icon")==key)
            self.assertEqual(ET.tostring(a),ET.tostring(b))
            self.assertIn("data-fixed-color",a.attrib)
            print("AWS_ICON_OK",key,p.name)
        jfig._AWS=None
    def test_missing_cache_fails_closed(self):
        jfig._AWS=None
        with self.assertRaises(ValueError):
            figure_svg({"width":1160,"height":400,"alt":"x","operations":[{"component":"aws","args":[200,100,"unapproved","S3"]}]})
if __name__=="__main__":unittest.main()
