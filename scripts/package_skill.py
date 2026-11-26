"""Copilot Chatの個人スキルZIPを生成。SKILL.mdをZIPルートに置く。"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/"skills"/"ai-slide-engine"
EXT={".md",".txt",".json",".py"}
def package(output):
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(output,"w",ZIP_DEFLATED) as z:
        for p in sorted(SKILL.rglob("*")):
            if p.is_file() and p.suffix in EXT and "__pycache__" not in p.parts:
                z.write(p,p.relative_to(SKILL).as_posix())
    return output
if __name__=="__main__":
    print(package(ROOT/"dist"/"ai-slide-engine.zip"))
