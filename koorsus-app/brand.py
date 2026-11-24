"""Instance identity. One codebase, several products.

Defaults are Arkiv. A systemd drop-in overrides these for another product,
so no fork and no second copy of the code to maintain.
"""
import os

BRAND = os.environ.get("ARKIV_BRAND", "Arkiv")
TAGLINE = os.environ.get("ARKIV_TAGLINE",
                         "Your firm's private document assistant")
PORT = int(os.environ.get("ARKIV_PORT", "5001"))
DATA_ROOT = os.environ.get("ARKIV_DATA_ROOT", "/mnt/lake")
BACKUP_ROOT = os.environ.get("ARKIV_BACKUP_ROOT", "/mnt/arkiv-backup")
INDEX_NAME = os.environ.get("ARKIV_INDEX_NAME", "arkiv_index")


def mark():
    """The brand with its first letter accented, matching existing markup."""
    return '<span class="accent">' + BRAND[0] + "</span>" + BRAND[1:]
