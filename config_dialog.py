# -*- coding: utf-8 -*-
"""Apple-style settings dialog for 摸鱼复习条."""

from __future__ import annotations

from copy import deepcopy
from typing import Callable, Optional

from aqt.qt import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QComboBox,
    QFont,
    QFontComboBox,
    QFrame,
    QHBoxLayout,
    QKeySequence,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyleFactory,
    Qt,
    QVBoxLayout,
    QWidget,
)


_DIALOG_STYLE = """
QDialog#MoyuConfigDialog {
    background: #f5f5f7;
}
QScrollArea {
    background: transparent;
    border: none;
}
QWidget#ScrollInner {
    background: transparent;
}
QLabel#PageTitle {
    color: #1d1d1f;
    font-size: 26px;
    font-weight: 700;
    letter-spacing: -0.5px;
}
QLabel#PageSub {
    color: #86868b;
    font-size: 13px;
}
QLabel#SectionLabel {
    color: #86868b;
    font-size: 12px;
    font-weight: 600;
    padding: 2px 2px 6px 2px;
}
QFrame#Group {
    background: #ffffff;
    border: 1px solid rgba(0,0,0,0.04);
    border-radius: 14px;
}
QWidget#Row {
    background: transparent;
    min-height: 52px;
    max-height: 64px;
}
QLabel#RowLabel {
    color: #1d1d1f;
    font-size: 14px;
    font-weight: 500;
}
QLabel#RowHint {
    color: #86868b;
    font-size: 11px;
}
QFrame#Separator {
    background: rgba(60,60,67,0.12);
    max-height: 1px;
    min-height: 1px;
    border: none;
    margin-left: 14px;
    margin-right: 0px;
}
QLineEdit#CapsuleInput, QSpinBox#CapsuleInput, QDoubleSpinBox#CapsuleInput,
QFontComboBox#CapsuleInput, QComboBox#CapsuleInput {
    min-height: 34px;
    max-height: 34px;
    min-width: 148px;
    max-width: 220px;
    padding: 0 14px;
    border: none;
    border-radius: 17px;
    background: #f2f2f7;
    color: #1d1d1f;
    font-size: 13px;
    selection-background-color: #007aff;
}
QLineEdit#CapsuleInput:focus, QSpinBox#CapsuleInput:focus,
QDoubleSpinBox#CapsuleInput:focus, QFontComboBox#CapsuleInput:focus,
QComboBox#CapsuleInput:focus {
    background: #e5e5ea;
}
QComboBox#CapsuleInput::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 28px;
    border: none;
    background: transparent;
}
QComboBox#CapsuleInput::down-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8e8e93;
    margin-right: 12px;
}
QComboBox#CapsuleInput QAbstractItemView {
    background: #ffffff;
    border: 1px solid rgba(0,0,0,0.08);
    border-radius: 12px;
    padding: 6px;
    outline: none;
    selection-background-color: #007aff;
    selection-color: #ffffff;
}
QSpinBox#CapsuleInput::up-button, QSpinBox#CapsuleInput::down-button,
QDoubleSpinBox#CapsuleInput::up-button, QDoubleSpinBox#CapsuleInput::down-button {
    width: 16px;
    border: none;
    background: transparent;
    margin-right: 6px;
}
QFontComboBox#CapsuleInput::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 28px;
    border: none;
    background: transparent;
}
QFontComboBox#CapsuleInput::down-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8e8e93;
    margin-right: 12px;
}
QFontComboBox#CapsuleInput QAbstractItemView {
    background: #ffffff;
    border: 1px solid rgba(0,0,0,0.08);
    border-radius: 12px;
    padding: 6px;
    outline: none;
    selection-background-color: #007aff;
    selection-color: #ffffff;
}
QCheckBox {
    color: #1d1d1f;
    font-size: 14px;
    spacing: 10px;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 6px;
    border: none;
    background: #e8e8ed;
}
QCheckBox::indicator:checked {
    background: #007aff;
}
QFrame#Footer {
    background: #f5f5f7;
    border-top: 1px solid rgba(60,60,67,0.12);
}
QPushButton#SaveBtn {
    background: #007aff;
    color: white;
    border: none;
    border-radius: 10px;
    min-height: 36px;
    min-width: 96px;
    padding: 0 18px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#SaveBtn:hover { background: #0066d6; }
QPushButton#SecondaryBtn {
    background: #e8e8ed;
    color: #1d1d1f;
    border: none;
    border-radius: 10px;
    min-height: 36px;
    min-width: 80px;
    padding: 0 16px;
    font-size: 14px;
    font-weight: 560;
}
QPushButton#SecondaryBtn:hover { background: #dedee3; }
"""


