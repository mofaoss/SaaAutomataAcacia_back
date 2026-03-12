from __future__ import annotations

import time
from dataclasses import dataclass

from app.features.utils.home_navigation import back_to_home
from app.framework.core.module_system import periodic_module
from app.framework.core.module_system.models import Field
from app.framework.i18n import _
from app.framework.infra.automation.timer import Timer


@dataclass(frozen=True, slots=True)
class ShoppingItem:
    key: str
    target_text: str
    label: str
    msgid: str


PERSON_ITEMS: tuple[ShoppingItem, ...] = (
    ShoppingItem("item_person_1", "肴", _("肴", msgid="yao"), "yao"),
    ShoppingItem("item_person_2", "安卡希雅", _("安卡希雅", msgid="acacia"), "acacia"),
    ShoppingItem("item_person_3", "里芙", _("里芙", msgid="lyfe"), "lyfe"),
    ShoppingItem("item_person_4", "辰星", _("辰星", msgid="chenxing"), "chenxing"),
    ShoppingItem("item_person_5", "茉莉安", _("茉莉安", msgid="marian"), "marian"),
    ShoppingItem("item_person_6", "芬妮", _("芬妮", msgid="fenny"), "fenny"),
    ShoppingItem("item_person_7", "芙提雅", _("芙提雅", msgid="fritia"), "fritia"),
    ShoppingItem("item_person_8", "瑟瑞斯", _("瑟瑞斯", msgid="siris"), "siris"),
    ShoppingItem("item_person_9", "琴诺", _("琴诺", msgid="cherno"), "cherno"),
    ShoppingItem("item_person_10", "猫汐尔", _("猫汐尔", msgid="mauxir"), "mauxir"),
    ShoppingItem("item_person_11", "晴", _("晴", msgid="haru"), "haru"),
    ShoppingItem("item_person_12", "恩雅", _("恩雅", msgid="enya"), "enya"),
    ShoppingItem("item_person_13", "妮塔", _("妮塔", msgid="nita"), "nita"),
)

WEAPON_ITEMS: tuple[ShoppingItem, ...] = (
    ShoppingItem("item_weapon_1", "彩虹打火机", _("彩虹打火机", msgid="prismatic_igniter"), "prismatic_igniter"),
    ShoppingItem("item_weapon_2", "深海呼唤", _("深海呼唤", msgid="deep_sea_call"), "deep_sea_call"),
    ShoppingItem("item_weapon_3", "草莓蛋糕", _("草莓蛋糕", msgid="strawberry_shortcake"), "strawberry_shortcake"),
)

SHOP_ITEMS: tuple[ShoppingItem, ...] = (
    ShoppingItem("CheckBox_buy_3", "通用强化套件", _("通用强化套件", msgid="universal_enhancement_kit"), "universal_enhancement_kit"),
    ShoppingItem("CheckBox_buy_4", "优选强化套件", _("优选强化套件", msgid="premium_enhancement_kit"), "premium_enhancement_kit"),
    ShoppingItem("CheckBox_buy_5", "精致强化套件", _("精致强化套件", msgid="exquisite_enhancement_kit"), "exquisite_enhancement_kit"),
    ShoppingItem("CheckBox_buy_6", "新手战斗记录", _("新手战斗记录", msgid="beginner_battle_record"), "beginner_battle_record"),
    ShoppingItem("CheckBox_buy_7", "普通战斗记录", _("普通战斗记录", msgid="standard_battle_record"), "standard_battle_record"),
    ShoppingItem("CheckBox_buy_8", "优秀战斗记录", _("优秀战斗记录", msgid="advanced_battle_record"), "advanced_battle_record"),
    ShoppingItem("CheckBox_buy_9", "初级职级认证", _("初级职级认证", msgid="junior_rank_certification"), "junior_rank_certification"),
    ShoppingItem("CheckBox_buy_10", "中级职级认证", _("中级职级认证", msgid="intermediate_rank_certification"), "intermediate_rank_certification"),
    ShoppingItem("CheckBox_buy_11", "高级职级认证", _("高级职级认证", msgid="senior_rank_certification"), "senior_rank_certification"),
    ShoppingItem("CheckBox_buy_12", "合成颗粒", _("合成颗粒", msgid="synthetic_particles"), "synthetic_particles"),
    ShoppingItem("CheckBox_buy_13", "芳烃塑料", _("芳烃塑料", msgid="hydrocarbon_plastic"), "hydrocarbon_plastic"),
    ShoppingItem("CheckBox_buy_14", "单极纤维", _("单极纤维", msgid="monopolar_fibers"), "monopolar_fibers"),
    ShoppingItem("CheckBox_buy_15", "光纤轴突", _("光纤轴突", msgid="fiber_axon"), "fiber_axon"),
)

