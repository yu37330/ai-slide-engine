"""公開資料だけを含む初回配布ZIPの取得用。"""
import base64
import hashlib
import sys
from pathlib import Path
data=Path(sys.argv[1]).read_bytes()
s=base64.b64encode(data).decode("ascii")
chunks=[s[i:i+10000] for i in range(0,len(s),10000)]
print("COPILOT_EXPORT_START",len(chunks),len(data),hashlib.sha256(data).hexdigest())
for i,chunk in enumerate(chunks):print("COPILOT_CHUNK",i,chunk)
print("COPILOT_EXPORT_END")
