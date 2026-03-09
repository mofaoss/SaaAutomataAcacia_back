# SaaAssistantAca Architecture (Final, Single-Track)

## Layering
- `app/presentation`: Qt pages/widgets/resources, only UI rendering and intent binding.
- `app/application`: task orchestration policies, task registry, sequence defaults/serialization.
- `app/core`: kernel capabilities (`task_engine`, `event_bus`, `config`, `observability`).
- `app/infrastructure`: external/technical adapters (`automation`, `config`, `runtime`, `events`, `vision`, `logging`).
- `app/modules`: vertical feature slices (`usecase` + `ui`).
- `app/utils`: generic utility helpers (text normalization, item mapping utilities).

## Key Rules
- UI layer does not directly own thread lifecycle; runtime execution goes through `app/core/task_engine`.
- Cross-page run-state coordination goes through `app/core/event_bus/global_task_bus.py`.
- Task metadata is centralized in `app/application/tasks/task_registry.py`.
- Old paths (`app/view`, `app/repackage`, `app/resource`, `utils`, `app/infra`) are fully removed.

## Application Layer Role
- `app/application` is the orchestration boundary, not a utility bucket.
- It owns use-case flow, state transitions, run planning, and cross-module coordination.
- `app/application/daily/controller.py` is the single entry for daily run state machine and thread lifecycle decisions.
- `app/presentation` only emits user intent and renders state.

## Core Runtime Paths
- Runtime root: `runtime/`
- Config/data: `runtime/appdata/`
- Logs: `runtime/log/`
- Temp files: `runtime/temp/`

## Module Contract
- Module directory shape:
  - `app/modules/<module>/usecase/`
  - `app/modules/<module>/ui/`
- Modules are registered once in task registry and consumed by presentation/application layers.

## Current Migration Status
- Presentation split finished: views/widgets/resources moved to `app/presentation/*`.
- Infrastructure split finished: generic adapters moved to `app/infrastructure/*` (no `infra/common` subpackage, no flat `*_utils.py`).
- Project-scoped helpers are moved to `app/utils/*` (`network.py`, `updater.py`, `windows.py`, `vision.py`, `randoms.py`, `ui.py`).
- Legacy `app/common` package is fully removed.
- Registry-based daily/additional task source is active.
- Scheduler and thread engine are centralized in `app/core/task_engine`.
- Daily orchestration helpers are extracted to `app/application/daily/orchestration.py`.
- Daily state machine and thread lifecycle are extracted to `app/application/daily/controller.py`.
- Daily settings/config persistence and UI binding wiring are extracted to `app/application/daily/settings_usecase.py` and `app/application/daily/ui_binding_usecase.py`.
- Hotkey routing policy is extracted to `app/application/hotkey/routing.py`.
- Startup interface load plan is extracted to `app/application/startup/interface_plan.py`.
