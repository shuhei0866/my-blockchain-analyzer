"""Fail if a distribution contains legacy code, configuration or data."""
from pathlib import Path
import sys
from zipfile import ZipFile

paths=list(Path(sys.argv[1]).glob("blockchain_portfolio_core-*.whl"))
assert len(paths)==1,"expected one built core wheel"
code={"blockchain_portfolio/"+name+".py" for name in ("__init__","model","providers","valuation")}
with ZipFile(paths[0]) as wheel:
    files=set(wheel.namelist())
    metadata={p for p in files if p.startswith("blockchain_portfolio_core-") and ".dist-info/" in p
              and p.rsplit("/",1)[-1] in {"METADATA","WHEEL","RECORD","top_level.txt"}}
    assert files==code|metadata,"unexpected file in distribution"
print("wheel boundary verified")
