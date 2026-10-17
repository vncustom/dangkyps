"""Truy van nghiep vu dung chung: trang thai duyet file, danh sach file."""
import json
import sqlite3

FILE_SELECT = """
SELECT f.*,
  (SELECT result FROM reviews r WHERE r.file_id = f.file_id AND r.reviewer_kind = 'ban_phu_trach') AS bp_result,
  (SELECT result FROM reviews r WHERE r.file_id = f.file_id AND r.reviewer_kind = 'bien_tap_vien') AS btv_result,
  (SELECT so_phieu FROM tickets t WHERE t.file_id = f.file_id) AS so_phieu
FROM files f
"""


def review_state(bp_result: str | None, btv_result: str | None) -> str:
    """dat khi ca hai Dat; khong_dat khi it nhat mot ben Khong dat; con lai chua."""
    if "khong_dat" in (bp_result, btv_result):
        return "khong_dat"
    if bp_result == "dat" and btv_result == "dat":
        return "dat"
    return "chua"


def _decorate(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["review_state"] = review_state(d["bp_result"], d["btv_result"])
    try:
        d["qc_items"] = json.loads(d["qc_json"]) if d.get("qc_json") else []
    except ValueError:
        d["qc_items"] = []
    return d


def list_files(conn: sqlite3.Connection, unit: str | None = None, where: str = "",
               params: tuple = ()) -> list[dict]:
    clauses, args = [], list(params)
    if unit is not None:
        clauses.append("f.unit = ?")
        args.append(unit)
    if where:
        clauses.append(where)
    sql = FILE_SELECT + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY f.file_id DESC"
    return [_decorate(r) for r in conn.execute(sql, args)]


def get_file(conn: sqlite3.Connection, file_id: int) -> dict | None:
    row = conn.execute(FILE_SELECT + " WHERE f.file_id = ?", (file_id,)).fetchone()
    return _decorate(row) if row else None


def units(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT ds_ban FROM users WHERE ds_ban != '' ORDER BY ds_ban")]
