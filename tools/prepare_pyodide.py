#!/usr/bin/env python3
"""Vendor the official Pyodide 314.0.7 runtime for browser/offline deployment.

Run once before uploading the static app, or let GitHub Actions do it.
Needs internet access only at build time. No credit card or Python server.
"""
from pathlib import Path
from urllib.request import urlopen, Request
import sys

VERSION='314.0.7'
CDN=f'https://cdn.jsdelivr.net/pyodide/v{VERSION}/full/'
FILES=('pyodide.js','pyodide.asm.mjs','pyodide.asm.wasm','python_stdlib.zip','pyodide-lock.json')
TARGET=Path(__file__).resolve().parents[1]/'vendor'/'pyodide'
TARGET.mkdir(parents=True,exist_ok=True)
def main():
    for filename in FILES:
        dst=TARGET/filename
        if dst.exists() and dst.stat().st_size>1000:
            print('Already present:', filename, dst.stat().st_size)
            continue
        print('Downloading:', filename,flush=True)
        req=Request(CDN+filename,headers={'User-Agent':'ASTRA-Browser-PWA/1.3.1'})
        tmp=dst.with_suffix(dst.suffix+'.part')
        try:
            with urlopen(req,timeout=90) as src, open(tmp,'wb') as out:
                while True:
                    part=src.read(256*1024)
                    if not part:break
                    out.write(part)
            if tmp.stat().st_size<1000: raise RuntimeError(f'Unexpected small file: {filename}')
            tmp.replace(dst)
        finally:
            tmp.unlink(missing_ok=True)
    print('Pyodide runtime bundled: ',TARGET)
if __name__=='__main__':main()
