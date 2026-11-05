"""Prepare a fresh unpatched control tree; never compile or run SUMO."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ST = Path('C:/Users/Ko_rr/AppData/Local/JDRT-native-build/choice_v126_20261019')
COMMIT = 'fa7df22d7f1c4ae245192ecc32410a49f1ffb2a3'
SOURCE = ST / ('sources/sumo-' + COMMIT)
TARGET = ST / 'sources/control126_20261020'
REPORT = ST / 'control_source_preparation_20261020.json'
REGISTERED = Path(__file__).parent / 'audit_history/walk_native_proposal_20261019/proposal_manifest.json'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


if TARGET.exists() or REPORT.exists():
    raise SystemExit('Control preparation already exists; preserve it')
proposal = json.loads(REGISTERED.read_bytes())
native = proposal['target']
if native != 'src/microsim/transportables/MSPModel_Striping.cpp' or sha(SOURCE / native) != proposal['proposed_sha256']:
    raise SystemExit('Unexpected registered native source')
archive_path = ST / ('downloads/sumo-' + COMMIT + '.zip')
with zipfile.ZipFile(archive_path) as archive:
    original = archive.read('sumo-' + COMMIT + '/' + native)
if hashlib.sha256(original).hexdigest() != proposal['official_before_sha256']:
    raise SystemExit('Official archive native source differs from registered base')
result = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'PREPARING',
          'source_commit': COMMIT, 'patched_source_root': str(SOURCE), 'control_source_root': str(TARGET),
          'archive_sha256': sha(archive_path), 'registered_proposal_sha256': sha(REGISTERED),
          'compiler_started': False, 'simulation_executed': False, 'core_ready': False}
try:
    # Extended paths avoid MAX_PATH when copying long upstream test/header names.
    source_long = Path('\\\\?\\' + str(SOURCE.resolve()))
    target_long = Path('\\\\?\\' + str(TARGET.resolve()))
    shutil.copytree(source_long, target_long, copy_function=shutil.copy2)
    (target_long / native).write_bytes(original)
    inventories = []
    for folder in (source_long, target_long):
        inventory = {}
        for path in folder.rglob('*'):
            if path.is_symlink() or path.is_junction():
                raise ValueError('Unexpected source-tree link')
            if path.is_file():
                inventory[path.relative_to(folder).as_posix()] = sha(path)
        inventories.append(inventory)
    if set(inventories[0]) != set(inventories[1]):
        raise ValueError('Copied source file sets differ')
    differences = [name for name in inventories[0] if inventories[0][name] != inventories[1][name]]
    if differences != [native]:
        raise ValueError('Control differs by more than the registered native patch')
    result.update(status='PREPARED_NOT_BUILT', file_count=len(inventories[0]),
                  source_sha256={'patched': inventories[0], 'control': inventories[1]},
                  differences=differences, shared_cmake_sha256=sha(target_long / 'src/CMakeLists.txt'))
except BaseException as error:
    result.update(status='FAILED_PRESERVED', error=repr(error))
    raise
finally:
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'report': str(REPORT), 'status': result['status'], 'files': result['file_count'],
                  'differences': result['differences']}, ensure_ascii=False))
