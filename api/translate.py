"""
Lyrics Translation
-------------------
Translate lyrics between languages using argostranslate (offline, free).
Falls back to a simple placeholder if argostranslate is not installed.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("wulira-translate")

# Supported translation pairs (argostranslate)
SUPPORTED_PAIRS: dict[str, list[str]] = {}
_argos_available = False

try:
    import argostranslate.package
    import argostranslate.translate
    _argos_available = True
except ImportError:
    pass


def is_available() -> bool:
    return _argos_available


def get_installed_languages() -> list[dict[str, str]]:
    """List installed translation languages."""
    if not _argos_available:
        return []
    try:
        langs = argostranslate.translate.get_installed_languages()
        return [{"code": l.code, "name": l.name} for l in langs]
    except Exception:
        return []


def get_available_pairs() -> list[dict[str, str]]:
    """List available source→target translation pairs."""
    if not _argos_available:
        return []
    try:
        langs = argostranslate.translate.get_installed_languages()
        pairs = []
        for src in langs:
            for tgt in langs:
                if src != tgt:
                    t = src.get_translation(tgt)
                    if t:
                        pairs.append({
                            "from_code": src.code,
                            "from_name": src.name,
                            "to_code": tgt.code,
                            "to_name": tgt.name,
                        })
        return pairs
    except Exception:
        return []


def install_language_pair(from_code: str, to_code: str) -> bool:
    """Download and install a translation package."""
    if not _argos_available:
        return False
    try:
        argostranslate.package.update_package_index()
        available = argostranslate.package.get_available_packages()
        pkg = next(
            (p for p in available if p.from_code == from_code and p.to_code == to_code),
            None,
        )
        if not pkg:
            logger.warning(f"No package for {from_code}→{to_code}")
            return False
        argostranslate.package.install_from_path(pkg.download())
        logger.info(f"Installed translation: {from_code}→{to_code}")
        return True
    except Exception as e:
        logger.error(f"Failed to install {from_code}→{to_code}: {e}")
        return False


def translate_text(text: str, from_code: str, to_code: str) -> Optional[str]:
    """Translate a single text string."""
    if not _argos_available:
        return None
    try:
        return argostranslate.translate.translate(text, from_code, to_code)
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return None


def translate_segments(
    segments: list[dict[str, Any]],
    from_code: str,
    to_code: str,
) -> list[dict[str, Any]]:
    """Translate all segments, preserving timestamps."""
    if not _argos_available:
        return segments

    translated = []
    for seg in segments:
        original = seg.get("text", "")
        result = translate_text(original, from_code, to_code)
        translated.append({
            **seg,
            "text": result or original,
            "original_text": original,
            "translated": result is not None,
        })
    return translated
