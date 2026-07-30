"""The declared French normalisation rule for deterministic search (Story 3.2 / AD-21).

The deterministic engine proves an absence, so a term must be found *by a defined, tested rule* and
not by accident — opposing counsel needs the one document where the word appears with an accent the
OCR dropped. This rule is **recall-first**: it FOLDS variants so a query for ``etat`` finds
``l'État``
in the text. Search is then containment of ``normalize(query)`` in ``normalize(text)``.

The rule (``fr-fold-v1``), applied identically to the query and the stored text:

1. expand the ``œ``/``æ`` ligatures (NFKD leaves them intact) → ``oe``/``ae``;
2. NFKD-decompose and strip combining marks — fold diacritics (``État`` → ``etat``);
3. case-fold;
4. join a hyphen immediately before a line break — scanned-line-break hyphenation (``bail-\nleur``
   → ``bailleur``); a real hyphen (``porte-fenetre``) is kept;
5. turn the elision apostrophe into a space so the elided word stands alone (``l'état`` →
   ``l etat``,
   found by a containment search for ``etat``);
6. collapse whitespace.

The applied rule's identity (``NORMALIZATION``) is declared on every result set (AD-21). The
expression grammar (boolean / proximity / wildcard) that AD-21 also makes configuration-as-data is
a later tuning; 3.2's default is exact normalised containment.
"""

from __future__ import annotations

import re
import unicodedata

NORMALIZATION = "fr-fold-v1"

_LIGATURES = str.maketrans({"œ": "oe", "Œ": "oe", "æ": "ae", "Æ": "ae"})
_APOSTROPHES = "'’ʼʹ`´"        # ' ' ʼ ʹ ` ´
_LINE_BREAK_HYPHEN = re.compile(r"-\s*\n\s*")      # a hyphen just before a scanned line break
_WHITESPACE = re.compile(r"\s+")
_APOSTROPHE_RUN = re.compile(f"[{re.escape(_APOSTROPHES)}]")


def normalize(text: str) -> str:
    """Fold ``text`` to its normalised search form (``fr-fold-v1``). Deterministic; recall-first."""
    s = text.translate(_LIGATURES)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold()
    s = _LINE_BREAK_HYPHEN.sub("", s)              # join a scanned line break (keep real hyphens)
    s = _APOSTROPHE_RUN.sub(" ", s)                # the elided word stands alone
    return _WHITESPACE.sub(" ", s).strip()