SHOP_CHECKBOX_KEYS: tuple[str, ...] = tuple(item.key for item in SHOP_ITEMS)
PERSON_ITEM_KEYS: tuple[str, ...] = tuple(item.key for item in PERSON_ITEMS)
WEAPON_ITEM_KEYS: tuple[str, ...] = tuple(item.key for item in WEAPON_ITEMS)


def _display_name(item: ShoppingItem) -> str:
    return str(_(item.target_text, msgid=item.msgid))


def _item_key_to_target_map(items: tuple[ShoppingItem, ...]) -> dict[str, str]:
    return {item.key: item.target_text for item in items}


def _item_target_to_display_map(items: tuple[ShoppingItem, ...]) -> dict[str, str]:
    return {item.target_text: _display_name(item) for item in items}


def build_field_declarations() -> dict[str, Field]:
    fields: dict[str, Field] = {}
    for item in SHOP_ITEMS:
        fields[item.key] = Field(
            name=item.label,
            msgid=item.msgid,
            group=_("材料道具", msgid="shop_group"),
            layout="full",
        )
    for item in PERSON_ITEMS:
        fields[item.key] = Field(
            name=item.label,
            msgid=item.msgid,
            group=_("角色碎片", msgid="character_shards_group"),
            layout="half",
        )
    for item in WEAPON_ITEMS:
        fields[item.key] = Field(
            name=item.label,
            msgid=item.msgid,
            group=_("武器", msgid="weapon_group"),
            layout="full",
        )
    return fields


