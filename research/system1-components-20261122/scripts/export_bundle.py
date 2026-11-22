#!/usr/bin/env python3
"""Export only the verdict-free components study public-safe overlay."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

P=Path(__file__).resolve().parents[1]
FILES=['PROTOCOL.md','REPORT.md','README.md','REPRODUCE.md','HANDOFF.md',
       'allocation.json','design.json','heldout-cases.json','requests.json','freeze.json',
       'scripts/prepare.py','scripts/run.py','scripts/analyze.py','scripts/export_bundle.py',
       'evidence/live-results.json','evidence/summary.json','evidence/checks.json']


def export(output):
    files={n:(P/n).read_bytes() for n in FILES}
    files['SHA256SUMS.json']=(json.dumps({n:hashlib.sha256(b).hexdigest() for n,b in sorted(files.items())},indent=2)+'\n').encode()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,11,22,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644 << 16
            z.writestr(info,data)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    export(parser.parse_args().output)
