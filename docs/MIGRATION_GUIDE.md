# Migration Guide (No Compatibility Track)

## Removed Legacy Layout
- `app/view` -> `app/presentation/views`
- `app/repackage` -> `app/presentation/widgets`
- `app/resource` -> `app/presentation/resources`
- `utils` -> `app/infrastructure/*`
- `app/infra` -> `app/infrastructure`

## Runtime Data Relocation
- Old root runtime folders are replaced by:
  - `runtime/appdata`
  - `runtime/log`
  - `runtime/temp`
- Path constants are centralized in `app/infrastructure/runtime/paths.py`.

## Common Package Refactor
- Legacy `app/common` has been fully removed.
- Runtime/config/event/vision/logging capabilities are relocated to:
  - `app/infrastructure/config/*`
  - `app/infrastructure/runtime/*`
  - `app/infrastructure/events/*`
  - `app/infrastructure/vision/*`
  - `app/infrastructure/logging/*`
- Generic CPU capability is organized under `app/infrastructure/system/*`.
- Presentation-specific UI shared helpers are relocated to:
  - `app/presentation/shared/*`
- Tool-like helpers are relocated to:
  - `app/utils/*` (`network.py`, `updater.py`, `windows.py`, `vision.py`, `randoms.py`, `ui.py`)

## Task Orchestration Contracts
- Task metadata source: `app/application/tasks/task_registry.py`
- Daily policy: `app/application/tasks/daily_policy.py`
- Sequence defaults: `app/application/tasks/daily_defaults.py`
- Sequence serialization: `app/application/tasks/sequence_serializer.py`
- Daily orchestration helpers: `app/application/daily/orchestration.py`
- Daily state machine / thread lifecycle controller: `app/application/daily/controller.py`
- Daily settings/config use case: `app/application/daily/settings_usecase.py`
- Daily UI binding use case: `app/application/daily/ui_binding_usecase.py`
- Hotkey action routing: `app/application/hotkey/routing.py`
- Interface startup planning: `app/application/startup/interface_plan.py`
- Engine threads/scheduler: `app/core/task_engine/*`
- Global run-state bus: `app/core/event_bus/global_task_bus.py`

## UI Integration Rules
- `app/presentation/views/daily.py` and `app/presentation/views/additional_features.py` must consume centralized registry data.
- UI components should not import legacy paths.
- New feature modules are added under `app/modules/<name>/{usecase,ui}` and then registered once in `task_registry.py`.

## Verification Commands
- `python -m compileall app`
- `python -m py_compile SAA.py`
- `python scripts/smoke_release.py`
- `python scripts/release_cleanup_pack.py`
