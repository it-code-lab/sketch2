from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

PROFILE_FILE = 'user_profiles.json'
VALID_KEY = re.compile(r'[^a-zA-Z0-9_\- ]+')


def sanitize_profile_name(name: str) -> str:
    name = (name or '').strip()
    name = VALID_KEY.sub('', name)
    return name[:80].strip()


def profile_path(root: Path) -> Path:
    return root / PROFILE_FILE


def _load(root: Path) -> dict[str, Any]:
    path = profile_path(root)
    if not path.exists():
        return {'profiles': {}}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict) and isinstance(data.get('profiles'), dict):
            return data
    except Exception:
        pass
    return {'profiles': {}}


def _save(root: Path, data: dict[str, Any]) -> None:
    profile_path(root).write_text(json.dumps(data, indent=2), encoding='utf-8')


def list_profiles(root: Path) -> list[dict[str, Any]]:
    data = _load(root)
    profiles = []
    for name, payload in data.get('profiles', {}).items():
        profiles.append({
            'name': name,
            'updated': payload.get('updated', 0),
            'notes': payload.get('notes', ''),
        })
    return sorted(profiles, key=lambda x: (x.get('updated', 0), x.get('name', '')), reverse=True)


def get_profile(root: Path, name: str) -> dict[str, Any] | None:
    name = sanitize_profile_name(name)
    data = _load(root)
    payload = data.get('profiles', {}).get(name)
    if not payload:
        return None
    return {'name': name, **payload}


def save_profile(root: Path, name: str, settings: dict[str, Any], notes: str = '') -> dict[str, Any]:
    name = sanitize_profile_name(name)
    if not name:
        raise ValueError('Profile name is required.')
    data = _load(root)
    profile = {
        'settings': settings,
        'notes': (notes or '')[:300],
        'updated': int(time.time()),
    }
    data.setdefault('profiles', {})[name] = profile
    _save(root, data)
    return {'name': name, **profile}


def delete_profile(root: Path, name: str) -> bool:
    name = sanitize_profile_name(name)
    data = _load(root)
    if name in data.get('profiles', {}):
        del data['profiles'][name]
        _save(root, data)
        return True
    return False
