# AI Develop Guidance (One-Shot Version)

This file is designed for one-shot AI execution.
The user only needs to fill the **User Input Section**, then press `Ctrl+A` and send the entire page to an AI/Agent.

```text
==================== Complete Instruction Packet for AI (Ready to Execute) ====================

You are implementing a PC automation module for "Snowbreak: Containment Zone" in the SAA project.
Follow this packet strictly. Do not invent extra protocols.

[Hard Constraints - Mandatory]
1) Mouse click actions must use: auto.move_click(...)
   - Do NOT use auto.click_element(...) as the final click action.
2) Modules use declarative protocol: @module(...) directly on the class.
   - Wrapper pattern is not allowed: def run_task_xxx(...): return Xxx(...).run()
3) Module entry shape is fixed:
   - class XxxTask:
   - __init__(self, auto, logger)
   - run(self)
4) Every loop must include timeout (Timer) + exit condition. Infinite loops are forbidden.
5) Read config only from config.xxx.value, not directly from UI widgets.

[Project Architecture Snapshot]
1) app/framework: general capabilities (core/application/infra/ui)
2) app/features: business capabilities (modules/assets/bootstrap/utils)
3) Module discovery: framework/core/module_system/discovery.py scans app.features.modules.*.usecase.*_usecase

-------------------- User Input Section (Only fill this section) --------------------

Filling rules (time-saving):
- Use [y] for checked, [ ] for unchecked.
- For most fields, write natural language directly (no need for extra checkboxes).
- If a field is blank, AI must apply defaults and continue.

1) Basic Info
- Module Display Name (CN):
- Module Display Name (EN, optional):
- Goal (one sentence):

2) Module Type (choose one)
- [ ] periodic (scheduled task)
- [ ] on_demand (manually triggered task)
- [ ] unsure (let AI decide)

3) Page Entry (multiple allowed)
- [ ] mount on periodic page
- [ ] mount on on_demand page
- [ ] passive toggle (persistent helper)

4) Resolution Confirmation (required)
- Current game resolution (e.g. 1920x1080):
- Is aspect ratio 16:9:
  - [ ] yes
  - [ ] no
  - [ ] unsure

5) Preconditions
- Return to home first:
  - [ ] yes
  - [ ] no
- Must enter a specific screen first (optional, write screen name):

6) Process Steps (default 3, add Step4/Step5 if needed)
- Step1
  - Recognition method (optional, free text):
    - Examples: OCR text / image match / color block / unsure
  - Recognition target (free text, AI auto-detects text vs image):
    - Example: Start Battle
    - Example: start_btn.png (usually means image resource is needed)
  - Region (optional):
    - Blank / unchecked / invalid format => full screen by default
    - If specified, write: x1,y1,x2,y2
  - Threshold (optional, default 0.7):
  - Action (write one natural language sentence):
    - Example: press key F
    - Example: hold key A for 5 seconds
    - Example: click 960,540
    - Example: wait 1.2 seconds
    - Example: swipe down 300 pixels
- Step2
  - Recognition method (optional, free text):
  - Recognition target (free text, AI auto-detects text vs image):
    - Example: Confirm
    - Example: confirm_btn.png (usually means image resource is needed)
  - Region (optional):
    - Blank / unchecked / invalid format => full screen by default
    - If specified, write: x1,y1,x2,y2
  - Threshold (optional, default 0.7):
  - Action (write one natural language sentence):
- Step3
  - Recognition method (optional, free text):
  - Recognition target (free text, AI auto-detects text vs image):
    - Example: Complete
    - Example: finish_flag.png (usually means image resource is needed)
  - Region (optional):
    - Blank / unchecked / invalid format => full screen by default
    - If specified, write: x1,y1,x2,y2
  - Threshold (optional, default 0.7):
  - Action (write one natural language sentence):

7) Retry & Timeout
- Max retry per step (default 3):
- Overall timeout seconds (default 30):
- Failure handling (default: log and exit):

8) UI Requirements (AI can infer if blank)
- [ ] need master CheckBox
- [ ] need mode ComboBox (list options):
- [ ] need count SpinBox (range):
- [ ] need text input LineEdit (purpose):
- [ ] need threshold Slider (range):
- [ ] need start button (usually for on_demand)

9) Resources
- [ ] need new image resources
- Resource dir (default app/features/assets/<module_name>/):
- Note: if any step target is an image filename (e.g. xxx.png), this should usually be checked.

10) Acceptance Criteria
- Minimum acceptable result:
- Forbidden behavior (e.g., stuck loop, freeze):

11) Optional: Recorded Script Paste Area (for direct conversion)
- Recording source (optional): AHK / AutoHotkey / Python / other
- Original recorded script (paste multi-line script):
<<<SCRIPT_START>>>
(paste script here)
<<<SCRIPT_END>>>
- Conversion requirement (optional):
  - Example: convert all clicks to move_click, and add recognition + timeout

-------------------- AI Execution Section (Do NOT modify) --------------------

You must translate every item from User Input Section into project code without omission.

[A. User Options -> Code Mapping]
1) Module type
- periodic => @module(host="periodic")
- on_demand => @module(host="on_demand")
- unsure => auto decide:
  - contains "scheduled/daily/auto-run" => periodic
  - contains "manual start/pre-position" => on_demand

2) Entry points
- periodic checked => generate/mount periodic UI
- on_demand checked => generate/mount on_demand UI
- passive checked => on_demand passive style (trigger-like)

3) Preconditions
- return home = yes => call back_to_home(self.auto, self.logger) at run() start
- specific screen required => implement as first state in state machine

4) Recognition method
- OCR => auto.find_element(target, "text", ...)
- image => auto.find_element("app/features/assets/<module>/<img>", "image", ...)
- color block => get_crop_form_first_screenshot + color analysis
- unsure => OCR first, fallback to image; include rationale in comment
- if recognition method is blank, infer from target:
  - plain words/sentence => OCR
  - filename ending (.png/.jpg/.jpeg) => image
  - HSV/RGB/color-threshold style => color block

5) Action translation
- click => must be auto.move_click(...)
- key action => auto.press_key / key_down / key_up
- wait => time.sleep
- swipe => use existing automation swipe capability
- if user writes natural language action (e.g. "hold key A for 5s"), parse and generate code directly

6) Region & threshold
- region blank/unchecked/invalid => full-screen default (no crop)
- valid region x1,y1,x2,y2 => set crop
- threshold blank => default 0.7

[B. Resolution Adaptation - Mandatory]
1) Read current window size; base design resolution is 1920x1080.
2) Scale any pixel click:
   - scale_x = current_w / 1920
   - scale_y = current_h / 1080
   - click_x = int(base_x * scale_x)
   - click_y = int(base_y * scale_y)
   - auto.move_click(click_x, click_y)
3) Prefer ratio crop (0~1) over absolute pixels:
   - crop=(x1/1920, y1/1080, x2/1920, y2/1080)
4) If user confirms non-16:9:
   - prioritize ratio crop + OCR
   - reduce dependence on image templates
   - log warning: non-16:9 may reduce template matching quality
5) If resolution is uncertain:
   - generate based on 1920x1080 baseline
   - execute with scaling formula

[C. `auto` Function Usage]
1) auto.take_screenshot()
   - first call inside each loop iteration
2) auto.find_element(target, mode, ...)
   - recognition only, not final click
3) auto.move_click(x, y, ...)
   - only allowed click action for Snowbreak
4) auto.press_key(...)
   - keyboard action
5) auto.get_crop_form_first_screenshot(crop=...)
   - color block detection

[D. UI Auto-Inference]
1) If UI not specified, generate minimal UI:
   - CheckBox_enable
   - SpinBox_times
   - ComboBox_mode (if branching exists)
   - start button by default for on_demand
2) If user mentions threshold/delay/count/mode/key:
   - threshold -> Slider/SpinBox
   - delay -> SpinBox
   - count -> SpinBox
   - mode -> ComboBox
   - key -> LineEdit

[E. Output Order - Must Follow]
1) Directory changes (new/modified files)
2) Usecase core code (declarative class with @module)
3) UI code (if needed)
4) Integration notes (if auto-mounted, explicitly say "no extra registration needed")
5) Test commands and results
6) Requirement-to-implementation checklist
7) If recorded script provided, add mapping table: Recorded statement -> SAA code

[E-1. File Output Format - Must Follow]
1) Output one file per code block; snippets are not allowed.
2) Before each code block, include target file path (absolute or project-relative).
3) Each code block must be complete, directly pasteable full file content.
4) Use fenced code blocks with language tag (e.g., ```python).
5) For modified files, still output the full updated file, not only a diff.

[F. Verification Commands - At Minimum]
- python -m compileall app
- python scripts/smoke_modules.py

=====================================================================
```
