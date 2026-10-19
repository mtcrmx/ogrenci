"""CLI: python -m migrations [up|down|status] [hedef_surum]"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import database as db
from migrations import current_version, migrate_down, migrate_up


def main() -> None:
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "up").lower()
    target = int(sys.argv[2]) if len(sys.argv) > 2 else None
    con = db._conn()
    try:
        if cmd == "up":
            ran = migrate_up(con, target=target)
            print(f"migrate_up tamamlandi: {ran} (aktif surum={current_version(con)})")
        elif cmd == "down":
            hedef = 0 if target is None else target
            rev = migrate_down(con, target=hedef)
            print(f"migrate_down tamamlandi: {rev} (aktif surum={current_version(con)})")
        elif cmd == "status":
            print(f"aktif surum={current_version(con)}")
        else:
            raise SystemExit(f"Bilinmeyen komut: {cmd}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
