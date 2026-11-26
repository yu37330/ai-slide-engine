"""Copilot Chatの個人スキルZIPを生成。SKILL.mdをZIPルートに置く。"""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_STORED
ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/"skills"/"ai-slide-engine"
EXT={".md",".txt",".json",".py",".mjs",".js",".css"}
def package(output):
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(output,"w",ZIP_STORED) as z:
        for p in sorted(SKILL.rglob("*"),key=lambda p: tuple(part.casefold() for part in p.relative_to(SKILL).parts)):
            if p.is_file() and (p.suffix in EXT or p.relative_to(SKILL).as_posix()=="templates/catalog.zip") and "__pycache__" not in p.parts:
                # WindowsとLinuxで同一のUTF-8・LF・固定時刻を使う。署名対象を再現可能にする。
                info=ZipInfo(p.relative_to(SKILL).as_posix(),(2026,1,1,0,0,0))
                info.create_system=0
                info.external_attr=0o600 << 16
                z.writestr(info,p.read_bytes() if p.suffix==".zip" else p.read_text(encoding="utf-8").encode("utf-8"))
    return output
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT/"dist"/"ai-slide-engine.zip")
    args=parser.parse_args()
    print(package(args.output))
