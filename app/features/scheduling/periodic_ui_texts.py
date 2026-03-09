from __future__ import annotations


def apply_periodic_module_texts(ui, *, is_non_chinese_ui: bool, ui_text_fn):
    def w(name: str):
        return ui.require_module_widget(name)

    w("ComboBox_power_day").addItems(["1", "2", "3", "4", "5", "6"])
    w("ComboBox_power_usage").addItems(
        [
            ui_text_fn("活动材料本", "Event Stages"),
            ui_text_fn("刷常规后勤", "Operation Logistics"),
        ]
    )
    w("ComboBox_run").addItems(
        ["Toggle Sprint", "Hold Sprint"]
        if is_non_chinese_ui
        else ["切换疾跑", "按住疾跑"]
    )

    for line_edit in [w("LineEdit_c1"), w("LineEdit_c2"), w("LineEdit_c3"), w("LineEdit_c4")]:
        line_edit.setPlaceholderText(ui_text_fn("未输入", "Not set"))

    w("BodyLabel_enter_tip").setText(
        "### Tips\n* Select your server in Settings\n* Enable \"Auto open game\" and select the correct game path by the tutorial above\n* Game will be launched automatically when you click start or when a task needs to execute, no need to set schedule\n* Schedule for auto login is not affected by other modules"
        if is_non_chinese_ui
        else "### 提示\n* 去设置里选择你的区服\n* 建议勾选“自动打开游戏”，请根据上方教程选择对应的路径\n* 点击开始或有任务需要执行时会自动拉起游戏，无需设置计划 \n* 自动登录的计划功能不受其他模块影响"
    )
    w("BodyLabel_person_tip").setText(
        "### Tips\n* Enter codename instead of full name, e.g. use \"朝翼\" (Dawnwing) for \"凯茜娅-朝翼\" (Katya-Dawnwing)"
        if is_non_chinese_ui
        else "### 提示\n* 输入代号而非全名，比如想要刷“凯茜娅-朝翼”，就输入“朝翼”"
    )
    w("BodyLabel_collect_supplies").setText(
        "### Tips\n* Default: Always claim Supply Station stamina and friend stamina \n* Enable \"Redeem Code\" to fetch and redeem online codes automatically\n* Online codes are maintained by developers and may not always be updated in time\n* You can import a txt file for batch redeem (one code per line)"
        if is_non_chinese_ui
        else "### 提示 \n* 默认必领供应站体力和好友体力\n* 勾选“领取兑换码”会自动拉取在线兑换码进行兑换\n* 在线兑换码由开发者维护，更新不一定及时\n* 导入txt文本文件可以批量使用用户兑换码，txt需要一行一个兑换码"
    )
    w("BodyLabel_chasm_tip").setText(
        "### Tips\n* Neural Simulation opens every Tuesday at 10:00"
        if is_non_chinese_ui
        else "### 提示\n* 拟境每周2的10:00开启"
    )
    w("BodyLabel_reward_tip").setText(
        "### Tips\n* Claim monthly card and daily rewards"
        if is_non_chinese_ui
        else "### 提示\n* 领取大月卡和日常奖励"
    )
    w("BodyLabel_weapon_tip").setText(
        "### Tips\n* Automatically identifies and consumes upgrade materials\n* Stops when weapon reaches max level"
        if is_non_chinese_ui
        else "### 提示\n* 自动从背包选择第一把武器进行强化\n* 自动识别并消耗升级材料，直到武器等级提升或满级"
    )
    w("BodyLabel_shard_tip").setText(
        "### Tips\n* Auto receive, gift, and recycle puzzle shards\n* Retains at least 15 of each shard when recycling"
        if is_non_chinese_ui
        else "### 提示\n* 自动进行基地信源碎片的接收、赠送和回收\n* 回收时每种碎片默认至少保留15个"
    )
    w("BodyLabel_tip_action").setText(
        "### Tips\n* Auto-run operation \n* Repeats the first training stage for specified times with no stamina cost\n* Useful for weekly pass mission count"
        if is_non_chinese_ui
        else "### 提示\n* 重复刷指定次数无需体力的实战训练第一关\n* 用于完成凭证20次常规行动周常任务"
    )

    w("PrimaryPushButton_path_tutorial").setText(ui_text_fn("查看教程", "Tutorial"))
    w("StrongBodyLabel_4").setText(ui_text_fn("启动器中查看游戏路径", "Find game path in launcher"))
    w("CheckBox_open_game_directly").setText(ui_text_fn("自动打开游戏", "Auto open game"))
    w("PushButton_select_directory").setText(ui_text_fn("选择", "Browse"))

    w("CheckBox_mail").setText(ui_text_fn("领取邮件", "Claim Mail"))
    w("CheckBox_fish_bait").setText(ui_text_fn("领取鱼饵", "Claim Bait"))
    w("CheckBox_dormitory").setText(ui_text_fn("宿舍碎片", "Dorm Shards"))
    w("CheckBox_redeem_code").setText(ui_text_fn("领取兑换码", "Redeem Codes"))
    w("PrimaryPushButton_import_codes").setText(ui_text_fn("导入", "Import"))
    w("PushButton_reset_codes").setText(ui_text_fn("重置", "Reset"))

    w("StrongBodyLabel").setText(ui_text_fn("选择要购买的商品", "Select items to buy"))
    shop_items = [
        ("CheckBox_buy_3", "通用强化套件", "Universal Enhancement Kit"),
        ("CheckBox_buy_4", "优选强化套件", "Premium Enhancement Kit"),
        ("CheckBox_buy_5", "精致强化套件", "Exquisite Enhancement Kit"),
        ("CheckBox_buy_6", "新手战斗记录", "Beginner Battle Record"),
        ("CheckBox_buy_7", "普通战斗记录", "Standard Battle Record"),
        ("CheckBox_buy_8", "优秀战斗记录", "Advanced Battle Record"),
        ("CheckBox_buy_9", "初级职级认证", "Junior Rank Certification"),
        ("CheckBox_buy_10", "中级职级认证", "Intermediate Rank Certification"),
        ("CheckBox_buy_11", "高级职级认证", "Senior Rank Certification"),
        ("CheckBox_buy_12", "合成颗粒", "Synthetic Particles"),
        ("CheckBox_buy_13", "芳烃塑料", "Hydrocarbon Plastic"),
        ("CheckBox_buy_14", "单极纤维", "Monopolar Fibers"),
        ("CheckBox_buy_15", "光纤轴突", "Fiber Axon"),
    ]
    for attr, zh, en in shop_items:
        w(attr).setText(ui_text_fn(zh, en))

    w("StrongBodyLabel_2").setText(ui_text_fn("选择体力使用方式", "Stamina usage mode"))
    w("CheckBox_is_use_power").setText(ui_text_fn("自动使用期限", "Auto use expiring"))
    w("BodyLabel_6").setText(ui_text_fn("天内的体力药", "day potion"))

    w("StrongBodyLabel_3").setText(ui_text_fn("选择需要刷碎片的角色", "Select characters for shards"))
    w("BodyLabel_3").setText(ui_text_fn("角色1：", "Character 1:"))
    w("BodyLabel_4").setText(ui_text_fn("角色2：", "Character 2:"))
    w("BodyLabel_5").setText(ui_text_fn("角色3：", "Character 3:"))
    w("BodyLabel_8").setText(ui_text_fn("角色4：", "Character 4:"))
    w("CheckBox_is_use_chip").setText(ui_text_fn("记忆嵌片不足时自动使用2片", "Auto use 2 chips when not enough"))

    w("BodyLabel_22").setText(ui_text_fn("疾跑方式", "Sprint mode"))
    w("BodyLabel_7").setText(ui_text_fn("刷取次数", "Run count"))

    w("CheckBox_receive_shards").setText(ui_text_fn("一键接收", "Auto Receive"))
    w("CheckBox_gift_shards").setText(ui_text_fn("一键赠送", "Auto Gift"))
    w("CheckBox_recycle_shards").setText(ui_text_fn("智能回收", "Smart Recycle"))

    w("CheckBox_close_game").setText(ui_text_fn("退出游戏", "Exit Game"))
    w("CheckBox_close_proxy").setText(ui_text_fn("退出小助手但不关机", "Exit SAA but don't shutdown"))
    w("CheckBox_shutdown").setText(ui_text_fn("关机", "Shutdown PC"))
