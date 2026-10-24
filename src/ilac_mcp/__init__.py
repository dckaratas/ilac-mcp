"""ilac-mcp: TİTCK ilaç listeleri için MCP sunucusu."""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ilac-mcp", description="TİTCK ilaç verisi için MCP sunucusu")
    sub = parser.add_subparsers(dest="komut")
    sub.add_parser("serve", help="MCP sunucusunu stdio üzerinden başlatır (varsayılan)")
    sub.add_parser("sync", help="TİTCK listelerini indirip yerel veritabanını günceller")
    ara = sub.add_parser("ara", help="Komut satırından ilaç arar")
    ara.add_argument("sorgu")
    ara.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)

    if args.komut == "sync":
        from .db import db_path
        from .sync import sync

        stats = sync()
        print(json.dumps(stats, ensure_ascii=False), "->", db_path(), file=sys.stderr)
    elif args.komut == "ara":
        from . import db

        with db.session() as conn:
            for r in db.search(conn, args.sorgu, limit=args.limit):
                print(f"{r['barkod']}  {r.get('durum') or '-':6}  {r.get('atc') or '-':8}  {r['ad']}")
    else:
        from .server import server

        server.run()
