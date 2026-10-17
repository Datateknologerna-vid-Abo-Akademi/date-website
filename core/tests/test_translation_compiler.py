"""The .po compiler used by the test settings has to agree with msgfmt.

`core.settings.test` compiles the catalogs with `core.translation_compiler` on
import, so a dev or test tree reads what that compiler produced rather than what
`manage.py compilemessages` would have produced. The entries it used to get wrong
were the contextual and the plural ones, which is why this file pins both, and
compares the whole catalog against msgfmt when gettext is installed.
"""

from __future__ import annotations

import gettext
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from django.test import SimpleTestCase

from core.translation_compiler import compile_po_to_mo

PO = '''msgid ""
msgstr ""
"Project-Id-Version: date-website\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"

#: attendance/models.py:65
msgctxt "singular"
msgid "närvaroevenemang"
msgstr "läsnäolotapahtuma"

#: templates/common/attendance/index.html:9
msgid "Närvaroevenemang"
msgstr "Närvaroevenemang"

#: attendance/models.py:184
msgid "deltagare"
msgid_plural "deltagare"
msgstr[0] "deltagare"
msgstr[1] "deltagare"

#: attendance/models.py:99
#, fuzzy
msgid "Osäker sträng"
msgstr "Osäker sträng"

#: attendance/models.py:120
msgid ""
"En sträng som "
"är delad"
msgstr ""
"En översättning som "
"är delad"

#~ msgid "Borttagen"
#~ msgstr "Borttagen"
'''


class TranslationCompilerTests(SimpleTestCase):
    def compile(self, po_text: str = PO) -> tuple[dict, Path, Path]:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        po_path = directory / "django.po"
        po_path.write_text(po_text, encoding="utf-8")
        mo_path = directory / "django.mo"

        compile_po_to_mo(po_path, mo_path)

        return self.catalog(mo_path), po_path, mo_path

    @staticmethod
    def catalog(mo_path: Path) -> dict:
        """The parsed catalog, keyed the way a reader looks entries up.

        `_catalog` is private, and this is the only way to see what a compiled
        catalog actually resolves to.
        """
        with mo_path.open("rb") as handle:
            return gettext.GNUTranslations(handle)._catalog  # type: ignore[attr-defined]

    def test_a_contextual_entry_keeps_its_context(self):
        catalog, _po, _mo = self.compile()

        # The context is part of the key, so the plain msgid keeps its own value
        # and the contextual one is not reachable without it.
        self.assertEqual(catalog["singular\x04närvaroevenemang"], "läsnäolotapahtuma")
        self.assertEqual(catalog["Närvaroevenemang"], "Närvaroevenemang")

    def test_a_plural_entry_keeps_every_form(self):
        catalog, _po, _mo = self.compile()

        # Python's gettext keys plural entries as (msgid, form index).
        self.assertEqual(catalog[("deltagare", 0)], "deltagare")
        self.assertEqual(catalog[("deltagare", 1)], "deltagare")

    def test_fuzzy_entries_are_left_out_and_the_header_is_kept(self):
        catalog, _po, _mo = self.compile()

        self.assertNotIn("Osäker sträng", catalog)
        # The header carries the charset, and makemessages marks it fuzzy.
        self.assertIn("", catalog)

    def test_multiline_values_are_joined(self):
        catalog, _po, _mo = self.compile()

        self.assertEqual(catalog["En sträng som är delad"], "En översättning som är delad")

    def test_obsolete_entries_are_left_out(self):
        catalog, _po, _mo = self.compile()

        self.assertNotIn("Borttagen", catalog)

    @unittest.skipUnless(shutil.which("msgfmt"), "gettext is not installed")
    def test_the_catalog_matches_what_msgfmt_produces(self):
        ours, po_path, _mo = self.compile()
        theirs_path = po_path.with_name("msgfmt.mo")

        subprocess.run(["msgfmt", "-o", str(theirs_path), str(po_path)], check=True)

        self.assertEqual(ours, self.catalog(theirs_path))
