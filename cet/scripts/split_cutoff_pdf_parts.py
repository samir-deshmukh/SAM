#!/usr/bin/env python3
"""Prepare temporary page-range PDF parts in a short-lived process."""
from __future__ import annotations
import argparse
from pathlib import Path
import fitz
from chunked_cutoff_extractor import split_pdf

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--chunk-pages", type=int, default=1000)
    parser.add_argument("--skip-indices", default="", help="Comma-separated 1-based parts already complete")
    parser.add_argument("--count-only", action="store_true")
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error(f"Source PDF does not exist: {args.source}")
    with fitz.open(args.source) as source:
        total_pages = len(source)
        if args.count_only:
            print(total_pages)
            return 0
        if args.out is None:
            parser.error("--out is required unless --count-only is used")
        if args.chunk_pages < 1:
            parser.error("--chunk-pages must be positive")
        args.out.mkdir(parents=True, exist_ok=True)
        skip = {int(x) for x in args.skip_indices.split(",") if x.strip().isdigit()}
        count = (total_pages + args.chunk_pages - 1) // args.chunk_pages
        for idx in range(count):
            number = idx + 1
            if number in skip:
                continue
            start = idx * args.chunk_pages
            end = min(start + args.chunk_pages, total_pages)
            destination = args.out / f"part_{number:04d}.pdf"
            if destination.exists():
                continue
            split_pdf(source, destination, start, end)
            print(f"Prepared part {number}/{count}: pages {start+1}-{end}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
