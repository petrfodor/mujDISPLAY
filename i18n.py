# i18n.py
"""Načítání překladů a poskytování lokalizovaných textů."""

import json
import os
from threading import Lock

_translations = {}
_current_lang = 'CZ'
_lock = Lock()

LANGUAGES = ['CZ', 'SK', 'EN', 'DE', 'FR']

def load_language(lang):
    global _translations, _current_lang
    file_path = os.path.join(os.path.dirname(__file__), 'lang', f'{lang.lower()}.json')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            _translations = json.load(f)
        _current_lang = lang
    except FileNotFoundError:
        fallback = os.path.join(os.path.dirname(__file__), 'lang', 'en.json')
        if os.path.exists(fallback):
            with open(fallback, 'r', encoding='utf-8') as f:
                _translations = json.load(f)
        else:
            _translations = {}
        _current_lang = 'EN'

def _(key, **kwargs):
    with _lock:
        text = _translations.get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text

def get_current_lang():
    return _current_lang
