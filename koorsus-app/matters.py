import json
import os
from datetime import datetime

REGISTRY_PATH = '/home/jeeves/arkiv/instance/matters.json'

def _load():
    if not os.path.exists(REGISTRY_PATH):
        return {}
    try:
        with open(REGISTRY_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def _save(data):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, 'w') as f:
        json.dump(data, f, indent=2)

def register_matter(tag):
    """Called on ingest to ensure the matter exists in the registry."""
    data = _load()
    if tag not in data:
        data[tag] = {
            'status': 'active',
            'opened_at': datetime.now().isoformat(),
            'last_query_at': None
        }
        _save(data)

def touch_matter(tag):
    """Called on query to update the 'last active' timestamp."""
    if not tag:
        return
    data = _load()
    if tag in data:
        data[tag]['last_query_at'] = datetime.now().isoformat()
        _save(data)

def archive_matter(tag, archived=True):
    data = _load()
    if tag in data:
        data[tag]['status'] = 'archived' if archived else 'active'
        _save(data)

def get_matters(include_archived=False):
    """Returns a list of matters sorted by most recently queried."""
    from rag import store
    data = _load()
    chroma_matters = store.matters()
    
    # Auto-register any matters found in ChromaDB that aren't in the registry yet
    changed = False
    for m in chroma_matters:
        if m['tag'] not in data:
            data[m['tag']] = {
                'status': 'active',
                'opened_at': datetime.now().isoformat(),
                'last_query_at': None
            }
            changed = True
    if changed:
        _save(data)
    
    out = []
    for tag, info in data.items():
        if not include_archived and info['status'] == 'archived':
            continue
        count = next((m['count'] for m in chroma_matters if m['tag'] == tag), 0)
        out.append({
            'tag': tag,
            'count': count,
            'status': info['status'],
            'last_query_at': info.get('last_query_at')
        })
    
    # Sort: recently queried first. If never queried, sort A to Z.
    out.sort(key=lambda x: (
        x['last_query_at'] is not None,
        x['last_query_at'] or '',
        x['tag'].lower()
    ), reverse=True)
    return out
