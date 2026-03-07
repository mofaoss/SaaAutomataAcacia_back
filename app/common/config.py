# coding:utf-8
import sys
import locale as pylocale
import ctypes
import json
from enum import Enum

from PySide6.QtCore import QLocale
from qfluentwidgets import (qconfig, QConfig, ConfigItem, OptionsConfigItem, BoolValidator,
                            OptionsValidator, Theme, ConfigSerializer)

from .setting import CONFIG_FILE


class Language(Enum):
    """ Language enumeration """
    CHINESE_SIMPLIFIED = QLocale(QLocale.Chinese, QLocale.China)
    CHINESE_TRADITIONAL = QLocale(QLocale.Chinese, QLocale.HongKong)
    ENGLISH = QLocale(QLocale.English)
    AUTO = QLocale()


class LanguageSerializer(ConfigSerializer):
    """ Language serializer """
    _traditional_aliases = {
        "zh_HK", "zh_TW", "zh_MO", "zh_Hant", "zh_Hant_TW", "zh_Hant_HK", "zh_Hant_MO"
    }

    def serialize(self, language):
        return language.value.name() if language != Language.AUTO else "Auto"

    def deserialize(self, value: str):
        if value == "Auto":
            return Language.AUTO

        locale_name = value.replace('-', '_')
        if locale_name in self._traditional_aliases or locale_name.startswith("zh_Hant"):
            return Language.CHINESE_TRADITIONAL

        # 兼容 en_* 配置
        if locale_name.startswith("en"):
            return Language.ENGLISH

        if locale_name.startswith("zh"):
            return Language.CHINESE_SIMPLIFIED

        return Language.CHINESE_SIMPLIFIED


# ========================================================
# 新增：专门用来对付复杂列表字典的序列化器，保证数据能存进硬盘
# ========================================================
class TaskSequenceSerializer(ConfigSerializer):
    def serialize(self, sequence):
        # 存入配置时，将其转化为 JSON 字符串
        return json.dumps(sequence, ensure_ascii=False)

    def deserialize(self, value):
        # 读取配置时，将 JSON 字符串还原为对象
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                pass
        elif isinstance(value, list):
            return value
        # 读不到就返回空列表，让业务层的 _normalize_task_sequence 去补全
        return []
# ========================================================


def isWin11():
    return sys.platform == 'win32' and sys.getwindowsversion().build >= 22000


def normalize_app_locale(locale: QLocale) -> QLocale:
    if not isinstance(locale, QLocale):
        locale = QLocale(str(locale))

    locale_name = locale.name().replace('-', '_')
    if locale_name in {"zh_HK", "zh_TW", "zh_MO", "zh_Hant", "zh_Hant_TW", "zh_Hant_HK", "zh_Hant_MO"} \
            or locale_name.startswith("zh_Hant"):
        return QLocale(QLocale.Chinese, QLocale.HongKong)
    if locale_name.startswith("zh"):
        return QLocale(QLocale.Chinese, QLocale.China)
    return locale


def get_system_ui_locale() -> QLocale:
    if sys.platform == 'win32':
        try:
            language_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            locale_name = pylocale.windows_locale.get(language_id)
            if locale_name:
                return QLocale(locale_name)
        except Exception:
            pass
    return QLocale.system()


def resolve_configured_locale(language_config=None) -> QLocale:
    if language_config is None:
        language_config = config.get(config.language)

    if language_config == config.language.defaultValue:
        return normalize_app_locale(get_system_ui_locale())

    if isinstance(language_config, Language):
        if language_config == Language.AUTO:
            return normalize_app_locale(get_system_ui_locale())
        return normalize_app_locale(language_config.value)

    if isinstance(language_config, QLocale):
        return normalize_app_locale(language_config)

    if isinstance(language_config, str):
        language = LanguageSerializer().deserialize(language_config)
        return resolve_configured_locale(language)

    return normalize_app_locale(get_system_ui_locale())