@periodic_module(
    _("商店购买", msgid="shopping_title"),
    fields=build_field_declarations(),
    auto_page_collapsible_groups=True,
    auto_page_groups_collapsed_by_default=True,
    description="""### 提示
* 根据设置自动购买商店中的角色碎片、武器和其他商品。
* 购买顺序：先角色碎片和武器，再其他商品。
* 每个商品会尝试多次，直到购买成功或确认售罄。""",
)
class ShoppingModule:
    def __init__(
        self,
        auto,
        logger,
        isLog: bool = False,
        CheckBox_buy_3: bool = False,
        CheckBox_buy_4: bool = False,
        CheckBox_buy_5: bool = False,
        CheckBox_buy_6: bool = False,
        CheckBox_buy_7: bool = False,
        CheckBox_buy_8: bool = False,
        CheckBox_buy_9: bool = False,
        CheckBox_buy_10: bool = False,
        CheckBox_buy_11: bool = False,
        CheckBox_buy_12: bool = False,
        CheckBox_buy_13: bool = False,
        CheckBox_buy_14: bool = False,
        CheckBox_buy_15: bool = False,
        item_person_1: bool = False,
        item_person_2: bool = False,
        item_person_3: bool = False,
        item_person_4: bool = False,
        item_person_5: bool = False,
        item_person_6: bool = False,
        item_person_7: bool = False,
        item_person_8: bool = False,
        item_person_9: bool = False,
        item_person_10: bool = False,
        item_person_11: bool = False,
        item_person_12: bool = False,
        item_person_13: bool = False,
        item_weapon_1: bool = False,
        item_weapon_2: bool = False,
        item_weapon_3: bool = False,
    ):
        self.auto = auto
        self.logger = logger
        self.is_log = bool(isLog)

        values = locals()
        self.commodity_dic = {key: bool(values.get(key, False)) for key in SHOP_CHECKBOX_KEYS}
        self.person_dic = {key: bool(values.get(key, False)) for key in PERSON_ITEM_KEYS}
        self.weapon_dic = {key: bool(values.get(key, False)) for key in WEAPON_ITEM_KEYS}

        self.person_key_to_target = _item_key_to_target_map(PERSON_ITEMS)
        self.weapon_key_to_target = _item_key_to_target_map(WEAPON_ITEMS)
        self.shop_key_to_target = _item_key_to_target_map(SHOP_ITEMS)

        all_items = SHOP_ITEMS + PERSON_ITEMS + WEAPON_ITEMS
        self.target_to_display = _item_target_to_display_map(all_items)

        self.scroll_fallback_points = [
            (960, 540),
            (1552, 537),
            (520, 540),
        ]
        self.scroll_point_index = 0

    def run(self):
        back_to_home(self.auto, self.logger)
        self.open_store()
        self.buy()

    def open_store(self):
        timeout = Timer(10).start()
        while True:
            self.auto.take_screenshot()

            if self.auto.click_element(
                "常规",
                "text",
                crop=(89 / 1920, 140 / 1080, 220 / 1920, 191 / 1080),
                is_log=self.is_log,
            ):
                time.sleep(0.5)
                break
            if self.auto.click_element(
                "商店",
                "text",
                crop=(1759 / 1920, 1002 / 1080, 1843 / 1920, 1050 / 1080),
                is_log=self.is_log,
            ):
                time.sleep(0.2)
                continue

            if timeout.reached():
                self.logger.error(_("Open shop timeout", msgid="open_shop_timeout"))
                break

    def buy(self):
        timeout = Timer(30).start()
        buy_list = self.collect_item()
        temp_list = buy_list.copy()
        finish_list: list[str] = []
        is_selected = False
        text = temp_list.pop(0) if temp_list else ""

        self.scroll_to_bottom(scroll_times=1)
        while True:
            if len(buy_list) == len(finish_list):
                break

            self.auto.take_screenshot()
            if not text:
                break

            if not is_selected:
                if self.auto.find_element(
                    ["售", "罄"],
                    "text",
                    crop=(850 / 1920, 500 / 1080, 1070 / 1920, 900 / 1080),
                    is_log=self.is_log,
                ):
                    continue

                if self.try_select_item(text):
                    time.sleep(0.3)
                    is_selected = True
                    continue

                self.logger.warning(
                    _(
                        "{var_0} not found in shop",
                        msgid="var_0_not_found_in_shop",
                        var_0=self._display_name(text),
                    )
                )
                finish_list.append(text)
                text = temp_list.pop(0) if temp_list else ""
                continue

            if self.auto.find_element(
                "获得道具",
                "text",
                crop=(824 / 1920, 0, 1089 / 1920, 129 / 1080),
                is_log=self.is_log,
            ):
                self.auto.press_key("esc")
                time.sleep(0.2)
                self.scroll_to_bottom()
                finish_list.append(text)
                text = temp_list.pop(0) if temp_list else ""
                is_selected = False
                continue

            if self.auto.find_element(
                "不足",
                "text",
                crop=(866 / 1920, 513 / 1080, 1048 / 1920, 880 / 1080),
                is_log=self.is_log,
            ):
                self.logger.warning(_("Insufficient currency", msgid="insufficient_currency"))
                break

            if self.auto.click_element(
                "最大",
                "text",
                crop=(1713 / 1920, 822 / 1080, 1, 895 / 1080),
                is_log=self.is_log,
            ):
                if self.auto.click_element(
                    "购买",
                    "text",
                    crop=(1740 / 1920, 993 / 1080, 1828 / 1920, 1038 / 1080),
                    is_log=self.is_log,
                ):
                    time.sleep(1)
                    continue
            else:
                is_selected = False
                if self.auto.find_element(
                    ["售", "罄"],
                    "text",
                    crop=(850 / 1920, 500 / 1080, 1070 / 1920, 900 / 1080),
                    is_log=self.is_log,
                ):
                    finish_list.append(text)
                    text = temp_list.pop(0) if temp_list else ""
                continue

            if timeout.reached():
                self.logger.error(_("Purchase timeout", msgid="purchase_timeout"))
                break

        back_to_home(self.auto, self.logger)

    def collect_item(self) -> list[str]:
        result_list: list[str] = []

        for key, value in self.person_dic.items():
            if value and key in self.person_key_to_target:
                result_list.append(self.person_key_to_target[key])

        for key, value in self.weapon_dic.items():
            if value and key in self.weapon_key_to_target:
                result_list.append(self.weapon_key_to_target[key])

        for key, value in self.commodity_dic.items():
            if value and key in self.shop_key_to_target:
                result_list.append(self.shop_key_to_target[key])

        return result_list

    def _display_name(self, target_name: str) -> str:
        return self.target_to_display.get(target_name, target_name)

    def try_select_item(self, text: str, max_attempts: int = 4) -> bool:
        for attempt in range(max_attempts):
            if self.auto.click_element(text, "text", crop=(302 / 1920, 194 / 1080, 1, 1), is_log=self.is_log):
                return True
            if attempt < max_attempts - 1:
                self.logger.info(
                    _(
                        "{var_0} not found, retry after scrolling ({var_1}/{var_2})",
                        msgid="var_0_not_found_retry_after_scrolling_var_1_var_2",
                        var_0=self._display_name(text),
                        var_1=attempt + 1,
                        var_2=max_attempts - 1,
                    )
                )
                self.scroll_to_bottom(scroll_times=1)
        return False

    def scroll_to_bottom(self, scroll_times: int = 3):
        for _ in range(scroll_times):
            if not self.scroll_once():
                self.logger.warning(
                    _(
                        "Shop scroll failed: all fallback points were ineffective",
                        msgid="shop_scroll_failed_all_fallback_points_were_ineffective",
                    )
                )

    def scroll_once(self) -> bool:
        total = len(self.scroll_fallback_points)
        for offset in range(total):
            idx = (self.scroll_point_index + offset) % total
            x, y = self.scroll_fallback_points[idx]
            sx = int(x / self.auto.scale_x)
            sy = int(y / self.auto.scale_y)
            self.auto.move_to(sx, sy)
            if self.auto.mouse_scroll(sx, sy, -1200, time_out=0.8):
                self.scroll_point_index = (idx + 1) % total
                time.sleep(0.03)
                return True
        return False
