import time

import cv2
import numpy as np

from app.framework.core.module_system import Field, on_demand_module
from app.framework.i18n.runtime import _
from app.framework.infra.vision.vision import count_color_blocks


@on_demand_module(
    "Trigger",
    fields={
        "CheckBox_trigger_auto_f": Field(
            id="auto_f",
            label="Auto F",
            help="Automatically press F when collect prompt appears",
        ),
        "CheckBox_trigger_auto_e": Field(
            id="nita_auto_e",
            label="Nita Auto E",
            help="Automatically press E during QTE stage",
        ),
    },
    description="### Tips\n"
    "* Trigger runs as a background helper and does not block other on-demand tasks.\n"
    "* Enable Auto F to collect prompts automatically.\n"
    "* Enable Nita Auto E for QTE timing support.",
)
class TriggerModule:
    def __init__(
        self,
        auto,
        logger,
        isLog: bool = False,
        CheckBox_trigger_auto_f: bool = True,
        CheckBox_trigger_auto_e: bool = True,
    ):
        self.auto = auto
        self.logger = logger
        self.is_log = bool(isLog)
        self.enable_auto_f = bool(CheckBox_trigger_auto_f)
        self.enable_auto_e = bool(CheckBox_trigger_auto_e)

        self._collect_image = "app/features/modules/fishing/assets/images/collect.png"
        self._collect_crop = (1506 / 1920, 684 / 1080, 1547 / 1920, 731 / 1080)

        self._qte_text = "12"
        self._qte_text_crop = (1100 / 2560, 931 / 1440, 1458 / 2560, 1044 / 1440)
        self._qte_color_crop = (1130 / 2560, 1003 / 1440, 1428 / 2560, 1025 / 1440)

        self.upper_blue = np.array([109, 170, 255])
        self.lower_blue = np.array([104, 85, 200])
        self.upper_green = np.array([31, 173, 230])
        self.lower_green = np.array([27, 102, 175])

    def _try_auto_f(self) -> bool:
        if self.auto.find_element(
            self._collect_image,
            "image",
            crop=self._collect_crop,
            is_log=self.is_log,
            match_method=cv2.TM_CCOEFF_NORMED,
        ):
            self.auto.press_key("f")
            return True
        return False

    def _try_nita_auto_e(self) -> bool:
        if not self.auto.find_element(
            self._qte_text,
            "text",
            is_log=self.is_log,
            crop=self._qte_text_crop,
        ):
            return False

        crop_image = self.auto.get_crop_form_first_screenshot(crop=self._qte_color_crop)
        blue_blocks = count_color_blocks(crop_image, self.lower_blue, self.upper_blue, False)
        green_blocks = count_color_blocks(crop_image, self.lower_green, self.upper_green, False)
        if blue_blocks > 1 or green_blocks > 1:
            self.auto.press_key("e")
            time.sleep(0.3)
            return True
        return False

    def run(self):
        if not self.enable_auto_f and not self.enable_auto_e:
            self.logger.warning(
                _(
                    "Trigger skipped: all options are disabled",
                    msgid="trigger_skipped_all_options_disabled",
                )
            )
            return

        self.logger.info(
            _(
                "Trigger started in background mode",
                msgid="trigger_started_in_background_mode",
            )
        )

        while True:
            self.auto.take_screenshot()
            acted = False
            if self.enable_auto_f:
                acted = self._try_auto_f() or acted
            if self.enable_auto_e:
                acted = self._try_nita_auto_e() or acted
            if not acted:
                time.sleep(0.03)