def is_non_chinese_ui_language() -> bool:
    """Whether current UI language context should be treated as non-Chinese."""
    locale_name = resolve_configured_locale().name().replace('-', '_')
    return not locale_name.startswith("zh")


def is_traditional_ui_language() -> bool:
    """Whether current UI language context should be treated as Traditional Chinese."""
    locale_name = resolve_configured_locale().name().replace('-', '_')
    if locale_name in {"zh_HK", "zh_TW", "zh_MO", "zh_Hant", "zh_Hant_TW", "zh_Hant_HK", "zh_Hant_MO"}:
        return True
    return locale_name.startswith("zh_Hant")


class Config(QConfig):
    """ Config of application """

    # =========================================================
    # 1. 主窗口与基础设置 (MainWindow & Built-in)
    # =========================================================
    micaEnabled  = ConfigItem("MainWindow", "MicaEnabled", isWin11(), BoolValidator())
    language     = OptionsConfigItem("MainWindow", "Language", Language.AUTO, OptionsValidator(Language), LanguageSerializer(), restart=True)
    dpiScale     = OptionsConfigItem("MainWindow", "DpiScale", "Auto", OptionsValidator([1, 1.25, 1.5, 1.75, 2, "Auto"]), restart=True)
    position     = ConfigItem("MainWindow", "position", None)
    nav_expanded = ConfigItem("MainWindow", "NavExpanded", True, BoolValidator())
    is_ocr       = ConfigItem("MainWindow", "is_ocr", False, BoolValidator())

    # =========================================================
    # 2. 系统与个性化设置 (Settings - Personal & Update)
    # =========================================================
    enter_interface       = OptionsConfigItem("setting_personal", "enter_interface", 0, OptionsValidator([0, 1, 2]))
    server_interface      = OptionsConfigItem("setting_personal", "server_interface", 0, OptionsValidator([0, 1, 2, 3]))
    isLog                 = ConfigItem("setting_personal", "isLog", False, BoolValidator())
    isInputLog            = ConfigItem("setting_personal", "isInputLog", False, BoolValidator())
    showScreenshot        = ConfigItem("setting_personal", "showScreenshot", False, BoolValidator())
    windowTrackingInput   = ConfigItem("setting_personal", "windowTrackingInput", True, BoolValidator())
    windowTrackingAlpha   = ConfigItem("setting_personal", "windowTrackingAlpha", 1)
    saveScaleCache        = ConfigItem("setting_personal", "saveScaleCache", False, BoolValidator(), restart=True)
    ocr_use_gpu           = ConfigItem("setting_personal", "ocr_use_gpu", False, BoolValidator())  # Abandoned, kept for config compatibility
    is_resize             = ConfigItem("setting_personal", "is_resize", None)
    auto_start_task       = ConfigItem("setting_personal", "auto_start_task", False, BoolValidator())
    auto_boot_startup     = ConfigItem("setting_personal", "auto_boot_startup", False, BoolValidator())
    inform_message        = ConfigItem("setting_personal", "inform_message", True, BoolValidator())

    checkUpdateAtStartUp     = ConfigItem("Update", "CheckUpdateAtStartUp", True, BoolValidator())
    checkPrereleaseForStable = ConfigItem("Update", "CheckPrereleaseForStable", False, BoolValidator())
    github_api_cache         = ConfigItem("Update", "GithubApiCache", {})
    update_proxies           = ConfigItem("Update", "update_proxies", '')
    cpu_support_avx2         = ConfigItem("about", "cpu_support_avx2", None)

    # =========================================================
    # 3. 首页接口与常规选项 (Home Interface)
    # =========================================================
    date_tip                    = ConfigItem("home_interface_enter", "date_tip", None)
    LineEdit_game_directory     = ConfigItem("home_interface_enter", "LineEdit_game_directory", "./")
    CheckBox_open_game_directly = ConfigItem("home_interface_enter", "CheckBox_open_game_directly", False, BoolValidator())

    CheckBox_entry_1     = ConfigItem("home_interface_option", "CheckBox_entry", False, BoolValidator())
    CheckBox_stamina_2   = ConfigItem("home_interface_option", "CheckBox_stamina", False, BoolValidator())
    CheckBox_shop_3      = ConfigItem("home_interface_option", "CheckBox_shop", False, BoolValidator())
    CheckBox_use_power_4 = ConfigItem("home_interface_option", "CheckBox_use_power", False, BoolValidator())
    CheckBox_person_5    = ConfigItem("home_interface_option", "CheckBox_person", False, BoolValidator())
    CheckBox_chasm_6     = ConfigItem("home_interface_option", "CheckBox_chasm", False, BoolValidator())
    CheckBox_reward_7    = ConfigItem("home_interface_option", "CheckBox_reward", False, BoolValidator())
    CheckBox_weapon_8    = ConfigItem("home_interface_option", "CheckBox_weapon_8", False, BoolValidator())
    CheckBox_shard_exchange_9 = ConfigItem("home_interface_option", "CheckBox_shard_exchange_9", False, BoolValidator())

    ComboBox_run_mode    = OptionsConfigItem("home_interface_after_use", "ComboBox_run_mode", 0, OptionsValidator([0, 1, 2]))
    ComboBox_end_action  = OptionsConfigItem("home_interface_after_use", "ComboBox_end_action", 0, OptionsValidator([0, 1, 2, 3]))

    # --- 角色碎片 (Person) ---
    LineEdit_c1          = ConfigItem("home_interface_person", "LineEdit_c1", "")
    LineEdit_c2          = ConfigItem("home_interface_person", "LineEdit_c2", "")
    LineEdit_c3          = ConfigItem("home_interface_person", "LineEdit_c3", "")
    LineEdit_c4          = ConfigItem("home_interface_person", "LineEdit_c4", "")
    all_characters       = ConfigItem("home_interface_person", "all_characters", 37)
    CheckBox_is_use_chip = ConfigItem("home_interface_person", "CheckBox_is_use_chip", False, BoolValidator())

    # --- 体力设置 (Power) ---
    ComboBox_power_day    = OptionsConfigItem("home_interface_power", "ComboBox_power_day", -1, OptionsValidator([-1, 0, 1, 2, 3, 4, 5]))
    ComboBox_power_usage  = OptionsConfigItem("home_interface_power", "ComboBox_power_usage", -1, OptionsValidator([-1, 0, 1, 2, 3, 4, 5]))
    CheckBox_is_use_power = ConfigItem("home_interface_power", "CheckBox_is_use_power", False, BoolValidator())
    update_data           = ConfigItem("home_interface_power", "update_data", None)
    task_name             = ConfigItem("home_interface_power", "task_name", "")

    # --- 奖励与后勤 (Reward) ---
    CheckBox_mail        = ConfigItem("home_interface_reward", "CheckBox_mail", False, BoolValidator())
    CheckBox_fish_bait   = ConfigItem("home_interface_reward", "CheckBox_fish_bait", False, BoolValidator())
    CheckBox_dormitory   = ConfigItem("home_interface_reward", "CheckBox_dormitory", False, BoolValidator())
    CheckBox_redeem_code = ConfigItem("home_interface_reward", "CheckBox_redeem_code", False, BoolValidator())
    used_codes           = ConfigItem("home_interface_reward", "used_codes", [])
    import_codes         = ConfigItem("home_interface_reward", "import_codes", [])

    # --- 商店购物 (Shopping) ---
    CheckBox_buy_3  = ConfigItem("home_interface_shopping", "CheckBox_buy_3", False, BoolValidator())
    CheckBox_buy_4  = ConfigItem("home_interface_shopping", "CheckBox_buy_4", False, BoolValidator())
    CheckBox_buy_5  = ConfigItem("home_interface_shopping", "CheckBox_buy_5", False, BoolValidator())
    CheckBox_buy_6  = ConfigItem("home_interface_shopping", "CheckBox_buy_6", False, BoolValidator())
    CheckBox_buy_7  = ConfigItem("home_interface_shopping", "CheckBox_buy_7", False, BoolValidator())
    CheckBox_buy_8  = ConfigItem("home_interface_shopping", "CheckBox_buy_8", False, BoolValidator())
    CheckBox_buy_9  = ConfigItem("home_interface_shopping", "CheckBox_buy_9", False, BoolValidator())
    CheckBox_buy_10 = ConfigItem("home_interface_shopping", "CheckBox_buy_10", False, BoolValidator())
    CheckBox_buy_11 = ConfigItem("home_interface_shopping", "CheckBox_buy_11", False, BoolValidator())
    CheckBox_buy_12 = ConfigItem("home_interface_shopping", "CheckBox_buy_12", False, BoolValidator())
    CheckBox_buy_13 = ConfigItem("home_interface_shopping", "CheckBox_buy_13", False, BoolValidator())
    CheckBox_buy_14 = ConfigItem("home_interface_shopping", "CheckBox_buy_14", False, BoolValidator())
    CheckBox_buy_15 = ConfigItem("home_interface_shopping", "CheckBox_buy_15", False, BoolValidator())

    item_person_0  = ConfigItem("home_interface_shopping_person", "item_person_0", False, BoolValidator())
    item_person_1  = ConfigItem("home_interface_shopping_person", "item_person_1", False, BoolValidator())
    item_person_2  = ConfigItem("home_interface_shopping_person", "item_person_2", False, BoolValidator())
    item_person_3  = ConfigItem("home_interface_shopping_person", "item_person_3", False, BoolValidator())
    item_person_4  = ConfigItem("home_interface_shopping_person", "item_person_4", False, BoolValidator())
    item_person_5  = ConfigItem("home_interface_shopping_person", "item_person_5", False, BoolValidator())
    item_person_6  = ConfigItem("home_interface_shopping_person", "item_person_6", False, BoolValidator())
    item_person_7  = ConfigItem("home_interface_shopping_person", "item_person_7", False, BoolValidator())
    item_person_8  = ConfigItem("home_interface_shopping_person", "item_person_8", False, BoolValidator())
    item_person_9  = ConfigItem("home_interface_shopping_person", "item_person_9", False, BoolValidator())
    item_person_10 = ConfigItem("home_interface_shopping_person", "item_person_10", False, BoolValidator())
    item_person_11 = ConfigItem("home_interface_shopping_person", "item_person_11", False, BoolValidator())
    item_person_12 = ConfigItem("home_interface_shopping_person", "item_person_12", False, BoolValidator())
    item_person_13 = ConfigItem("home_interface_shopping_person", "item_person_13", False, BoolValidator())

    item_weapon_0 = ConfigItem("home_interface_shopping_weapon", "item_weapon_0", False, BoolValidator())
    item_weapon_1 = ConfigItem("home_interface_shopping_weapon", "item_weapon_1", False, BoolValidator())
    item_weapon_2 = ConfigItem("home_interface_shopping_weapon", "item_weapon_2", False, BoolValidator())
    item_weapon_3 = ConfigItem("home_interface_shopping_weapon", "item_weapon_3", False, BoolValidator())

    # 信源碎片相关设置
    enable_receive_shards = ConfigItem("ShardExchange", "enable_receive_shards", True, BoolValidator())
    enable_gift_shards    = ConfigItem("ShardExchange", "enable_gift_shards", True, BoolValidator())
    enable_recycle_shards = ConfigItem("ShardExchange", "enable_recycle_shards", True, BoolValidator())

    # =========================================================
    # 4. 自动化任务调度清单 (DailyTasks Sequence)
    # =========================================================
    daily_task_sequence = ConfigItem(
        "DailyTasks", "TaskSequence",
        [
            {
                "id": "task_login", "enabled": False, "use_periodic": False, "last_run": 0,
                "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
                "execution_config":  [{"type": "daily", "day": 0, "time": "05:00", "max_runs": 1}]
            },
            {
                "id": "task_supplies", "enabled": False, "use_periodic": False, "last_run": 0,
                "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
                "execution_config":  [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]
            },
            {
                "id": "task_shop", "enabled": False, "use_periodic": False, "last_run": 0,
                "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
                "execution_config":  [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]
            },
            {
                "id": "task_stamina", "enabled": False, "use_periodic": False, "last_run": 0,
                "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
                "execution_config":  [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]
            },
            {
                "id": "task_shards", "enabled": False, "use_periodic": False, "last_run": 0,
                "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
                "execution_config":  [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]
            },
            {
                "id": "task_chasm", "enabled": False, "use_periodic": False, "last_run": 0,
                "activation_config": [{"type": "weekly", "day": 1, "time": "10:00", "max_runs": 1}],
                "execution_config":  [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]
            },
            {
                "id": "task_operation", "enabled": False, "use_periodic": False, "last_run": 0,
                "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
                "execution_config":  [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]
            },
            {
                "id": "task_reward", "enabled": False, "use_periodic": False, "last_run": 0,
                "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
                "execution_config":  [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]
            },
            {
                "id": "task_weapon", "enabled": False, "use_periodic": False, "last_run": 0,
                "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
                "execution_config":  [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]
            },
            {
                "id": "task_shard_exchange", "enabled": False, "use_periodic": False, "last_run": 0,
                "activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
                "execution_config":  [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]
            },
        ], serializer=TaskSequenceSerializer()
    )

    # =========================================================
    # 5. 小游戏自动化 (Minigames & Modules)
    # =========================================================
    game_title_name = ConfigItem("automation", "game_title_name", "尘白禁区")
    game_language   = OptionsConfigItem("automation", "game_language", 0, OptionsValidator([0, 1]))

    # --- 常规训练 ---
    SpinBox_action_times = ConfigItem("add_action", "SpinBox_action_times", 20)
    ComboBox_run         = OptionsConfigItem("add_action", "ComboBox_run", 0, OptionsValidator([0, 1]))

    # --- 钓鱼相关 ---
    CheckBox_is_save_fish  = ConfigItem("add_fish", "CheckBox_is_save_fish", False, BoolValidator())
    CheckBox_is_limit_time = ConfigItem("add_fish", "CheckBox_is_limit_time", False, BoolValidator())
    SpinBox_fish_times     = ConfigItem("add_fish", "SpinBox_fish_times", 1)
    LineEdit_fish_base     = ConfigItem("add_fish", "LineEdit_fish_base", "22,255,255")
    LineEdit_fish_lower    = ConfigItem("add_fish", "LineEdit_fish_lower", "20,220,245")
    LineEdit_fish_upper    = ConfigItem("add_fish", "LineEdit_fish_upper", "25,255,255")
    ComboBox_fishing_mode  = OptionsConfigItem("add_fish", "ComboBox_fishing_mode", 0, OptionsValidator([0, 1]))
    ComboBox_lure_type     = OptionsConfigItem("add_fish", "ComboBox_lure_type", 0, OptionsValidator([0, 1, 2, 3, 4, 5, 6, 7]))
    LineEdit_fish_key      = ConfigItem("add_fish", "LineEdit_fish_key", "space")
    fish_key_list          = ConfigItem("add_fish", "fish_key_list", ['shift', 'space', 'ctrl'])

    # --- 异星守护 / 迷宫 / 按摩 / 酒馆 ---
    ComboBox_mode        = OptionsConfigItem("add_alien", "ComboBox_mode", 0, OptionsValidator([0, 1]))
    ComboBox_mode_maze   = OptionsConfigItem("add_maze", "ComboBox_mode_maze", 0, OptionsValidator([0, 1]))
    ComboBox_wife        = OptionsConfigItem("add_massaging", "ComboBox_wife", 0, OptionsValidator([0, 1, 2, 3, 4]))
    ComboBox_card_mode   = OptionsConfigItem("add_drink", "ComboBox_card_mode", 0, OptionsValidator([0, 1]))
    SpinBox_drink_times  = ConfigItem("add_drink", "SpinBox_drink_times", -1)
    CheckBox_is_speed_up = ConfigItem("add_drink", "CheckBox_is_speed_up", False, BoolValidator())

    # --- 心动水弹 ---
    SpinBox_water_win_times   = ConfigItem("add_water", "SpinBox_water_win_times", 5)
    Slider_count_threshold    = ConfigItem("add_water", "Slider_count_threshold", 60)
    Slider_template_threshold = ConfigItem("add_water", "Slider_template_threshold", 60)

    # --- 信源解析 ---
    SpinBox_max_solutions    = ConfigItem("jigsaw", "SpinBox_max_solutions", 10)
    LineEdit_jigsaw_piece_1  = ConfigItem("pieces_num", "LineEdit_jigsaw_piece_1", "0")
    LineEdit_jigsaw_piece_2  = ConfigItem("pieces_num", "LineEdit_jigsaw_piece_2", "0")
    LineEdit_jigsaw_piece_3  = ConfigItem("pieces_num", "LineEdit_jigsaw_piece_3", "0")
    LineEdit_jigsaw_piece_4  = ConfigItem("pieces_num", "LineEdit_jigsaw_piece_4", "0")
    LineEdit_jigsaw_piece_5  = ConfigItem("pieces_num", "LineEdit_jigsaw_piece_5", "0")
    LineEdit_jigsaw_piece_6  = ConfigItem("pieces_num", "LineEdit_jigsaw_piece_6", "0")
    LineEdit_jigsaw_piece_7  = ConfigItem("pieces_num", "LineEdit_jigsaw_piece_7", "0")
    LineEdit_jigsaw_piece_8  = ConfigItem("pieces_num", "LineEdit_jigsaw_piece_8", "0")
    LineEdit_jigsaw_piece_9  = ConfigItem("pieces_num", "LineEdit_jigsaw_piece_9", "0")
    LineEdit_jigsaw_piece_10 = ConfigItem("pieces_num", "LineEdit_jigsaw_piece_10", "0")
    LineEdit_jigsaw_piece_11 = ConfigItem("pieces_num", "LineEdit_jigsaw_piece_11", "0")

    # --- 抓帕鲁 ---
    CheckBox_capture_pals_partner   = ConfigItem("add_capture_pals", "CheckBox_capture_pals_partner", True, BoolValidator())
    CheckBox_capture_pals_adventure = ConfigItem("add_capture_pals", "CheckBox_capture_pals_adventure", False, BoolValidator())
    CheckBox_capture_pals_sync      = ConfigItem("add_capture_pals", "CheckBox_capture_pals_sync", False, BoolValidator())

    ComboBox_capture_pals_partner_mode   = ConfigItem("add_capture_pals", "ComboBox_capture_pals_partner_mode", 0)
    ComboBox_capture_pals_adventure_mode = ConfigItem("add_capture_pals", "ComboBox_capture_pals_adventure_mode", 1)

    SpinBox_capture_pals_sync_every_min            = ConfigItem("add_capture_pals", "SpinBox_capture_pals_sync_every_min", 5)
    SpinBox_capture_pals_partner_fixed_interval    = ConfigItem("add_capture_pals", "SpinBox_capture_pals_partner_fixed_interval", 35)
    SpinBox_capture_pals_partner_patrol_interval   = ConfigItem("add_capture_pals", "SpinBox_capture_pals_partner_patrol_interval", 10)
    SpinBox_capture_pals_adventure_fixed_interval  = ConfigItem("add_capture_pals", "SpinBox_capture_pals_adventure_fixed_interval", 300)
    SpinBox_capture_pals_adventure_patrol_interval = ConfigItem("add_capture_pals", "SpinBox_capture_pals_adventure_patrol_interval", 1200)

config = Config()
config.themeMode.value = Theme.AUTO
qconfig.load(str(CONFIG_FILE.absolute()), config)