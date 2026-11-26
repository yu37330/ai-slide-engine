"""Compare archive payloads, independent of platform ZIP metadata and order."""
from pathlib import Path
from zipfile import ZipFile
import sys

def payload(path):
    with ZipFile(path) as z:
        assert z.testzip() is None, f"Corrupt archive: {path}"
        names=z.namelist()
        assert len(names)==len(set(names)), f"Duplicate entry: {path}"
        assert "SKILL.md" in names, "SKILL.md must be at ZIP root"
        return {name:z.read(name) for name in names}

if __name__=="__main__":
    generated,checked=map(payload,sys.argv[1:3])
    assert generated.keys()==checked.keys(), "ZIP file list differs"
    assert generated==checked, "ZIP content differs from source"
    print(f"ZIP payload verified: {len(checked)} files")
