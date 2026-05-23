"""
tools/google_sheets_tool.py — Google Sheets read/write.
Requires 'spreadsheets' scope.
"""


def _svc():
    from tools.google_auth import get_service
    return get_service("sheets", "v4")


def sheets_read(spreadsheet_id: str, range_: str = "Sheet1!A1:Z100") -> str:
    """Read a range from a Google Sheets spreadsheet."""
    try:
        result = _svc().spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_
        ).execute()
        rows = result.get("values", [])
        if not rows:
            return "No data in that range."
        return "\n".join("\t".join(str(c) for c in row) for row in rows)
    except Exception as e:
        return _scope_err(e)


def sheets_append(spreadsheet_id: str, values: list, sheet_name: str = "Sheet1") -> str:
    """Append a row to a Google Sheets spreadsheet."""
    try:
        _svc().spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [values]},
        ).execute()
        return f"Row appended: {values}"
    except Exception as e:
        return _scope_err(e)


def sheets_write(spreadsheet_id: str, range_: str, values: list) -> str:
    """Write values to a range in a spreadsheet."""
    try:
        _svc().spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()
        return f"Written to {range_}."
    except Exception as e:
        return _scope_err(e)


def sheets_create(title: str, headers: list | None = None) -> str:
    """Create a new Google Spreadsheet, optionally with headers."""
    try:
        body: dict = {"properties": {"title": title}}
        if headers:
            body["sheets"] = [{"data": [{"rowData": [
                {"values": [{"userEnteredValue": {"stringValue": h}} for h in headers]}
            ]}]}]
        result = _svc().spreadsheets().create(body=body).execute()
        sid = result["spreadsheetId"]
        return f"Created '{title}'\nID: {sid}\nhttps://docs.google.com/spreadsheets/d/{sid}"
    except Exception as e:
        return _scope_err(e)


def _scope_err(e: Exception) -> str:
    msg = str(e).lower()
    if "insufficient" in msg or "permission" in msg or "403" in msg:
        return ("Sheets needs 'spreadsheets' scope. "
                "Re-run auth/google_oauth.py to grant it.")
    return f"Sheets error: {e}"
