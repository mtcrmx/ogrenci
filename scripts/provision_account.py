"""Offline account recovery on the school's server.

Example: python scripts/provision_account.py --teacher "NAME" --output /private/code.txt
Use the production DB environment only deliberately. Output is created exclusively;
existing files are never overwritten. Deliver the file privately and remove it after use.
"""
import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Create one private school account recovery code.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--teacher')
    group.add_argument('--student-no', type=int)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import database as db
    import account_security as auth
    db.initialize_db()
    con = db._conn()
    if args.teacher:
        row = con.execute('SELECT id, ad_soyad FROM ogretmenler WHERE ad_soyad=?', (args.teacher,)).fetchone()
    else:
        rows = con.execute('SELECT id, ad_soyad FROM ogrenciler WHERE ogr_no=?', (args.student_no,)).fetchall()
        row = rows[0] if len(rows) == 1 else None
    con.close()
    if not row:
        parser.error('A unique matching account was not found.')
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        code = auth.issue_teacher_code(row['id']) if args.teacher else auth.issue_parent_code(row['id'])
        output.write(f"{row['ad_soyad']}\n{args.student_no or ''}\n{code}\n")
    print('Recovery code saved to the specified private file. Previous sessions are revoked.')


if __name__ == '__main__':
    main()
