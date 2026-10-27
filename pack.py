#!/usr/bin/env python3
"""把整个 skill 打成一个 zip，可以直接发给别人。

用法：
    python pack.py                    # 输出到 dist/，版本号默认当天日期
    python pack.py --version 1.0.0

打包时自动排除：__pycache__、.git、dist、编辑器目录。
"""
from __future__ import annotations

import argparse
import fnmatch
import zipfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT_NAME = "github-release"

EXCLUDE_DIRS = {
    "__pycache__", ".git", ".idea", ".vscode", "dist", ".pytest_cache",
}
EXCLUDE_FILES = {"*.pyc", "*.pyo", ".DS_Store", "Thumbs.db"}


def should_skip(rel: Path) -> bool:
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return True
    return any(fnmatch.fnmatch(rel.name, pat) for pat in EXCLUDE_FILES)


def collect() -> list[Path]:
    return [
        p.relative_to(HERE)
        for p in sorted(HERE.rglob("*"))
        if p.is_file() and not should_skip(p.relative_to(HERE))
    ]


def main(argv=None):
    ap = argparse.ArgumentParser(description="打包 skill")
    ap.add_argument("--version", default=f"1.0.{date.today():%Y%m%d}")
    ap.add_argument("-o", "--out", default=str(HERE / "dist"))
    a = ap.parse_args(argv)

    files = collect()
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    zp = out_dir / f"{ROOT_NAME}-{a.version}.zip"

    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            z.write(HERE / rel, f"{ROOT_NAME}/{rel.as_posix()}")

    total = sum((HERE / f).stat().st_size for f in files)
    print(f"[ok] {zp}")
    print(f"     {len(files)} 个文件 · 原始 {total/1024:.1f} KB · 压缩后 {zp.stat().st_size/1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
