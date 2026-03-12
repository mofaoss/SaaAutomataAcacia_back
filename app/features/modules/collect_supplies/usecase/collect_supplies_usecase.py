import time
from datetime import datetime

from PySide6.QtCore import Qt
from qfluentwidgets import InfoBar, InfoBarPosition

from app.framework.infra.config.app_config import config
from app.framework.infra.config.data_models import parse_config_update_data
from app.features.utils.network import get_cloudflare_data
from app.framework.infra.automation.timer import Timer
from app.features.utils.home_navigation import back_to_home

from app.framework.core.module_system import Field, periodic_module
from app.framework.i18n import _
from app.framework.ui.widgets.custom_message_box import CustomMessageBox


_COLLECT_SUPPLIES_FIELDS = {
    "CheckBox_mail": Field("邮箱奖励", group="补给领取"),
    "CheckBox_fish_bait": Field("鱼饵奖励", group="补给领取"),
    "CheckBox_dormitory": Field("宿舍碎片", group="补给领取"),
    "CheckBox_redeem_code": Field("自动兑换码", group="补给领取"),
}


@periodic_module(
    "领取补给",
    fields=_COLLECT_SUPPLIES_FIELDS,
    description="""### 提示
        * 默认会领取补给站体力和好友体力。
        * 启用兑换码后可自动获取并兑换网络兑换码。
        * 在线兑换码由开发者维护，可能存在更新延迟。""",
    actions={
        "导入兑换码": "on_import_codes_click",
        "重置兑换码": "on_reset_codes_click",
    },
)
class CollectSuppliesModule:
    def __init__(
        self,
        auto=None,
        logger=None,
        *,
        app_config=None,
        isLog: bool = False,
        CheckBox_mail: bool = False,
        CheckBox_fish_bait: bool = False,
        CheckBox_dormitory: bool = False,
        CheckBox_redeem_code: bool = False,
        TextEdit_import_codes: str = '',
        update_data: str = '',
        used_codes: list = None,
        import_codes: list = None,
        settings_usecase=None,
    ):
        self.auto = auto
        self.logger = logger
        self.app_config = app_config
        self.is_log = bool(isLog)
        self.enable_mail = bool(CheckBox_mail)
        self.enable_fish_bait = bool(CheckBox_fish_bait)
        self.enable_dormitory = bool(CheckBox_dormitory)
        self.enable_redeem_code = bool(CheckBox_redeem_code)
        self.import_codes_text = TextEdit_import_codes
        self.update_data = update_data
        self.used_codes = list(used_codes or [])
        self.import_codes = list(import_codes or [])
        self.settings_usecase = settings_usecase
        self._is_import_dialog_open = False
        super().__init__()

    def run(self):
        # 确保在主页面
        back_to_home(self.auto, self.logger)

        if self.enable_mail:
            self.receive_mail()
        if self.enable_fish_bait:
            self.receive_fish_bait()
        if self.enable_dormitory:
            self.receive_dormitory()
        if self.enable_redeem_code:
            self.redeem_code()

        self.friends_power()
        self.station_power()

    @staticmethod
    def _resolve_text_edit(*, page=None, text_edit=None):
        if text_edit is not None:
            return text_edit
        if page is None:
            return None
        return getattr(page, "TextEdit_import_codes", None)

    @staticmethod
    def _set_text_edit_value(text_edit, value: str) -> None:
        if text_edit is None:
            return
        if hasattr(text_edit, "setPlainText"):
            text_edit.setPlainText(str(value))
            return
        if hasattr(text_edit, "setText"):
            text_edit.setText(str(value))

    @staticmethod
    def _read_text_edit_value(text_edit) -> str:
        if text_edit is None:
            return ""
        if hasattr(text_edit, "toPlainText"):
            return str(text_edit.toPlainText() or "")
        if hasattr(text_edit, "text"):
            return str(text_edit.text() or "")
        return ""

    def _reset_redeem_codes(self) -> str:
        if self.settings_usecase is not None and hasattr(self.settings_usecase, "reset_redeem_codes"):
            return str(self.settings_usecase.reset_redeem_codes() or "")

        app_cfg = self.app_config or config
        content = ""
        import_item = getattr(app_cfg, "import_codes", None)
        used_item = getattr(app_cfg, "used_codes", None)
        if import_item is not None and getattr(import_item, "value", None):
            app_cfg.set(import_item, [])
            content += " 导入 "
        if used_item is not None and getattr(used_item, "value", None):
            app_cfg.set(used_item, [])
            content += " 已使用 "
        return content

    @staticmethod
    def _fallback_parse_import_codes(raw_text: str) -> list[str]:
        lines = (raw_text or "").splitlines()
        result: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if ":" in stripped:
                result.append(stripped.split(":")[-1].strip())
            elif "：" in stripped:
                result.append(stripped.split("：")[-1].strip())
            else:
                result.append(stripped)
        return result

    def _parse_import_codes(self, raw_text: str) -> list[str]:
        if self.settings_usecase is not None and hasattr(self.settings_usecase, "parse_import_codes"):
            return list(self.settings_usecase.parse_import_codes(raw_text))
        return self._fallback_parse_import_codes(raw_text)

    def _save_import_codes(self, codes: list[str]) -> None:
        self.import_codes = list(codes)
        if self.settings_usecase is not None and hasattr(self.settings_usecase, "save_import_codes"):
            self.settings_usecase.save_import_codes(codes)
            return

        app_cfg = self.app_config or config
        import_item = getattr(app_cfg, "import_codes", None)
        if import_item is not None:
            app_cfg.set(import_item, list(codes))

    def _prompt_import_codes(self, parent):
        if self._is_import_dialog_open:
            return None

        self._is_import_dialog_open = True
        try:
            dialog = CustomMessageBox(parent, _("导入兑换码"), "text_edit")
            dialog.content.setEnabled(True)
            dialog.content.setPlaceholderText(_("每行一个兑换码", msgid="one_code_per_line"))
            if dialog.exec():
                return str(dialog.content.toPlainText() or "")
            return None
        finally:
            self._is_import_dialog_open = False

    def on_reset_codes_click(self, page=None, host=None, text_edit=None, **_kwargs):
        text_edit = self._resolve_text_edit(page=page, text_edit=text_edit)
        if self._read_text_edit_value(text_edit):
            self._set_text_edit_value(text_edit, "")
        content = self._reset_redeem_codes()
        InfoBar.success(
            title=_('Reset Successful', msgid='reset_successful'),
            content=_(f'Successfully reset import and display {content}', msgid='successfully_reset_import_and_display_content'),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
            parent=host or page,
        )

    def on_import_codes_click(self, page=None, host=None, text_edit=None, **_kwargs):
        raw_codes = self._prompt_import_codes(page or host)
        if raw_codes is None:
            return

        codes = self._parse_import_codes(raw_codes)
        self._save_import_codes(codes)

        text_edit = self._resolve_text_edit(page=page, text_edit=text_edit)
        self._set_text_edit_value(text_edit, "\n".join(codes))

    def friends_power(self):
        timeout = Timer(30).start()
        while True:
            self.auto.take_screenshot()

            # 正常退出
            if self.auto.find_element('感知', 'text', crop=(761 / 1920, 517 / 1080, 1175 / 1920, 563 / 1080),
                                      is_log=self.is_log):
                break
            # 收过体力再进入的情况
            if self.auto.find_element('好友', 'text',
                                      crop=(59 / 1920, 112 / 1080, 187 / 1920, 162 / 1080), is_log=self.is_log):
                if not self.auto.find_element('键收赠', 'text',
                                              crop=(1722 / 1920, 1012 / 1080, 1858 / 1920, 1055 / 1080),
                                              is_log=self.is_log):
                    break
            if self.auto.click_element('键收赠', 'text', crop=(1722 / 1920, 1012 / 1080, 1858 / 1920, 1055 / 1080),
                                       is_log=self.is_log):
                continue
            # if self.auto.click_element("app/features/modules/collect_supplies/assets/images/friends.png", "image",
            #                            crop=(259 / 1920, 448 / 1080, 364 / 1920, 515 / 1080), is_log=self.is_log):
            #     continue
            if self.auto.find_element('基地', 'text', crop=(
                    1598 / 1920, 678 / 1080, 1661 / 1920, 736 / 1080), is_log=self.is_log) and self.auto.find_element(
                '任务', 'text', crop=(
                        1452 / 1920, 327 / 1080, 1529 / 1920, 376 / 1080), is_log=self.is_log):
                self.auto.click_element_with_pos((int(330 / self.auto.scale_x), int(486 / self.auto.scale_y)))
                time.sleep(0.3)
                continue

            if timeout.reached():
                self.logger.error(_("领取好友体力超时"))
                break
        back_to_home(self.auto, self.logger)

    def station_power(self):
        confirm_flag = False

        timeout = Timer(30).start()
        while True:
            self.auto.take_screenshot()

            # 按正常流程走完的退出情况
            if confirm_flag:
                if self.auto.click_element('购买', 'text', crop=(1741 / 2560, 1004 / 1440, 1831 / 2560, 1060 / 1440),
                                           is_log=self.is_log):
                    break
            # 已经领取但重复进入的情况
            if self.auto.find_element(['限时', '补给箱'], 'text',
                                      crop=(195 / 1920, 113 / 1080, 325 / 1920, 160 / 1080), is_log=self.is_log):
                if not self.auto.find_element(["每日", "物资配给箱"], "text",
                                              crop=(223 / 1920, 625 / 1080, 500 / 1920, 677 / 1080),
                                              is_log=self.is_log):
                    break
            if self.auto.click_element(["每日", "物资配给箱"], "text",
                                       crop=(223 / 1920, 625 / 1080, 500 / 1920, 677 / 1080),
                                       is_log=self.is_log):
                confirm_flag = True
                time.sleep(1)
                continue
            if self.auto.click_element('供应站', 'text', crop=(141 / 1920, 553 / 1080, 229 / 1920, 596 / 1080),
                                       is_log=self.is_log):
                continue

            if not self.auto.find_element(["补给"], 'text', crop=(133 / 1920, 44 / 1080, 376 / 1920, 91 / 1080),
                                          is_log=self.is_log):
                self.auto.click_element_with_pos((int(47 / self.auto.scale_x), int(448 / self.auto.scale_y)))
                time.sleep(0.3)
                continue
            if timeout.reached():
                self.logger.error(_("购买每日物资配给箱超时"))
                break
                back_to_home(self.auto, self.logger)

    def receive_mail(self):
        timeout = Timer(30).start()
        click_flag = False
        while True:
            self.auto.take_screenshot()

            if self.auto.find_element('获得道具', 'text', crop=(824 / 1920, 0, 1089 / 1920, 129 / 1080),
                                      is_log=self.is_log):
                break
            else:
                if click_flag:
                    break
            if self.auto.click_element('批量领取', 'text', crop=(303 / 1920, 982 / 1080, 462 / 1920, 1028 / 1080),
                                       is_log=self.is_log):
                click_flag = True
                continue
            # if self.auto.click_element('app/features/modules/collect_supplies/assets/images/mail.png', 'image',
            #                            crop=(76 / 1920, 437 / 1080, 151 / 1920, 491 / 1080), is_log=self.is_log):
            #     continue
            if self.auto.find_element('基地', 'text', crop=(
                    1598 / 1920, 678 / 1080, 1661 / 1920, 736 / 1080), is_log=self.is_log) and self.auto.find_element(
                '任务', 'text', crop=(
                        1452 / 1920, 327 / 1080, 1529 / 1920, 376 / 1080), is_log=self.is_log):
                self.auto.click_element_with_pos((int(115 / self.auto.scale_x), int(468 / self.auto.scale_y)))
                time.sleep(0.3)
                continue

            if timeout.reached():
                self.logger.error(_("领取邮箱资源超时"))
                break
                back_to_home(self.auto, self.logger)

    def receive_fish_bait(self):
        timeout = Timer(30).start()
        while True:
            self.auto.take_screenshot()

            if self.auto.find_element('获得道具', 'text', crop=(824 / 1920, 0, 1089 / 1920, 129 / 1080),
                                      is_log=self.is_log):
                break
            if self.auto.find_element('开拓任务', 'text', crop=(36 / 1920, 103 / 1080, 163 / 1920, 155 / 1080),
                                      is_log=self.is_log):
                if not self.auto.click_element('键领取', 'text', crop=(22 / 1920, 965 / 1080, 227 / 1920, 1030 / 1080),
                                               is_log=self.is_log,
                                               extract=[(241, 240, 241), 128]):
                    break
                else:
                    break
            if self.auto.click_element("开拓目标", "text", crop=(1611 / 1920, 879 / 1080, 1716 / 1920, 919 / 1080),
                                       is_log=self.is_log):
                time.sleep(0.5)
                continue
            if self.auto.click_element("新星开拓", "text", crop=(0, 758 / 1080, 1, 828 / 1080), is_log=self.is_log):
                continue
            if self.auto.click_element("特别派遣", "text", crop=(181 / 1920, 468 / 1080, 422 / 1920, 541 / 1080),
                                       is_log=self.is_log):
                time.sleep(0.3)
                continue
            if self.auto.click_element("战斗", "text", crop=(1510 / 1920, 450 / 1080, 1650 / 1920, 530 / 1080),
                                       is_log=self.is_log, extract=[(39, 39, 56), 128]):
                time.sleep(0.3)
                continue

            if timeout.reached():
                self.logger.error(_("领取鱼饵超时"))
                break
                back_to_home(self.auto, self.logger)

    def receive_dormitory(self):
        """领取宿舍碎片"""
        timeout = Timer(30).start()
        finish_flag = False
        while True:
            self.auto.take_screenshot()

            if finish_flag and self.auto.click_element('退出', 'text',
                                                       crop=(2161 / 2560, 32 / 1440, 2250 / 2560, 94 / 1440),
                                                       is_log=self.is_log):
                while self.auto.click_element('退出', 'text',
                                              crop=(2161 / 2560, 32 / 1440, 2250 / 2560, 94 / 1440),
                                              is_log=self.is_log):
                    self.auto.take_screenshot()
                    time.sleep(1)
                break
            if self.auto.click_element('谢谢', 'text', crop=(1138 / 2560, 1075 / 1440, 1418 / 2560, 1153 / 1440),
                                       is_log=self.is_log):
                time.sleep(0.3)
                finish_flag = True
                self.auto.press_key('esc')
                continue
            if self.auto.click_element('键收取', 'text', crop=(1845 / 2560, 983 / 1440, 2073 / 2560, 1061 / 1440),
                                       is_log=self.is_log):
                time.sleep(1.5)
                self.auto.take_screenshot()
                # 无法获取时
                if self.auto.find_element(['已经', '上线', '断片'], 'text',
                                          crop=(979 / 2560, 687 / 1440, 1592 / 2560, 750 / 1440),
                                          is_log=self.is_log):
                    finish_flag = True
                    continue
                time.sleep(3)
                continue
            if self.auto.click_element('基地', 'text', crop=(2130 / 2560, 913 / 1440, 2217 / 2560, 977 / 1440),
                                       is_log=self.is_log):
                time.sleep(3)
                continue
            if self.auto.find_element('Esc', 'text', crop=(57 / 2560, 117 / 1440, 127 / 2560, 157 / 1440),
                                      is_log=self.is_log) or self.auto.find_element('Enter', 'text', crop=(
                    9 / 2560, 1377 / 1440, 130 / 2560, 1431 / 1440), is_log=self.is_log):
                self.auto.press_key('esc')
                continue
            if self.auto.click_element(['剩', '剩余'], 'text',
                                       crop=(2072 / 2560, 1372 / 1440, 2150 / 2560, 1418 / 1440),
                                       is_log=self.is_log):
                time.sleep(1)
                continue
            if timeout.reached():
                self.logger.error(_("领取宿舍拼图超时"))
                break

                back_to_home(self.auto, self.logger)

    def redeem_code(self):
        """领取兑换码"""
        def get_codes():
            """提取还在有效期内的兑换码"""
            active_codes = []

            # 检查配置数据是否存在且格式正确
            config_data = parse_config_update_data(self.update_data)
            if not config_data:
                self.logger.warning(_("配置数据为空或格式不正确，无法获取兑换码"))
                return active_codes

            used_codes = self.used_codes or []  # 确保不为None

            for code in config_data.data.redeemCodes:
                # 如果没被使用过才加入兑换
                if code.code not in used_codes:
                    active_codes.append(code.code)
            import_codes = self.import_codes or []  # 确保不为None
            # 加入用户导入
            for code in import_codes:
                if code not in used_codes:
                    active_codes.append(code)
            return active_codes

        codes = get_codes()

        if not codes or len(codes) == 0:
            self.logger.info(_("没有需要兑换的码"))
            return

        index = 0
        timeout = Timer(120).start()
        while True:
            self.auto.take_screenshot()

            # if self.auto.find_element("成功",'text',crop=(733/1920,473/1080,1182/1920,570/1080)):
            #     pass

            if self.auto.find_element(['礼品', '兑换'], 'text', crop=(823 / 1920, 294 / 1080, 1105 / 1920, 409 / 1080),
                                      is_log=self.is_log):
                self.logger.info(_("Start redeeming code {code}", msgid="redeem_code_start", code=codes[index]))
                # 点击 文本框
                self.auto.click_element_with_pos((int(960 / self.auto.scale_x), int(506 / self.auto.scale_y)))
                # 输入兑换码
                self.auto.type_string(codes[index])
                # 确定
                self.auto.click_element_with_pos((int(1417 / self.auto.scale_x), int(765 / self.auto.scale_y)))
                # 判断是否触发频繁操作，触发就退出
                time.sleep(2)
                self.auto.take_screenshot()
                if self.auto.click_element(['频繁'], 'text',
                                           crop=(982 / 2560, 664 / 1440, 1593 / 2560, 768 / 1440),
                                           is_log=self.is_log):
                    break
                # 加入已使用的兑换码列表
                old_used_codes = self.used_codes or []
                new_used_codes = old_used_codes.copy()
                new_used_codes.append(codes[index])
                self.used_codes = new_used_codes
                app_cfg = self.app_config or config
                if hasattr(app_cfg, "used_codes"):
                    app_cfg.set(app_cfg.used_codes, new_used_codes)
                index += 1
                time.sleep(1)
                continue

            if index >= len(codes):
                self.logger.info(_("兑换码已全部兑换"))
                self.auto.press_key('esc')
                break
            if self.auto.click_element(['前往', '兑换'], 'text',
                                       crop=(1573 / 1920, 568 / 1080, 1793 / 1920, 660 / 1080),
                                       is_log=self.is_log):
                time.sleep(0.7)
                continue

            if self.auto.find_element('游戏性设置', 'text', crop=(305 / 1920, 23 / 1080, 586 / 1920, 131 / 1080),
                                      is_log=self.is_log):
                # 固定坐标点“其他设置”
                self.auto.click_element_with_pos((int(160 / self.auto.scale_x), int(760 / self.auto.scale_y)))
                time.sleep(0.3)
                continue

            if self.auto.find_element('基地', 'text', crop=(
                    1598 / 1920, 678 / 1080, 1661 / 1920, 736 / 1080), is_log=self.is_log) and self.auto.find_element(
                '任务', 'text', crop=(
                        1452 / 1920, 327 / 1080, 1529 / 1920, 376 / 1080), is_log=self.is_log):
                # 点击右上角齿轮
                self.auto.click_element_with_pos((int(1864 / self.auto.scale_x), int(33 / self.auto.scale_y)))
                time.sleep(0.3)
                continue

            if timeout.reached():
                self.logger.error(_("兑换兑换码超时"))
                break
        back_to_home(self.auto, self.logger)
