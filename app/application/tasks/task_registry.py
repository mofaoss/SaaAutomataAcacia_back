# coding:utf-8
from app.modules.alien_guardian.usecase.alien_guardian_usecase import AlienGuardianModule
from app.modules.capture_pals.usecase.capture_pals_usecase import CapturePalsModule
from app.modules.chasm.usecase.chasm_usecase import ChasmModule
from app.modules.close_game.usecase.close_game_usecase import CloseGameModule
from app.modules.collect_supplies.usecase.collect_supplies_usecase import CollectSuppliesModule
from app.modules.drink.usecase.drink_usecase import DrinkModule
from app.modules.enter_game.usecase.enter_game_usecase import EnterGameModule
from app.modules.fishing.usecase.fishing_usecase import FishingModule
from app.modules.get_reward.usecase.get_reward_usecase import GetRewardModule
from app.modules.jigsaw.usecase.shard_exchange_usecase import ShardExchangeModule
from app.modules.maze.usecase.maze_usecase import MazeModule
from app.modules.operation_action.usecase.operation_usecase import OperationModule
from app.modules.person.usecase.person_usecase import PersonModule
from app.modules.shopping.usecase.shopping_usecase import ShoppingModule
from app.modules.upgrade.usecase.weapon_upgrade_usecase import WeaponUpgradeModule
from app.modules.use_power.usecase.use_power_usecase import UsePowerModule
from app.modules.water_bomb.usecase.water_bomb_usecase import WaterBombModule

from app.application.tasks.daily_policy import PRIMARY_TASK_ID
from app.application.tasks.task_definition import TaskDefinition, TaskDomain


DAILY_TASKS: list[TaskDefinition] = [
    TaskDefinition(PRIMARY_TASK_ID, EnterGameModule, "自动登录", "Auto Login", TaskDomain.DAILY, ui_page_index=0, option_key="CheckBox_entry_1", requires_home_sync=False, is_mandatory=True, force_first=True),
    TaskDefinition("task_supplies", CollectSuppliesModule, "领取福利", "Collect Supplies", TaskDomain.DAILY, ui_page_index=1, option_key="CheckBox_stamina_2"),
    TaskDefinition("task_shop", ShoppingModule, "商店购买", "Shop", TaskDomain.DAILY, ui_page_index=2, option_key="CheckBox_shop_3"),
    TaskDefinition("task_stamina", UsePowerModule, "体力扫荡", "Use Stamina", TaskDomain.DAILY, ui_page_index=3, option_key="CheckBox_use_power_4"),
    TaskDefinition("task_shards", PersonModule, "角色碎片", "Character Shards", TaskDomain.DAILY, ui_page_index=4, option_key="CheckBox_person_5"),
    TaskDefinition("task_chasm", ChasmModule, "精神拟境", "Neural Sim", TaskDomain.DAILY, ui_page_index=5, option_key="CheckBox_chasm_6"),
    TaskDefinition("task_reward", GetRewardModule, "收取奖励", "Claim Rewards", TaskDomain.DAILY, ui_page_index=6, option_key="CheckBox_reward_7"),
    TaskDefinition("task_operation", OperationModule, "常规训练", "Operation", TaskDomain.DAILY, ui_page_index=7, option_key="CheckBox_operation_8"),
    TaskDefinition("task_weapon", WeaponUpgradeModule, "武器升级", "Weapon Upgrade", TaskDomain.DAILY, ui_page_index=8, option_key="CheckBox_weapon_8"),
    TaskDefinition("task_shard_exchange", ShardExchangeModule, "信源碎片", "Shard Exchange", TaskDomain.DAILY, ui_page_index=9, option_key="CheckBox_shard_exchange_9"),
    TaskDefinition("task_close_game", CloseGameModule, "执行退出", "Execute Exit", TaskDomain.DAILY, ui_page_index=10, option_key="CheckBox_close_game_10", requires_home_sync=False),
]

ADDITIONAL_TASKS: list[TaskDefinition] = [
    TaskDefinition("fishing", FishingModule, "钓鱼", "Fishing", TaskDomain.ADDITIONAL, page_attr="page_fishing", card_widget_attr="SimpleCardWidget_fish", log_widget_attr="textBrowser_log_fishing", start_button_attr="PushButton_start_fishing"),
    TaskDefinition("action", OperationModule, "常规训练", "Operation", TaskDomain.ADDITIONAL, page_attr="page_action", card_widget_attr="SimpleCardWidget_action", log_widget_attr="textBrowser_log_action", start_button_attr="PushButton_start_action"),
    TaskDefinition("water_bomb", WaterBombModule, "心动水弹", "Water Bomb", TaskDomain.ADDITIONAL, page_attr="page_water_bomb", card_widget_attr="SimpleCardWidget_water_bomb", log_widget_attr="textBrowser_log_water_bomb", start_button_attr="PushButton_start_water_bomb"),
    TaskDefinition("alien_guardian", AlienGuardianModule, "异星守护", "Alien Guardian", TaskDomain.ADDITIONAL, page_attr="page_alien_guardian", card_widget_attr="SimpleCardWidget_alien_guardian", log_widget_attr="textBrowser_log_alien_guardian", start_button_attr="PushButton_start_alien_guardian"),
    TaskDefinition("maze", MazeModule, "迷宫", "Maze", TaskDomain.ADDITIONAL, page_attr="page_maze", card_widget_attr="SimpleCardWidget_maze", log_widget_attr="textBrowser_log_maze", start_button_attr="PushButton_start_maze"),
    TaskDefinition("drink", DrinkModule, "喝酒", "Drink", TaskDomain.ADDITIONAL, page_attr="page_card", card_widget_attr="SimpleCardWidget_card", log_widget_attr="textBrowser_log_drink", start_button_attr="PushButton_start_drink"),
    TaskDefinition("capture_pals", CapturePalsModule, "抓帕鲁", "Capture Pals", TaskDomain.ADDITIONAL, page_attr="page_capture_pals", card_widget_attr="SimpleCardWidget_capture_pals", log_widget_attr="textBrowser_log_capture_pals", start_button_attr="PushButton_start_capture_pals"),
]


DAILY_TASK_REGISTRY = {task.id: task.to_legacy_meta() for task in DAILY_TASKS}
DAILY_TASKS_BY_ID = {task.id: task for task in DAILY_TASKS}
ADDITIONAL_TASKS_BY_ID = {task.id: task for task in ADDITIONAL_TASKS}
