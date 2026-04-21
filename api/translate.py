"""
Lyrics Translation — Multi-backend
------------------------------------
Backends (tried in order):
  1. argostranslate (offline, free, ~30 languages)
  2. LibreTranslate API (self-hosted or public, free)
  3. deep-translator / Google Translate (free, 100+ languages incl. Luganda)

Luganda (lg) is only supported by backend 3.
"""

import os
import json
import logging
from typing import Any, Optional

logger = logging.getLogger("wulira-translate")

# ── Backend availability ───────────────────────────────
_argos_ok = False
_deep_ok = False

try:
    import argostranslate.package
    import argostranslate.translate
    _argos_ok = True
except ImportError:
    pass

try:
    from deep_translator import GoogleTranslator
    _deep_ok = True
except ImportError:
    pass

LIBRE_URL = os.environ.get("LIBRETRANSLATE_URL", "")


def is_available() -> bool:
    return _argos_ok or _deep_ok or bool(LIBRE_URL)


def get_backends() -> list[str]:
    backends = []
    if _argos_ok:
        backends.append("argostranslate")
    if LIBRE_URL:
        backends.append("libretranslate")
    if _deep_ok:
        backends.append("google")
    return backends


def get_installed_languages() -> list[dict[str, str]]:
    langs: list[dict[str, str]] = []
    if _argos_ok:
        try:
            for l in argostranslate.translate.get_installed_languages():
                langs.append({"code": l.code, "name": l.name, "backend": "argos"})
        except Exception:
            pass
    if _deep_ok:
        # Google supports these + many more
        for code, name in [
            ("lg", "Luganda"), ("sw", "Swahili"), ("en", "English"),
            ("fr", "French"), ("es", "Spanish"), ("de", "German"),
            ("ar", "Arabic"), ("hi", "Hindi"), ("zh-CN", "Chinese"),
            ("ja", "Japanese"), ("ko", "Korean"), ("pt", "Portuguese"),
            ("yo", "Yoruba"), ("ha", "Hausa"), ("am", "Amharic"),
            ("rw", "Kinyarwanda"), ("so", "Somali"),
        ]:
            if not any(l["code"] == code for l in langs):
                langs.append({"code": code, "name": name, "backend": "google"})
    return langs


def get_available_pairs() -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    if _argos_ok:
        try:
            installed = argostranslate.translate.get_installed_languages()
            for src in installed:
                for tgt in installed:
                    if src != tgt and src.get_translation(tgt):
                        pairs.append({"from_code": src.code, "to_code": tgt.code, "backend": "argos"})
        except Exception:
            pass
    if _deep_ok:
        # Highlight the key Luganda pairs
        for src, tgt in [("lg", "en"), ("en", "lg"), ("sw", "en"), ("en", "sw")]:
            if not any(p["from_code"] == src and p["to_code"] == tgt for p in pairs):
                pairs.append({"from_code": src, "to_code": tgt, "backend": "google"})
    return pairs


def install_language_pair(from_code: str, to_code: str) -> bool:
    if not _argos_ok:
        return False
    try:
        argostranslate.package.update_package_index()
        available = argostranslate.package.get_available_packages()
        pkg = next((p for p in available if p.from_code == from_code and p.to_code == to_code), None)
        if not pkg:
            return False
        argostranslate.package.install_from_path(pkg.download())
        return True
    except Exception as e:
        logger.error(f"Install failed: {e}")
        return False


# ── Translation backends ───────────────────────────────

def _translate_argos(text: str, from_code: str, to_code: str) -> Optional[str]:
    if not _argos_ok:
        return None
    try:
        result = argostranslate.translate.translate(text, from_code, to_code)
        return result if result and result != text else None
    except Exception:
        return None


def _translate_libre(text: str, from_code: str, to_code: str) -> Optional[str]:
    if not LIBRE_URL:
        return None
    try:
        import urllib.request
        data = json.dumps({"q": text, "source": from_code, "target": to_code}).encode()
        req = urllib.request.Request(
            f"{LIBRE_URL}/translate",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
        return result.get("translatedText")
    except Exception as e:
        logger.debug(f"LibreTranslate failed: {e}")
        return None


def _translate_google(text: str, from_code: str, to_code: str) -> Optional[str]:
    if not _deep_ok:
        return None
    try:
        result = GoogleTranslator(source=from_code, target=to_code).translate(text)
        return result
    except Exception as e:
        logger.debug(f"Google translate failed: {e}")
        return None


def translate_text(text: str, from_code: str, to_code: str) -> Optional[str]:
    """Translate text using the best available backend."""
    if not text.strip():
        return text

    # Try each backend in order
    for fn in (_translate_argos, _translate_libre, _translate_google):
        result = fn(text, from_code, to_code)
        if result:
            return result
    return None


def translate_segments(
    segments: list[dict[str, Any]],
    from_code: str,
    to_code: str,
) -> list[dict[str, Any]]:
    """Translate all segments, preserving timestamps."""
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
