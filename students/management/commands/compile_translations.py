"""Compile every locale/*/LC_MESSAGES/django.po into .mo without gettext.

The build host has no `msgfmt`, so this implements the GNU MO writer directly
(msgid/msgstr tables, hash table left empty — gettext handles that fine).
Plural forms are supported; fuzzy entries and comments are skipped.

    python manage.py compile_translations           # compile all locales
    python manage.py compile_translations --check   # fail if a .mo is stale
"""
import struct
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


def parse_po(text):
    """Return [(msgid, msgstr)] from PO text; ignores comments/fuzzy entries."""
    entries = []
    msgid, msgstr = [], []
    mode = None
    fuzzy = False

    def flush():
        nonlocal msgid, msgstr, fuzzy
        # The header entry (empty msgid) MUST stay: gettext reads the charset
        # from it, otherwise UTF-8 msgstrs raise UnicodeDecodeError.
        if not fuzzy and "".join(msgstr) and (msgid or "Content-Type" in "".join(msgstr)):
            entries.append(("".join(msgid), "".join(msgstr)))
        msgid, msgstr, fuzzy = [], [], False

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            mode = None
            continue
        if line.startswith("#"):
            if "fuzzy" in line:
                fuzzy = True
            continue
        if line.startswith("msgid "):
            if msgstr:
                flush()
            mode = "id"
            msgid = [_unquote(line[6:])]
        elif line.startswith("msgstr "):
            mode = "str"
            msgstr = [_unquote(line[7:])]
        elif line.startswith("msgid_plural "):
            mode = "id"
            msgid.append(_unquote(line[13:]))
        elif line.startswith("msgstr["):
            mode = "str"
            msgstr.append(_unquote(line.split(" ", 1)[1]))
        elif line.startswith('"'):
            value = _unquote(line)
            (msgid if mode == "id" else msgstr).append(value)
    flush()
    return entries


def _unquote(value):
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    return (value.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
            .replace("\\t", "\t"))


def build_mo(entries):
    """GNU MO file bytes."""
    entries = sorted(entries)
    ids = b"".join(mid.encode("utf-8") + b"\x00" for mid, _ in entries)
    strs = b"".join(msg.encode("utf-8") + b"\x00" for _, msg in entries)
    count = len(entries)
    key_start = 7 * 4
    value_start = key_start + count * 8
    string_start = value_start + count * 8
    key_offsets, value_offsets = [], []
    offset = 0
    for mid, _ in entries:
        # gettext only recognises the metadata entry when the key length is 0
        # (CPython's GNU reader checks `mlen == 0`), so keep that quirk.
        key_offsets.append((len(mid.encode("utf-8")) + 1 if mid else 0, offset))
        offset += len(mid.encode("utf-8")) + 1
    offset = 0
    for _, msg in entries:
        value_offsets.append((len(msg.encode("utf-8")) + 1, offset))
        offset += len(msg.encode("utf-8")) + 1

    output = [struct.pack("Iiiiiii", 0x950412DE, 0, count, key_start, value_start, 0, 0)]
    for length, pos in key_offsets:
        output.append(struct.pack("ii", length, string_start + pos))
    for length, pos in value_offsets:
        output.append(struct.pack("ii", length, string_start + len(ids) + pos))
    # A trailing NUL keeps the last msgstr from ending exactly at EOF:
    # CPython's reader treats `offset + length == filesize` as corruption.
    return b"".join(output) + ids + strs + b"\x00"


class Command(BaseCommand):
    help = "Compile .po translation files into .mo (pure Python, no gettext needed)"

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true",
                            help="exit non-zero when a .mo is missing or older than its .po")

    def handle(self, *args, **options):
        locale_dirs = list(dict.fromkeys(
            [Path(p) for p in settings.LOCALE_PATHS] + [Path(settings.BASE_DIR) / "locale"]
        ))
        stale = []
        compiled = 0
        for locale_dir in locale_dirs:
            for po in sorted(locale_dir.glob("*/LC_MESSAGES/*.po")):
                mo = po.with_suffix(".mo")
                if options["check"]:
                    if not mo.exists() or mo.stat().st_mtime < po.stat().st_mtime:
                        stale.append(str(po))
                    continue
                entries = parse_po(po.read_text(encoding="utf-8"))
                mo.write_bytes(build_mo(entries))
                compiled += 1
                self.stdout.write(f"{po.relative_to(locale_dir)} -> {mo.name} ({len(entries)} strings)")
        if options["check"]:
            if stale:
                self.stderr.write("stale translations (run manage.py compile_translations):\n  "
                                  + "\n  ".join(stale))
                raise SystemExit(1)
            self.stdout.write("translations up to date")
            return
        self.stdout.write(self.style.SUCCESS(f"compiled {compiled} catalogue(s)"))
