"""
tools/google_contacts_tool.py — Google Contacts via People API.
Requires 'contacts.readonly' scope.
"""


def _svc():
    from tools.google_auth import get_service
    return get_service("people", "v1")


def contacts_search(name: str) -> str:
    """Search contacts by name. Returns name + email + phone."""
    try:
        result = _svc().people().searchContacts(
            query=name,
            readMask="names,emailAddresses,phoneNumbers",
        ).execute()
        people = result.get("results", [])
        if not people:
            return f"No contacts found for '{name}'."
        lines = []
        for p in people[:5]:
            person = p.get("person", {})
            display = (person.get("names") or [{}])[0].get("displayName", "Unknown")
            emails = [e["value"] for e in person.get("emailAddresses", [])]
            phones = [ph["value"] for ph in person.get("phoneNumbers", [])]
            parts = [display]
            if emails:
                parts.append(emails[0])
            if phones:
                parts.append(phones[0])
            lines.append(" — ".join(parts))
        return "\n".join(lines)
    except Exception as e:
        return _scope_err(e)


def contacts_get_email(name: str) -> str:
    """Get the primary email address for a contact by name."""
    try:
        result = _svc().people().searchContacts(
            query=name, readMask="names,emailAddresses"
        ).execute()
        for p in result.get("results", []):
            person = p.get("person", {})
            emails = person.get("emailAddresses", [])
            if emails:
                return emails[0]["value"]
        return f"No email found for '{name}' in your contacts."
    except Exception as e:
        return _scope_err(e)


def contacts_list_frequent() -> str:
    """List recently modified contacts."""
    try:
        result = _svc().people().connections().list(
            resourceName="people/me",
            personFields="names,emailAddresses",
            pageSize=10,
            sortOrder="LAST_MODIFIED_DESCENDING",
        ).execute()
        people = result.get("connections", [])
        if not people:
            return "No contacts found."
        lines = []
        for p in people:
            display = (p.get("names") or [{}])[0].get("displayName", "Unknown")
            emails = [e["value"] for e in p.get("emailAddresses", [])]
            lines.append(f"{display}" + (f" — {emails[0]}" if emails else ""))
        return "\n".join(lines)
    except Exception as e:
        return _scope_err(e)


def _scope_err(e: Exception) -> str:
    msg = str(e).lower()
    if "insufficient" in msg or "permission" in msg or "403" in msg:
        return ("Contacts needs the 'contacts.readonly' scope. "
                "Re-run auth/google_oauth.py to grant it.")
    return f"Contacts error: {e}"
