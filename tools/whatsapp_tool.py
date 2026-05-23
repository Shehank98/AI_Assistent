"""
tools/whatsapp_tool.py — WhatsApp messaging via pywhatkit.
DESKTOP ONLY — requires WhatsApp Web logged in on the machine's browser.
Excluded on Railway (DESKTOP_MODE env var must be "true" to activate).

Note: pywhatkit works by opening WhatsApp Web in a browser and simulating keypresses.
It will NOT work on a headless server (Railway). Use DESKTOP_MODE=true locally only.
"""

import json
import os
from pathlib import Path

CONTACTS_FILE = Path.home() / ".jarvis" / "contacts.json"


def _load_contacts() -> dict:
    if CONTACTS_FILE.exists():
        return json.loads(CONTACTS_FILE.read_text())
    return {}


def whatsapp_send(phone_number: str, message: str) -> str:
    """
    Send a WhatsApp message to a phone number (international format, e.g. +94771234567).
    DESKTOP ONLY — requires WhatsApp Web logged in in your browser.
    """
    try:
        import pywhatkit as pwk
        # wait_time=15 gives WhatsApp Web time to load
        pwk.sendwhatmsg_instantly(phone_number, message, wait_time=15, tab_close=True)
        return f"WhatsApp message sent to {phone_number}."
    except ImportError:
        return "pywhatkit not installed. Run: pip install pywhatkit"
    except Exception as e:
        return f"WhatsApp error: {e}"


def whatsapp_send_to_contact(name: str, message: str) -> str:
    """
    Send a WhatsApp message to a saved contact by name.
    Contacts stored in ~/.jarvis/contacts.json as {"Name": "+94771234567"}.
    """
    contacts = _load_contacts()
    # Case-insensitive match
    match = None
    for contact_name, number in contacts.items():
        if name.lower() in contact_name.lower():
            match = (contact_name, number)
            break

    if not match:
        available = ", ".join(contacts.keys()) if contacts else "none saved"
        return (
            f"Contact '{name}' not found.\n"
            f"Available: {available}\n"
            f"To add contacts, edit {CONTACTS_FILE}"
        )

    return whatsapp_send(match[1], message)
