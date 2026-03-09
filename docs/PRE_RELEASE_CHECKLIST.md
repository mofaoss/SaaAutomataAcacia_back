# Pre-Release Checklist

## Architecture
- [ ] No references to legacy `app/common/*`
- [ ] No references to `signalBus.globalTaskStateChanged/globalStopRequest`
- [ ] Daily and additional tasks read from centralized registry

## Code Health
- [ ] `python -m compileall app` passes
- [ ] `python -m py_compile SAA.py` passes
- [ ] No unresolved imports in touched modules

## Runtime Smoke
- [ ] `python scripts/release_cleanup_pack.py` passes
- [ ] Report exists: `release/preflight_report.md`
- [ ] `python scripts/smoke_release.py` passes (optional secondary check)

## Manual Sanity
- [ ] Main window opens
- [ ] `F8` start/stop works for daily
- [ ] Additional task start/stop updates global state correctly
- [ ] App can exit from tray menu
