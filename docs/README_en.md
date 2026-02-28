<div align="center">
    <h1>
        <img src="../asset/logo_head.png" width="200"/>
        <br/>
        SaaAutomataAcacia
    </h1>
    <br/>

<a href="../README.md">简体中文</a> | English

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/P5P21QG9LW)
</div>

## 🌏 Language Compatibility

- Supported game languages: Simplified Chinese, Traditional Chinese
- Supported UI languages: Simplified Chinese, Traditional Chinese (Traditional uses `zh_HK` resources)
- Language settings are separated into independent options: `UI language` and `Game language`
- Automation text matching now normalizes Traditional Chinese to Simplified Chinese to reuse existing task keywords
- AUTO language behavior: follow system locale on Chinese systems; default to Simplified Chinese on non-Chinese systems
- Ensure dependencies are updated with `pip install -r requirements.txt` (includes `opencc-python-reimplemented`)
- You can set `MainWindow.Language` to `zh_HK` in `AppData/config.json` and restart for verification

## ✨Feature Introduction

> [!Tip]
> **Update**
> 1. Renamed the project to SaaAutomataAcacia and optimized the loading animation.
> 2. Added Traditional Chinese support.
> 3. Fixed the issue where Steam could not log in automatically.
> 4. Added support for farming operation logistics when using stamina.
> 5. Optimized memory chip usage logic and auto-applies by selected character count.
> 6. Added Star Exploration Pal Capture.
> 7. Improved background stability: better fault tolerance and quieter background operations.
> 8. Optimized shop purchase flow: fewer accidental clicks and more stable scrolling.
> 9. Fixed stamina potion day matching errors (e.g., 1/3 no longer mismatches to 11/13).
> 10. The UI now mostly supports English in core areas (Display/Home/Additional features).
> 11. More features to be updated...

> [!Warning]
>
> After version 2.0, all tasks support running while the window is obscured. Mouse clicks use an optimized method to
> minimize user disruption, enabling pure background operation for tasks not requiring mouse interaction. Only supports 16:
> 9 screen ratios. Works in both fullscreen and windowed modes. For other ratios, enable auto-scaling in settings to
> automatically resize and position the game window in the top-left corner (must be flush with the corner).

### ✨Feature List

<details><summary>Click to view development progress</summary>

✅ Game login

✅ Daily resource collection: Mail, friend stamina, supply station stamina, bait, dorm puzzles

✅ Shop purchases

✅ Event material farming

✅ Daily character fragments

✅ Neural Simulation sweep

✅ Daily mission reward collection

✅ Auto-fishing (pure background)

✅ Psychube analysis solution calculation

✅ Weekly 20-stage challenge

✅ Heartbeat Water Balloon

✅ Verification Battlefield (new maze)

✅ Extraterrestrial Guardian (endless & breakthrough)

✅ Mind Game

✅ Nita E-skill auto-QTE

✅ Light/dark mode adaptation

✅ Auto-collection trigger

✅ Auto-scaling ratio execution

✅ Automatic coordinate updates & schedule reminders

✅ Direct game launch via SaaAutomataAcacia

✅ GPU acceleration support for NVIDIA/AMD

✅ Auto-start on boot

✅ Stamina recovery notifications

✅ Auto redeem codes

✅ Farm operation logistics

✅ Star Exploration Pal Capture

⬜ Massage therapy

⬜ Update log display

⬜ Global hotkeys

⬜ Auto-gacha


</details>

### ⚡ Usage & Documentation

> [!Important]
>
> Special thanks to [vmoranv](https://github.com/vmoranv) for documentation support
> SaaAutomataAcacia Documentation: https://saadocs.netlify.app/

Demo video:[【基于图像识别的芬妮舞狮尘白自动化代理助手-哔哩哔哩】](https://b23.tv/W9OA85k)

### ✨ Running

<details>
<summary>👉 Click to expand screenshots 👈</summary>
<div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 10px;">
  <img src="../asset/1.png" style="width: 45%; max-width: 300px; object-fit: contain;" />
  <img src="../asset/2.png" style="width: 45%; max-width: 300px; object-fit: contain;" />
  <img src="../asset/3.png" style="width: 45%; max-width: 300px; object-fit: contain;" />
  <img src="../asset/4.png" style="width: 45%; max-width: 300px; object-fit: contain;" />
</div>
</details>

### 📌Download

- [Github Release](https://github.com/mofaoss/SaaAutomataAcacia/releases)

## ❤️ Related Projects

- OCR text recognition https://github.com/JaidedAI/EasyOCR
- Honkai: Star Rail Assistan https://github.com/moesnow/March7thAssistant
- MAA Arknights Assistant https://github.com/MaaAssistantArknights/MaaAssistantArknights
- GUI component library https://github.com/zhiyiYo/PyQt-Fluent-Widgets

## 📝License

> [!Note]
>
> GPLv3 License
[LICENSE](https://github.com/mofaoss/SaaAutomataAcacia/blob/main/LICENSE)
