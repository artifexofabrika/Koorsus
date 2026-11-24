import os
import re
import sys

# 1. Read the combined file
src_path = os.path.expanduser('~/arkiv/demo_corpus.txt')
dest_dir = os.path.expanduser('~/arkiv/demo_corpus')
os.makedirs(dest_dir, exist_ok=True)

with open(src_path, 'r', encoding='utf-8-sig', errors='replace') as f:
    text = f.read()

# 2. Find all FILE markers
# Format: === FILE: filename.txt ===
pattern = re.compile(r'^=== FILE:\s*(.+?)\s*===\s*$', re.MULTILINE)
matches = list(pattern.finditer(text))
print(f"Found {len(matches)} FILE markers.")

if len(matches) != 113:
    print(f"ERROR: Expected 113 markers, found {len(matches)}. Aborting.")
    sys.exit(1)

# 3. Extract each document
files_written = []
for i, m in enumerate(matches):
    filename = m.group(1).strip()
    start = m.end()
    end = matches[i+1].start() if i+1 < len(matches) else len(text)
    content = text[start:end]

    # Strip the trailing === END FILE === marker if present
    end_marker = re.compile(r'^=== END FILE ===\s*$', re.MULTILINE)
    em = end_marker.search(content)
    if em:
        content = content[:em.start()]

    content = content.strip()
    if not content:
        print(f"WARNING: {filename} is empty.")
        continue

    out_path = os.path.join(dest_dir, filename)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)
    files_written.append(filename)

print(f"Wrote {len(files_written)} files to {dest_dir}")

# 4. Parse the manifest
manifest = {}
manifest_start = text.find('=== MANIFEST ===')
if manifest_start == -1:
    print("ERROR: No manifest block found. Aborting.")
    sys.exit(1)
manifest_block = text[manifest_start:]
for line in manifest_block.splitlines():
    line = line.strip()
    if '|' in line and line.startswith('matter_'):
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 2:
            manifest[parts[0]] = {'tag': parts[1], 'case': parts[2] if len(parts) > 2 else ''}

print(f"Manifest contains {len(manifest)} matters.")

# 5. Ingest each file
sys.path.insert(0, '/home/jeeves/arkiv')
from rag.ingest import ingest_file

total_chunks = 0
ingested = 0
failed = []

for filename in sorted(files_written):
    m = re.match(r'(matter_\d+)', filename)
    if not m:
        print(f"SKIP (no matter prefix): {filename}")
        continue
    matter_key = m.group(1)
    info = manifest.get(matter_key)
    if not info:
        failed.append(filename + " (no manifest entry)")
        continue

    tag = info['tag']
    filepath = os.path.join(dest_dir, filename)
    try:
        n = ingest_file(filepath, source_name=filename, extra_metadata={'tag': tag, 'uploader': 'demo'})
        total_chunks += n
        ingested += 1
        if ingested % 10 == 0:
            print(f"  {ingested}/{len(files_written)} files ingested, {total_chunks} chunks so far.")
    except Exception as e:
        failed.append(filename + " (" + str(e) + ")")

print(f"\nDONE: {ingested} files ingested, {total_chunks} total chunks.")
if failed:
    print(f"FAILED ({len(failed)}):")
    for f in failed:
        print(f"  {f}")

# 6. Register matters
try:
    import matters
    for key, info in manifest.items():
        matters.register_matter(info['tag'])
    print(f"Registered {len(manifest)} matters in the registry.")
except Exception as e:
    print(f"WARN: Could not register matters: {e}")
