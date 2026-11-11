"""Check seed reproducibility, changed layouts, presets and source integrity."""
import hashlib
import json
from pathlib import Path
from generator import ROOT, ROOM, LEVELS, generate, validate_scene

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

source_before=digest(ROOM)
results=[]
for level,counts in LEVELS.items():
    for seed in [705,706,20261110]:
        path,data=generate(seed,level)
        results.append(validate_scene(path))
        assert len(data['objects'])==sum(counts)
        first=data
        _,second=generate(seed,level)
        assert first==second, (level,seed,'not reproducible')
    if level!='clean':
        first=json.loads((ROOT/'scenes'/f'{level}_seed_705'/'objects.json').read_text())
        second=json.loads((ROOT/'scenes'/f'{level}_seed_706'/'objects.json').read_text())
        assert [r['center_world'] for r in first['objects']] != [r['center_world'] for r in second['objects']]
assert source_before==digest(ROOM), 'The original room was changed'
report={'cases':results,'deterministic_seed_replay':True,'different_seeds_change_positions':True,'original_room_unchanged':True,'source_usda_sha256':source_before}
(ROOT/'generator_validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
