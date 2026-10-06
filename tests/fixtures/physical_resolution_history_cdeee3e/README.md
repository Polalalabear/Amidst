# Historical physical-resolution config fixtures

The files under `configs/` are exact byte copies of their original repository paths
at `cdeee3e316e88c87ab63cdcf3acb360485f00dd6`. They preserve the historical input
bindings in `data/scene_audit/phase1_physical_authority_20261006/manifest.json` while
active configs continue to evolve. The unit regression compares each fixture's
SHA-256 against that unchanged manifest and needs no Git history or local camera
calibration. The ignored historical camera artifact is checked separately when
explicitly provisioned; tests never generate or download it.
