import hashlib
from pathlib import Path
import re

IGNORE_SUFFIXES = {".py"}
NUM_PREFIX_RE = re.compile(r"^\d+_")  # matches leading numbers + underscore

def normalize_filename(path):
    """
    Returns the filename normalized for comparison:
    - numeric prefix removed
    - lowercase
    """
    filename = path.name
    filename = NUM_PREFIX_RE.sub("", filename)
    return filename.lower()

def file_hash(path, chunk_size=8192):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()

script_dir = Path(__file__).resolve().parent
other_dir = Path(r"C:\Users\Max\Desktop\rwBSP_test\banquet")

def collect_files(base):
    files = {}
    for p in base.rglob("*"):
        if p.is_file() and p.suffix.lower() not in (s.lower() for s in IGNORE_SUFFIXES):
            norm_name = normalize_filename(p)
            files[norm_name] = p
    return files

files_a = collect_files(script_dir)
files_b = collect_files(other_dir)

all_names = set(files_a) | set(files_b)

changed_dff_count = 0
for name in sorted(all_names):
    a = files_a.get(name)
    b = files_b.get(name)

    # filename-wise difference
    if a is None:
        print(f"FILENAME  | only in other   | {b}")
        continue
    if b is None:
        print(f"FILENAME  | only in script  | {a}")
        continue

    # content-wise difference
    if file_hash(a) != file_hash(b):
        print(f"CONTENT   | {a}  !=  {b}")
        if a.suffix.lower() == ".dff":
            changed_dff_count += 1
        

print(f"Total .dff files in script directory: {sum(1 for p in script_dir.rglob('*.dff') if p.is_file())}")
print("chaged .dff files:", changed_dff_count)