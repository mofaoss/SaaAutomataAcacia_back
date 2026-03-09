# -*- coding: utf-8 -*-


PERSON_ITEMS = [
    {"key": "item_person_0", "zh_name": "角色碎片", "en_name": "Character Shards"},
    {"key": "item_person_1", "zh_name": "肴", "en_name": "Yao"},
    {"key": "item_person_2", "zh_name": "安卡希雅", "en_name": "Acacia"},
    {"key": "item_person_3", "zh_name": "里芙", "en_name": "Lyfe"},
    {"key": "item_person_4", "zh_name": "辰星", "en_name": "Chenxing"},
    {"key": "item_person_5", "zh_name": "茉莉安", "en_name": "Marian"},
    {"key": "item_person_6", "zh_name": "芬妮", "en_name": "Fenny"},
    {"key": "item_person_7", "zh_name": "芙提雅", "en_name": "Fritia"},
    {"key": "item_person_8", "zh_name": "瑟瑞斯", "en_name": "Siris"},
    {"key": "item_person_9", "zh_name": "琴诺", "en_name": "Cherno"},
    {"key": "item_person_10", "zh_name": "猫汐尔", "en_name": "Mauxir"},
    {"key": "item_person_11", "zh_name": "晴", "en_name": "Haru"},
    {"key": "item_person_12", "zh_name": "恩雅", "en_name": "Enya"},
    {"key": "item_person_13", "zh_name": "妮塔", "en_name": "Nita"},
]

WEAPON_ITEMS = [
    {"key": "item_weapon_0", "zh_name": "武器", "en_name": "Weapon"},
    {"key": "item_weapon_1", "zh_name": "彩虹打火机", "en_name": "Prismatic Igniter"},
    {"key": "item_weapon_2", "zh_name": "草莓蛋糕", "en_name": "Strawberry Shortcake"},
    {"key": "item_weapon_3", "zh_name": "深海呼唤", "en_name": "Deep Sea's Call"},
]

SHOP_ITEMS = [
    {"key": "CheckBox_buy_3", "zh_name": "通用强化套件", "en_name": "Universal Enhancement Kit"},
    {"key": "CheckBox_buy_4", "zh_name": "优选强化套件", "en_name": "Premium Enhancement Kit"},
    {"key": "CheckBox_buy_5", "zh_name": "精致强化套件", "en_name": "Exquisite Enhancement Kit"},
    {"key": "CheckBox_buy_6", "zh_name": "新手战斗记录", "en_name": "Beginner Battle Record"},
    {"key": "CheckBox_buy_7", "zh_name": "普通战斗记录", "en_name": "Standard Battle Record"},
    {"key": "CheckBox_buy_8", "zh_name": "优秀战斗记录", "en_name": "Advanced Battle Record"},
    {"key": "CheckBox_buy_9", "zh_name": "初级职级认证", "en_name": "Junior Rank Certification"},
    {"key": "CheckBox_buy_10", "zh_name": "中级职级认证", "en_name": "Intermediate Rank Certification"},
    {"key": "CheckBox_buy_11", "zh_name": "高级职级认证", "en_name": "Senior Rank Certification"},
    {"key": "CheckBox_buy_12", "zh_name": "合成颗粒", "en_name": "Synthetic Particles"},
    {"key": "CheckBox_buy_13", "zh_name": "芳烃塑料", "en_name": "Hydrocarbon Plastic"},
    {"key": "CheckBox_buy_14", "zh_name": "单极纤维", "en_name": "Monopolar Fibers"},
    {"key": "CheckBox_buy_15", "zh_name": "光纤轴突", "en_name": "Fiber Axon"},
]


def get_person_text_to_key_map(is_non_chinese: bool):
    """
    Generates a mapping from person display names (both languages) to their internal keys.
    """
    name_key = "en_name" if is_non_chinese else "zh_name"
    mapping = {}
    for item in PERSON_ITEMS:
        # For compatibility, map both EN and ZH names to the same key
        mapping[item["zh_name"]] = item["key"]
        mapping[item["en_name"]] = item["key"]
    return mapping


def get_weapon_text_to_key_map(is_non_chinese: bool):
    """
    Generates a mapping from weapon display names (both languages) to their internal keys.
    """
    name_key = "en_name" if is_non_chinese else "zh_name"
    mapping = {}
    for item in WEAPON_ITEMS:
        mapping[item["zh_name"]] = item["key"]
        mapping[item["en_name"]] = item["key"]
    return mapping


def get_shop_item_key_to_name_map(is_non_chinese: bool):
    """
    Generates a mapping from shop item checkbox keys to their display names.
    """
    name_key = "en_name" if is_non_chinese else "zh_name"
    return {item["key"]: item[name_key] for item in SHOP_ITEMS}


def get_item_key_to_name_map(is_non_chinese: bool):
    """
    Generates a mapping from item keys (person, weapon) to their display names for the current language.
    """
    name_key = "en_name" if is_non_chinese else "zh_name"
    person_map = {item["key"]: item[name_key] for item in PERSON_ITEMS}
    weapon_map = {item["key"]: item[name_key] for item in WEAPON_ITEMS}
    return person_map, weapon_map

def get_shop_item_zh_name_to_display_name_map(is_non_chinese: bool):
    """
    Generates a mapping from a shop item's Chinese name (as the unique identifier)
    to its appropriate display name based on the selected language.
    """
    name_key = "en_name" if is_non_chinese else "zh_name"
    return {item["zh_name"]: item[name_key] for item in SHOP_ITEMS + PERSON_ITEMS + WEAPON_ITEMS}
