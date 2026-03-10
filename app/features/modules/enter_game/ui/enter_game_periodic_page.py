from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
)

from app.framework.infra.runtime.paths import PROJECT_ROOT
from app.framework.ui.views.periodic_base import ModulePageBase
from app.framework.i18n import _


class EnterGamePage(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__("page_5", parent=parent, host_context="periodic", use_default_layout=True)

        top_line = QHBoxLayout()
        self.StrongBodyLabel_4 = StrongBodyLabel(self)
        self.StrongBodyLabel_4.setObjectName("StrongBodyLabel_4")
        self.PrimaryPushButton_path_tutorial = PrimaryPushButton(self)
        self.PrimaryPushButton_path_tutorial.setObjectName("PrimaryPushButton_path_tutorial")
        top_line.addWidget(self.StrongBodyLabel_4)
        top_line.addWidget(self.PrimaryPushButton_path_tutorial)

        self.LineEdit_game_directory = LineEdit(self)
        self.LineEdit_game_directory.setEnabled(False)
        self.LineEdit_game_directory.setObjectName("LineEdit_game_directory")

        action_line = QHBoxLayout()
        self.CheckBox_open_game_directly = CheckBox(self)
        self.CheckBox_open_game_directly.setObjectName("CheckBox_open_game_directly")
        self.PushButton_select_directory = PushButton(self)
        self.PushButton_select_directory.setObjectName("PushButton_select_directory")
        action_line.addWidget(self.CheckBox_open_game_directly, 1)
        action_line.addWidget(self.PushButton_select_directory)

        self.BodyLabel_enter_tip = BodyLabel(self)
        self.BodyLabel_enter_tip.setObjectName("BodyLabel_enter_tip")
        self.BodyLabel_enter_tip.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_enter_tip.setWordWrap(True)

        self.main_layout.addLayout(top_line)
        self.main_layout.addWidget(self.LineEdit_game_directory)
        self.main_layout.addLayout(action_line)
        self.main_layout.addWidget(self.BodyLabel_enter_tip)
        self._apply_i18n()
        self.finalize()

    def _apply_i18n(self):
        self.PrimaryPushButton_path_tutorial.setText(self._ui_text("查看教程", "Tutorial"))
        self.StrongBodyLabel_4.setText(self._ui_text("启动器中查看游戏路径", "Find game path in launcher"))
        self.CheckBox_open_game_directly.setText(self._ui_text("自动打开游戏", "Auto open game"))
        self.PushButton_select_directory.setText(self._ui_text("选择", "Browse"))
        self.BodyLabel_enter_tip.setText(
            "### Tips\n* Select your server in Settings\n* Enable \"Auto open game\" and select the correct game path by the tutorial above\n* Game will be launched automatically when you click start or when a task needs to execute, no need to set schedule\n* Schedule for auto login is not affected by other modules"
            if self._is_non_chinese_ui
            else "### 提示\n* 去设置里选择你的区服\n* 建议勾选“自动打开游戏”，请根据上方教程选择对应的路径\n* 点击开始或有任务需要执行时会自动拉起游戏，无需设置计划 \n* 自动登录的计划功能不受其他模块影响"
        )

    @staticmethod
    def build_path_tutorial_payload(is_non_chinese_ui: bool) -> dict[str, str]:
        title = "How to find the game path" if is_non_chinese_ui else "如何查找对应游戏路径"
        content = (
            'No matter which server/channel you play, first select your server in Settings.\n'
            'For global server, choose a path like "E:\\SteamLibrary\\steamapps\\common\\SNOWBREAK".\n'
            'For CN/Bilibili server, open the Snowbreak launcher and find launcher settings.\n'
            'Then choose the game installation path shown there.'
            if is_non_chinese_ui
            else
            '不管你是哪个渠道服的玩家，第一步都应该先去设置里选服\n国际服选完服之后选择类似"E:\\SteamLibrary\\steamapps\\common\\SNOWBREAK"的路径\n官服和b服的玩家打开尘白启动器，新版或者旧版启动器都找到启动器里对应的设置\n在下面的路径选择中找到并选择刚才你看到的路径'
        )
        image = str(PROJECT_ROOT / "app" / "features" / "assets" / "enter_game" / "path_tutorial.png")
        return {
            "title": title,
            "content": content,
            "image": image,
        }
