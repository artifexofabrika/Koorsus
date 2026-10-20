"""
keychain.py – Single source of truth for API credentials.
Reads and writes ~/api_keys.json. All other modules should use this.
"""
import json
import os

KEYCHAIN_PATH = os.path.expanduser("~/api_keys.json")

def _read():
    """Return the list of credential entries, or an empty list."""
    if not os.path.exists(KEYCHAIN_PATH):
        return []
    try:
        with open(KEYCHAIN_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

def _write(entries):
    """Write the list of credential entries to disk."""
    with open(KEYCHAIN_PATH, "w") as f:
        json.dump(entries, f, indent=2)

def load(module):
    """
    Return the LAST saved key, secret, and passphrase for a given module.
    module: 'Crypto', 'Stocks', 'Wellness', 'Email', etc.
    Returns a dict with keys 'key', 'secret', 'passphrase', or all empty strings if not found.
    """
    entries = _read()
    last = {}
    for e in entries:
        if e.get("module", "").lower() == module.lower():
            last = e
    return {
        "key": last.get("key", ""),
        "secret": last.get("secret", ""),
        "passphrase": last.get("passphrase", ""),
    }

def save(label, module, key, secret, passphrase=""):
    """
    Upsert a credential entry. If an entry with the same label exists, update it.
    Otherwise append a new entry.
    """
    entries = _read()
    new_entry = {
        "label": label,
        "module": module,
        "key": key,
        "secret": secret,
        "passphrase": passphrase,
    }
    for i, e in enumerate(entries):
        if e.get("label", "") == label:
            entries[i] = new_entry
            _write(entries)
            return
    entries.append(new_entry)
    _write(entries)

def delete(label):
    """Remove the entry with the given label, if it exists."""
    entries = _read()
    entries = [e for e in entries if e.get("label", "") != label]
    _write(entries)

def list_all():
    """Return all saved entries (for dashboard display)."""
    return _read()