def _style_capsule(widget: QWidget) -> None:
    """Force non-native style so gray pill look applies on macOS."""
    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        widget.setStyle(fusion)
    widget.setObjectName("CapsuleInput")
    widget.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
    widget.setFixedHeight(34)


class CapsuleKeyEdit(QLineEdit):
    """Single-shortcut capture field with capsule styling."""

    def __init__(self, initial: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._seq = QKeySequence(initial)
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setPlaceholderText("点击后按键")
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        _style_capsule(self)
        self._refresh()

    def _refresh(self) -> None:
        text = self._seq.toString(QKeySequence.SequenceFormat.NativeText).strip()
        self.setText(text or "")

    def keySequence(self) -> QKeySequence:
        return self._seq

    def setKeySequence(self, seq: QKeySequence) -> None:
        self._seq = QKeySequence(seq)
        self._refresh()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self._seq = QKeySequence()
            self._refresh()
            event.accept()
            return
        if key in (
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        ):
            event.accept()
            return
        try:
            self._seq = QKeySequence(event.keyCombination())
        except Exception:
            self._seq = QKeySequence(key)
        self._refresh()
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.selectAll()
        super().mousePressEvent(event)


def _defaults() -> dict:
    return {
        "opacity": 1.0,
        "opaque_style_version": 1,
        "auto_show": True,
        "mathjax": True,
        "pos_x": None,
        "pos_y": None,
        "card_width": 330,
        "presentation_version": 2,
        "font_family": "PingFang SC",
        "font_size": 15,
        "capsule_style_version": 1,
        "toggle_shortcut": "Ctrl+Shift+M",
        "click_grade": "good",
        "double_click_action": "hide",
        "triple_click_action": "again",
        "shortcuts": {
            "again": "1",
            "hard": "2",
            "good": "3",
            "easy": "4",
            "delete_card": "0",
            "delete_card_2": "Escape",
            "reveal_1": "Space",
            "reveal_2": "Return",
            "reveal_grade": "good",
        },
    }


_GRADE_OPTIONS = (
    ("again", "重来"),
    ("hard", "困难"),
    ("good", "良好"),
    ("easy", "简单"),
)


def merge_config(user: Optional[dict]) -> dict:
    conf = _defaults()
    if not isinstance(user, dict):
        return conf
    conf.update({k: v for k, v in user.items() if k != "shortcuts"})
    sc = deepcopy(conf["shortcuts"])
    user_sc = user.get("shortcuts") or {}
    if isinstance(user_sc, dict):
        if "reveal_1" not in user_sc and "good_extra" in user_sc:
            extras = [str(x) for x in (user_sc.get("good_extra") or [])]
            if extras:
                sc["reveal_1"] = extras[0]
            if len(extras) > 1:
                sc["reveal_2"] = extras[1]
        sc.update({k: v for k, v in user_sc.items() if k != "good_extra"})
    conf["shortcuts"] = sc
    if int(user.get("presentation_version", 0)) < 2:
        # One-time migration from the large phone-card presentation.
        conf["card_width"] = min(int(conf.get("card_width", 330)), 330)
        conf["font_size"] = min(int(conf.get("font_size", 13)), 13)
        conf["presentation_version"] = 2
    if int(user.get("capsule_style_version", 0)) < 1:
        # Restore the user's original 15px capsule typography once. Later
        # font-size changes remain user-controlled, just like width changes.
        conf["font_size"] = 15
        conf["capsule_style_version"] = 1
    if int(user.get("opaque_style_version", 0)) < 1:
        conf["opacity"] = 1.0
        conf["opaque_style_version"] = 1
    return conf


class _Group(QFrame):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Group")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 2, 0, 2)
        self._lay.setSpacing(0)
        self._rows = 0

    def add_row(self, widget: QWidget) -> None:
        if self._rows > 0:
            sep = QFrame()
            sep.setObjectName("Separator")
            self._lay.addWidget(sep)
        self._lay.addWidget(widget)
        self._rows += 1


def _row(label: str, control: QWidget, hint: str = "") -> QWidget:
    wrap = QWidget()
    wrap.setObjectName("Row")
    wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    lay = QHBoxLayout(wrap)
    lay.setContentsMargins(14, 8, 14, 8)
    lay.setSpacing(16)

    left = QVBoxLayout()
    left.setContentsMargins(0, 0, 0, 0)
    left.setSpacing(1)
    lab = QLabel(label)
    lab.setObjectName("RowLabel")
    left.addWidget(lab)
    if hint:
        h = QLabel(hint)
        h.setObjectName("RowHint")
        h.setWordWrap(False)
        left.addWidget(h)
    left.addStretch(0)

    lay.addLayout(left, 1)
    control.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    lay.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
    return wrap


def _check_row(checkbox: QCheckBox) -> QWidget:
    wrap = QWidget()
    wrap.setObjectName("Row")
    wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    lay = QHBoxLayout(wrap)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.addWidget(checkbox)
    lay.addStretch(1)
    return wrap


def _section(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("SectionLabel")
    lab.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return lab


class MoyuConfigDialog(QDialog):
    def __init__(
        self,
        config: dict,
        on_save: Callable[[dict], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MoyuConfigDialog")
        self.setWindowTitle("摸鱼复习条")
        self.setStyleSheet(_DIALOG_STYLE)
        self.setMinimumSize(480, 420)
        self.resize(520, 640)
        self.setSizeGripEnabled(True)
        self._on_save = on_save
        self._conf = merge_config(config)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        head_lay = QVBoxLayout(header)
        head_lay.setContentsMargins(24, 20, 24, 8)
        head_lay.setSpacing(4)
        title = QLabel("设置")
        title.setObjectName("PageTitle")
        sub = QLabel("外观、字体与快捷键")
        sub.setObjectName("PageSub")
        head_lay.addWidget(title)
        head_lay.addWidget(sub)
        root.addWidget(header)

        # Scrollable body — prevents bottom clipping and stretch chaos
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        inner = QWidget()
        inner.setObjectName("ScrollInner")
        body = QVBoxLayout(inner)
        body.setContentsMargins(24, 8, 24, 20)
        body.setSpacing(6)
        body.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Appearance
        body.addWidget(_section("外观"))
        appear = _Group()
        self.opacity = QDoubleSpinBox()
        self.opacity.setRange(0.35, 1.0)
        self.opacity.setSingleStep(0.05)
        self.opacity.setDecimals(2)
        self.opacity.setValue(float(self._conf.get("opacity", 1.0)))
        _style_capsule(self.opacity)
        self.max_width = QSpinBox()
        self.max_width.setRange(280, 900)
        self.max_width.setSuffix(" px")
        self.max_width.setValue(int(self._conf.get("card_width", 330)))
        _style_capsule(self.max_width)
        self.toggle_shortcut = CapsuleKeyEdit(
            str(self._conf.get("toggle_shortcut") or "Ctrl+Shift+M")
        )
        self.auto_show = QCheckBox("启动后自动显示悬浮条")
        self.auto_show.setChecked(bool(self._conf.get("auto_show", True)))
        self.mathjax = QCheckBox("渲染 LaTeX 公式（MathJax）")
        self.mathjax.setChecked(bool(self._conf.get("mathjax", True)))
        appear.add_row(_row("不透明度", self.opacity))
        appear.add_row(_row("卡片宽度", self.max_width, "默认轻巧窄条，也可拖动左右边缘"))
        appear.add_row(_row("显示 / 隐藏", self.toggle_shortcut))
        appear.add_row(_check_row(self.auto_show))
        appear.add_row(_check_row(self.mathjax))
        body.addWidget(appear)
        body.addSpacing(10)

        # Font
        body.addWidget(_section("字体"))
        typo = _Group()
        self.font_family = QFontComboBox()
        self.font_family.setMinimumWidth(180)
        self.font_family.setMaximumWidth(220)
        fam = str(self._conf.get("font_family") or "PingFang SC")
        self.font_family.setCurrentFont(QFont(fam))
        _style_capsule(self.font_family)
        self.font_size = QSpinBox()
        self.font_size.setRange(11, 28)
        self.font_size.setSuffix(" pt")
        self.font_size.setValue(int(self._conf.get("font_size", 13)))
        _style_capsule(self.font_size)
        typo.add_row(_row("字体", self.font_family))
        typo.add_row(_row("字号", self.font_size))
        body.addWidget(typo)
        body.addSpacing(10)

        # Reveal
        body.addWidget(_section("显示答案"))
        reveal = _Group()
        sc = self._conf.get("shortcuts") or {}
        self.key_reveal_1 = CapsuleKeyEdit(str(sc.get("reveal_1") or "Space"))
        self.key_reveal_2 = CapsuleKeyEdit(str(sc.get("reveal_2") or "Return"))
        self.reveal_grade = QComboBox()
        for key, label in _GRADE_OPTIONS:
            self.reveal_grade.addItem(label, key)
        rg = str(sc.get("reveal_grade") or "good")
        idx = self.reveal_grade.findData(rg)
        self.reveal_grade.setCurrentIndex(idx if idx >= 0 else 2)
        _style_capsule(self.reveal_grade)
        reveal.add_row(_row("快捷键 A", self.key_reveal_1, "未显示答案时：显示答案"))
        reveal.add_row(_row("快捷键 B", self.key_reveal_2, "未显示答案时：显示答案"))
        reveal.add_row(
            _row("显示后再按", self.reveal_grade, "答案已显示时，A/B 键执行的评分")
        )
        body.addWidget(reveal)
        body.addSpacing(10)

        body.addWidget(_section("触摸板 / 鼠标"))
        pointer = _Group()
        options = (*_GRADE_OPTIONS, ("hide", "隐藏浮条"), ("undo", "撤销上次评分"),
                   ("focus", "仅聚焦 / 显示答案"), ("none", "不执行动作"))
        for attr, key, label, default in (
            ("click_grade", "click_grade", "单击动作", "good"),
            ("double_click_action", "double_click_action", "双击动作", "hide"),
            ("triple_click_action", "triple_click_action", "三击动作", "again"),
        ):
            combo = QComboBox()
            for value, text in options:
                combo.addItem(text, value)
            idx = combo.findData(self._conf.get(key, default))
            combo.setCurrentIndex(idx if idx >= 0 else combo.findData(default))
            _style_capsule(combo)
            setattr(self, attr, combo)
            pointer.add_row(_row(label, combo, "评分需答案已显示；恢复焦点的单击不评分"))
        body.addWidget(pointer)
        hint = QLabel("⌘Z（Windows：Ctrl+Z）撤销上次评分；连击判定结束后执行动作。")
        hint.setWordWrap(True)
        hint.setObjectName("RowHint")
        body.addWidget(hint)
        body.addSpacing(10)

        # Grade
        body.addWidget(_section("评分"))
        grade = _Group()
        self.key_again = CapsuleKeyEdit(str(sc.get("again") or "1"))
        self.key_hard = CapsuleKeyEdit(str(sc.get("hard") or "2"))
        self.key_good = CapsuleKeyEdit(str(sc.get("good") or "3"))
        self.key_easy = CapsuleKeyEdit(str(sc.get("easy") or "4"))
        self.key_delete = CapsuleKeyEdit(str(sc.get("delete_card") or "0"))
        self.key_delete_2 = CapsuleKeyEdit(str(sc.get("delete_card_2") or "Escape"))
        grade.add_row(_row("重来", self.key_again))
        grade.add_row(_row("困难", self.key_hard))
        grade.add_row(_row("良好", self.key_good))
        grade.add_row(_row("简单", self.key_easy))
        grade.add_row(_row("删除卡片 A", self.key_delete, "只删当前卡片，同笔记其他卡片保留"))
        grade.add_row(_row("删除卡片 B", self.key_delete_2, "与 A 相同；默认 Esc"))
        body.addWidget(grade)
        body.addSpacing(24)
        body.addStretch(0)

        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # Fixed footer
        footer = QFrame()
        footer.setObjectName("Footer")
        footer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        foot = QHBoxLayout(footer)
        foot.setContentsMargins(24, 12, 24, 14)
        foot.setSpacing(10)
        restore = QPushButton("还原")
        restore.setObjectName("SecondaryBtn")
        cancel = QPushButton("取消")
        cancel.setObjectName("SecondaryBtn")
        save = QPushButton("完成")
        save.setObjectName("SaveBtn")
        restore.clicked.connect(self._restore_defaults)
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        foot.addWidget(restore)
        foot.addStretch(1)
        foot.addWidget(cancel)
        foot.addWidget(save)
        root.addWidget(footer)

    def _restore_defaults(self) -> None:
        d = _defaults()
        self.opacity.setValue(d["opacity"])
        self.max_width.setValue(d["card_width"])
        self.auto_show.setChecked(True)
        self.mathjax.setChecked(True)
        self.toggle_shortcut.setKeySequence(QKeySequence(d["toggle_shortcut"]))
        self.font_family.setCurrentFont(QFont(d["font_family"]))
        self.font_size.setValue(d["font_size"])
        sc = d["shortcuts"]
        self.key_reveal_1.setKeySequence(QKeySequence(sc["reveal_1"]))
        self.key_reveal_2.setKeySequence(QKeySequence(sc["reveal_2"]))
        rg = str(sc.get("reveal_grade") or "good")
        idx = self.reveal_grade.findData(rg)
        self.reveal_grade.setCurrentIndex(idx if idx >= 0 else 2)
        self.click_grade.setCurrentIndex(self.click_grade.findData("good"))
        self.double_click_action.setCurrentIndex(self.double_click_action.findData("hide"))
        self.triple_click_action.setCurrentIndex(self.triple_click_action.findData("again"))
        self.key_again.setKeySequence(QKeySequence(sc["again"]))
        self.key_hard.setKeySequence(QKeySequence(sc["hard"]))
        self.key_good.setKeySequence(QKeySequence(sc["good"]))
        self.key_easy.setKeySequence(QKeySequence(sc["easy"]))
        self.key_delete.setKeySequence(QKeySequence(sc.get("delete_card") or "0"))
        self.key_delete_2.setKeySequence(QKeySequence(sc.get("delete_card_2") or "Escape"))

    @staticmethod
    def _seq_str(edit: CapsuleKeyEdit) -> str:
        return edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText).strip()

    def _save(self) -> None:
        conf = merge_config(self._conf)
        conf["click_grade"] = self.click_grade.currentData() or "good"
        conf["double_click_action"] = self.double_click_action.currentData() or "hide"
        conf["triple_click_action"] = self.triple_click_action.currentData() or "again"
        conf["opacity"] = float(self.opacity.value())
        conf["card_width"] = int(self.max_width.value())
        conf["auto_show"] = bool(self.auto_show.isChecked())
        conf["mathjax"] = bool(self.mathjax.isChecked())
        conf["toggle_shortcut"] = self._seq_str(self.toggle_shortcut) or "Ctrl+Shift+M"
        conf["font_family"] = self.font_family.currentFont().family() or "PingFang SC"
        conf["font_size"] = int(self.font_size.value())
        conf["shortcuts"] = {
            "again": self._seq_str(self.key_again) or "1",
            "hard": self._seq_str(self.key_hard) or "2",
            "good": self._seq_str(self.key_good) or "3",
            "easy": self._seq_str(self.key_easy) or "4",
            "delete_card": self._seq_str(self.key_delete) or "0",
            "delete_card_2": self._seq_str(self.key_delete_2) or "Escape",
            "reveal_1": self._seq_str(self.key_reveal_1) or "Space",
            "reveal_2": self._seq_str(self.key_reveal_2) or "Return",
            "reveal_grade": self.reveal_grade.currentData() or "good",
        }
        conf["pos_x"] = self._conf.get("pos_x")
        conf["pos_y"] = self._conf.get("pos_y")
        self._on_save(conf)
        self.accept()
