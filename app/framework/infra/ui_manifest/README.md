# UI Resources Quick Guide

## Authoring (module code)
- Keep native usage:
  - `self.auto.click(U("开始", id="start", roi=(0.1, 0.2, 0.3, 0.4)))`
  - `self.auto.click("start")`
- No extra author-facing DSL is required.

## Manifest files
- Human-edited source: `app/features/modules/<module>/assets/ui.json`
- Generated runtime view: `app/features/modules/<module>/assets/ui.generated.json`
- Runtime is read-only. Update generated data via `scripts/ui_sync.py --write`.

## ui.json fields
- `text`: localized display text (human-edit first)
- `image`: image path by id
- `position`: ROI/position object
  - Common edit fields: `x`, `y`, `w`, `h`
  - Advanced fields: `anchor`, `base_resolution`
- `match`: threshold/include/need_ocr/find_type defaults and per-id overrides
- `_meta`: technical metadata; usually do not edit manually

## Typical workflow
1. Edit `ui.json` (`text` / `image` / `position`).
2. Run `python scripts/ui_sync.py --write`.
3. Validate with `python scripts/ui_sync.py --audit`.

## Safety checks in report
- new definitions
- stale entries
- duplicate ids
- conflicting defaults
- locale gaps
- missing assets
- unresolved references
- ROI drift

