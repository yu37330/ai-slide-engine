"""CIだけで原典のフォントをローカルの一時領域に展開する。配布・commitしない。"""
import hashlib
import json
import sys
from pathlib import Path
from fontTools.ttLib import TTFont
source,dest=map(Path,sys.argv[1:3])
dest.mkdir(parents=True,exist_ok=True)
for name in ("NotoSansJP-Regular.woff2","NotoSansJP-Bold.woff2"):
    p=source/name
    font=TTFont(p);font.flavor=None
    out=dest/p.with_suffix(".ttf").name
    font.save(out)
    print("PARITY_FONT",json.dumps({"file":name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"family":font["name"].getDebugName(1),"style":font["name"].getDebugName(2)},ensure_ascii=False))
