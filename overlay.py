# -*- coding: utf-8 -*-
"""Resizable desktop card, preserving Anki template markup and typography."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable, Optional

from aqt import mw

from aqt.qt import (
    QApplication,
    QColor,
    QEvent,
    QUrl,
    QRegion,
    QRect,
    QWebEngineView,
    QWebEnginePage,
    QKeySequence,
    QLabel,
    QLineEdit,
    QPainter,
    QPlainTextEdit,
    QPoint,
    QTextEdit,
    QTimer,
    Qt,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from .config_dialog import merge_config
from .review_controller import ReviewController
from .rich_card import document
from .mac_window import configure_overlay, focus_overlay, has_keyboard_focus, window_status


def _normalize_key_name(name: str) -> str:
    n = (name or "").strip()
    aliases = {
        " ": "Space",
        "Space": "Space",
        "Return": "Return",
        "Enter": "Return",
        "\n": "Return",
        "\r": "Return",
        "Esc": "Escape",
        "Escape": "Escape",
    }
    if n in aliases:
        return aliases[n]
    normalized = QKeySequence(n).toString(QKeySequence.SequenceFormat.PortableText) or n
    return aliases.get(normalized, normalized)


def _key_from_event(event) -> str:
    k = event.key()
    if event.modifiers() & (Qt.KeyboardModifier.ControlModifier |
                            Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier):
        return QKeySequence(event.keyCombination()).toString(QKeySequence.SequenceFormat.PortableText)
    if k == Qt.Key.Key_Space:
        return "Space"
    if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
        return "Return"
    if k == Qt.Key.Key_Escape:
        return "Escape"
    if int(Qt.Key.Key_0) <= int(k) <= int(Qt.Key.Key_9):
        return str(int(k) - int(Qt.Key.Key_0))
    if int(Qt.Key.Key_A) <= int(k) <= int(Qt.Key.Key_Z):
        return chr(ord("A") + int(k) - int(Qt.Key.Key_A))
    try:
        text = QKeySequence(event.keyCombination()).toString(
            QKeySequence.SequenceFormat.PortableText
        )
    except Exception:
        text = QKeySequence(k).toString(QKeySequence.SequenceFormat.PortableText)
    return _normalize_key_name(text)


class _CardPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, kind, is_main_frame):  # noqa: N802
        # No Anki reviewer bridge and no navigation away from the card.
        if kind == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            return False
        return super().acceptNavigationRequest(url, kind, is_main_frame)


class _MoveHandle(QLabel):
    def __init__(self, owner):
        super().__init__("", owner)
        self.owner = owner
        self.setFixedHeight(6)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setToolTip("按住任意文字区域拖动；双击隐藏；两侧调整宽度")

    def paintEvent(self, event):
        pass  # Invisible drag strip; no permanent toolbar.

    def mousePressEvent(self, event):
        self.owner.mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.owner.mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.owner.mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.owner.mouseDoubleClickEvent(event)


class _WidthHandle(QWidget):
    def __init__(self, owner, side):
        super().__init__(owner)
        self.owner, self.side = owner, side
        self.origin = None
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setToolTip("左右拖动调整卡片宽度")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.owner._cancel_pending_click()
            self.origin = (event.globalPosition().x(), self.owner.x(), self.owner.width())
            self.owner._resizing = True
            event.accept()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            start, x, width = self.origin
            delta = round(event.globalPosition().x() - start)
            target = self.owner._clamp_width(width + (delta if self.side == 'right' else -delta))
            if self.side == 'left':
                self.owner.move(x + width - target, self.owner.y())
            self.owner._set_card_width(target)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self.origin is not None:
            self.origin = None
            self.owner._resizing = False
            self.owner._save_geometry()
            event.accept()


class MoyuOverlay(QWidget):
    closed = pyqtSignal()
    position_changed = pyqtSignal(int, int)

    def __init__(
        self,
        controller: ReviewController,
        config: dict,
        on_config_save: Callable[[dict], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.config = merge_config(config)
        self._on_config_save = on_config_save
        self._hovered = False
        self._pinned_reveal = False
        # After grading: stay collapsed until mouse leaves, then hover works again.
        self._await_mouse_leave = False
        self._dragging = False
        self._resizing = False
        self._drag_offset = QPoint()
        self._drag_start_position = QPoint()
        self._drag_moved = False
        self._press_card = None
        self._press_can_grade = False
        self._press_count = 0
        self._press_focus_only = False
        self._press_anchor = QPoint()
        self._refocus_click_required = False
        self._pending_click = None
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._commit_click_grade)
        self._opacity = float(self.config.get("opacity", 1.0))
        self._filter_installed = False
        self._keyboard_grabbed = False
        self._keyboard_session = False
        self._space_refresh = QTimer(self)
        self._space_refresh.setSingleShot(True)
        self._space_refresh.setInterval(150)
        self._space_refresh.timeout.connect(self._refresh_space_policy)
        self._space_settled = QTimer(self)
        self._space_settled.setSingleShot(True)
        self._space_settled.setInterval(1000)
        self._space_settled.timeout.connect(self._refresh_space_policy)
        self._last_space_status = None

        self.setObjectName("MoyuOverlay")
        self.setWindowFlags(
            (Qt.WindowType.Tool if sys.platform == "darwin" else Qt.WindowType.Window)
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._loaded = False
        self._rendered_expanded = False
        self._document = ""
        self._measure_serial = 0
        self._math_retries = 0
        self._last_expanded = None
        self._visible_height = 50
        self._card_width = self._clamp_width(int(self.config.get("card_width", 330)))
        self._measure_timer = QTimer(self)
        self._measure_timer.setSingleShot(True)
        self._measure_timer.setInterval(45)
        self._measure_timer.timeout.connect(self._measure_content)
        self._build_ui()
        self._apply_geometry_defaults()
        self.setWindowOpacity(self._opacity)

        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(40)
        self._hover_timer.timeout.connect(self._poll_hover)
        self.refresh()

    def apply_config(self, config: dict) -> None:
        self._cancel_pending_click()
        self.config = merge_config(config)
        self._opacity = float(self.config.get("opacity", 1.0))
        self.setWindowOpacity(self._opacity)
        self._set_card_width(int(self.config.get("card_width", 330)))
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 0, 4, 0)
        root.setSpacing(0)
        self.handle = _MoveHandle(self)
        root.addWidget(self.handle)
        self.web = QWebEngineView(self)
        self.web.setPage(_CardPage(self.web))
        self.web.page().setBackgroundColor(QColor(0, 0, 0, 0))
        self.web.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.web.setStyleSheet("background: transparent; border: 0;")
        root.addWidget(self.web, 1)
        self.web.loadFinished.connect(self._page_ready)
        self.web.page().contentsSizeChanged.connect(lambda _: self._queue_measure())
        self._left_handle = _WidthHandle(self, 'left')
        self._right_handle = _WidthHandle(self, 'right')
        self.setMinimumWidth(280)
        screen = self.screen()
        height = max(140, screen.availableGeometry().height() - 16) if screen else 700
        # The native canvas never changes height during reveal/collapse.
        # Transparent unused space is excluded from the input mask.
        self.setFixedHeight(height)
        self.resize(self._card_width, height)

    def _clamp_width(self, width: int) -> int:
        screen = self.screen()
        maximum = min(900, screen.availableGeometry().width() - 16) if screen else 900
        return max(280, min(width, maximum))

    def _set_card_width(self, width: int) -> None:
        self._card_width = self._clamp_width(width)
        if self.width() != self._card_width:
            self.resize(self._card_width, self.height())
        self._queue_measure()

    def _apply_geometry_defaults(self) -> None:
        screen = self.screen()
        geo = screen.availableGeometry() if screen else None
        x, y = self.config.get("pos_x"), self.config.get("pos_y")
        if x is None or y is None:
            x, y = (geo.center().x() - self._card_width//2, geo.y() + 20) if geo else (200, 40)
        if geo:
            x = max(geo.left(), min(int(x), geo.right() - self._card_width))
            y = max(geo.top(), min(int(y), geo.bottom() - 160))
        self.move(int(x), int(y))
        self._fit_surface_to_screen()

    def _fit_surface_to_screen(self) -> None:
        screen = self.screen()
        if not screen:
            return
        geo = screen.availableGeometry()
        # Recalculate only on initial placement, reopening, or explicit user
        # movement. Revealing an answer never moves or resizes the window.
        y = max(geo.top(), min(self.y(), geo.bottom() - 140))
        if y != self.y():
            self.move(self.x(), y)
        height = max(132, geo.bottom() - y - 8)
        if self.height() != height:
            self.setFixedHeight(height)
        self._queue_measure()

    def _save_geometry(self) -> None:
        self._fit_surface_to_screen()
        self.config.update(card_width=self.width(), pos_x=self.x(), pos_y=self.y())
        self._on_config_save(self.config)
        self.position_changed.emit(self.x(), self.y())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, '_left_handle'):
            self._left_handle.setGeometry(0, 0, 6, self.height())
            self._right_handle.setGeometry(self.width() - 6, 0, 6, self.height())
            self._left_handle.raise_()
            self._right_handle.raise_()
            self._queue_measure()

    def _install_app_filter(self) -> None:
        app = QApplication.instance()
        if app and not self._filter_installed:
            app.installEventFilter(self)
            self._filter_installed = True

    def _remove_app_filter(self) -> None:
        app = QApplication.instance()
        if app and self._filter_installed:
            app.removeEventFilter(self)
            self._filter_installed = False

    def _window_has_focus(self) -> bool:
        if self.isActiveWindow() and self._anki_active():
            return True
        try:
            return self.isVisible() and has_keyboard_focus(self)
        except Exception:
            return False

    def _focus_review_window(self) -> None:
        if not self._window_has_focus():
            try:
                focused = focus_overlay(self)
            except Exception:
                focused = False
            if not focused:
                self.activateWindow()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _grab_keys(self) -> None:
        if self._keyboard_grabbed:
            return
        self._keyboard_grabbed = True
        if self.isVisible():
            self._keyboard_session = True
            # Explicitly requested hover focus. Activate only once on entry;
            # never raise/rebuild the window or change its geometry/opacity.
            self._focus_review_window()

    def _release_keys(self) -> None:
        if not self._keyboard_grabbed:
            return
        self._keyboard_grabbed = False

    def show_overlay(self) -> None:
        if not self.controller.can_start():
            return
        if not self.controller.active:
            self.controller.start()
        else:
            self.controller.load_next()
        self._await_mouse_leave = False
        self._hovered = False
        self._pinned_reveal = False
        self._keyboard_session = False
        self._release_keys()
        self.refresh()
        self._fit_surface_to_screen()
        self._apply_space_policy()
        self.show()
        self.raise_()
        self._install_app_filter()
        self._hover_timer.start()

    def _apply_space_policy(self) -> None:
        try:
            configure_overlay(self)
        except Exception as error:
            # Do not silently abort opening the overlay if an OS API fails.
            # A single diagnostic per instance avoids a noisy log on re-show.
            if not getattr(self, "_space_policy_error_logged", False):
                self._space_policy_error_logged = True
                try:
                    with Path(__file__).with_name("moyu_debug.log").open("a", encoding="utf-8") as log:
                        log.write("fullscreen panel policy failed: " + str(error) + "\n")
                except OSError:
                    pass

    def _refresh_space_policy(self) -> None:
        if not self.isVisible():
            return
        self._apply_space_policy()
        try:
            status = window_status(self)
            if status and status != self._last_space_status:
                self._last_space_status = status
                with Path(__file__).with_name("moyu_debug.log").open("a", encoding="utf-8") as log:
                    log.write("fullscreen panel status: " + json.dumps(status, sort_keys=True) + "\n")
        except Exception:
            pass

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._apply_space_policy()
        # Qt may finish applying native window flags during the show cycle.
        # Reapply once after that cycle, never raise/activate on a timer.
        QTimer.singleShot(0, self._refresh_space_policy)

    def hide_overlay(self) -> None:
        self._space_refresh.stop()
        self._space_settled.stop()
        self._cancel_pending_click()
        self._keyboard_session = False
        self._cancel_drag()
        self._hover_timer.stop()
        self._release_keys()
        self._remove_app_filter()
        self._pinned_reveal = False
        self.controller.stop()
        self.hide()

    def toggle(self) -> None:
        if self.isVisible():
            self.hide_overlay()
        else:
            self.show_overlay()

    def refresh(self) -> None:
        parts = self.controller.current_html()
        if parts:
            front, back, note = parts
        else:
            front, back, note = "<p>暂无到期卡片</p>", "", ""
        markup = document(front, back, note,
            font_family=str(self.config.get("font_family") or "PingFang SC"),
            font_size=int(self.config.get("font_size", 13)),
            mathjax=bool(self.config.get("mathjax", True)))
        if markup != self._document:
            self._cancel_pending_click()
            self._document = markup
            self._loaded = False
            self._rendered_expanded = False
            self._last_expanded = None
            self._measure_serial += 1
            self._math_retries = 0
            base = QUrl(mw.serverURL()) if mw else QUrl()
            self.web.setHtml(markup, base)
        self._relayout()

    def _expanded(self) -> bool:
        if self._await_mouse_leave or self.controller.card is None:
            return False
        return self._hovered or self._pinned_reveal

    def _page_ready(self, ok: bool) -> None:
        self._loaded = ok
        if ok:
            self._last_expanded = None
            self._sync_expanded()
            self._keep_keyboard_focus()

    def _keep_keyboard_focus(self) -> None:
        # Keep focus on the persistent native widget across Chromium reloads,
        # without activating Anki if the user has switched to another app.
        if self._keyboard_session and self.isVisible() and self._window_has_focus():
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _sync_expanded(self) -> None:
        if not self._loaded:
            return
        expanded = self._expanded()
        self._measure_serial += 1
        serial = self._measure_serial
        if self._last_expanded != expanded:
            script = "window.moyuSetExpanded && window.moyuSetExpanded(%s)" % ('true' if expanded else 'false')
            self._last_expanded = expanded
        else:
            script = "window.moyuHeight && window.moyuHeight()"
        self.web.page().runJavaScript(script, lambda h: self._layout_ack(h, serial, expanded))

    def _layout_ack(self, height, serial: int, expanded: bool) -> None:
        if serial != self._measure_serial:
            return
        if height == -1:
            # MathJax is still typesetting; retry the measurement shortly.
            self._math_retries += 1
            if self._math_retries < 60:
                QTimer.singleShot(150, self._sync_expanded)
            return
        self._math_retries = 0
        self._rendered_expanded = expanded
        self._update_visible_region(height, serial)

    def _queue_measure(self) -> None:
        if hasattr(self, '_measure_timer'):
            self._measure_timer.start()

    def _measure_content(self) -> None:
        self._sync_expanded()

    def _update_visible_region(self, content_height, serial: int) -> None:
        if serial != self._measure_serial or not isinstance(content_height, (int, float)):
            return
        self._visible_height = max(32, min(int(content_height) + 6, self.height()))
        # Keep native geometry, opacity, and the front capsule unchanged.
        # Only the hit-test mask follows visible content.
        region = QRegion(QRect(0, 0, self.width(), self._visible_height))
        if region != self.mask():
            self.setMask(region)

    def _relayout(self) -> None:
        if self._expanded():
            self._grab_keys()
        elif not self._hovered and not self._pinned_reveal:
            self._release_keys()
        self._sync_expanded()

    def _reveal_keys(self) -> set[str]:
        sc = self.config.get("shortcuts") or {}
        out = set()
        for key in (sc.get("reveal_1"), sc.get("reveal_2")):
            n = _normalize_key_name(str(key or ""))
            if n:
                out.add(n)
        return out

    def _reveal_grade_ease(self) -> int:
        """Grade applied when reveal keys are pressed while answer is visible."""
        sc = self.config.get("shortcuts") or {}
        name = str(sc.get("reveal_grade") or "good").lower()
        return {"again": 1, "hard": 2, "good": 3, "easy": 4}.get(name, 3)

    def _click_action(self, count: int) -> str:
        key, default = {1: ("click_grade", "good"), 2: ("double_click_action", "hide"),
                        3: ("triple_click_action", "again")}[min(count, 3)]
        return str(self.config.get(key) or default).lower()

    def _cancel_pending_click(self) -> None:
        self._click_timer.stop()
        self._pending_click = None

    def _commit_click_grade(self) -> None:
        pending = self._pending_click
        self._cancel_pending_click()
        if pending is None:
            return
        card, markup, count, can_grade, focus_only, anchor = pending
        if (not self.isVisible() or not self.controller.active or
                self._dragging or self._resizing or self.controller.card is not card or
                self._document != markup):
            return
        # An activation click must never execute its configured action. Explicit
        # double/triple gestures remain available after returning to the overlay.
        if count == 1 and focus_only:
            return
        action = self._click_action(count)
        ease = {"again": 1, "hard": 2, "good": 3, "easy": 4}.get(action)
        if ease:
            if can_grade and self._loaded:
                self._on_grade(ease)
        elif action == "hide":
            self._quick_hide()
        elif action == "undo":
            self._undo_answer()
        elif action == "focus":
            self._focus_and_reveal()

    def _focus_and_reveal(self) -> None:
        self._keyboard_session = True
        self._focus_review_window()
        if self.controller.card is not None:
            self._await_mouse_leave = False
            self._pinned_reveal = True
            self._relayout()

    def _undo_allowed(self) -> bool:
        return bool(self.isVisible() and self.controller.active and
                    not self._typing_in_field() and
                    (self._window_has_focus() or self._cursor_over_self()))

    def _undo_answer(self) -> None:
        # If the click has not been submitted, simply cancel it; never undo
        # a previous card while the accidental click is still pending.
        if self._pending_click is not None or self._dragging:
            self._cancel_pending_click()
            self._cancel_drag()
            self._press_card = None
            self._focus_and_reveal()
            return
        if self.controller.undo_last_answer():
            self._refocus_click_required = False
            self._keyboard_session = True
            self._await_mouse_leave = False
            self._hovered = False
            self._pinned_reveal = True
            self.refresh()
            self._focus_and_reveal()

    def _grade_map(self) -> dict[str, int]:
        sc = self.config.get("shortcuts") or {}
        mapping: dict[str, int] = {}
        for name, ease in (("again", 1), ("hard", 2), ("good", 3), ("easy", 4)):
            key = _normalize_key_name(str(sc.get(name) or ""))
            if key:
                mapping[key] = ease
        return mapping

    def _delete_keys(self) -> set[str]:
        sc = self.config.get("shortcuts") or {}
        out = set()
        for key in (sc.get("delete_card"), sc.get("delete_card_2")):
            n = _normalize_key_name(str(key or ""))
            if n:
                out.add(n)
        return out

    def _cursor_over_self(self) -> bool:
        if not self.isVisible():
            return False
        # Slightly inflate hit area so leaving/entering is reliable after resize.
        local = self.mapFromGlobal(self.cursor().pos())
        return QRect(0, 0, self.width(), self._visible_height).adjusted(-2,-2,2,2).contains(local)

    def _poll_hover(self) -> None:
        if not self.isVisible() or self._dragging or self._resizing:
            return
        over = self._cursor_over_self()

        # Mouse hover must leave after grading; keyboard input is independent.
        if self._await_mouse_leave:
            if not over:
                self._await_mouse_leave = False
            else:
                return

        if over and not self._hovered:
            self._hovered = True
            self._grab_keys()
            self._relayout()
        elif not over and self._hovered:
            self._hovered = False
            if not self._pinned_reveal:
                self._release_keys()
            self._relayout()
        elif over and self._hovered and not self._keyboard_grabbed:
            self._grab_keys()

    def _typing_in_field(self) -> bool:
        w = QApplication.focusWidget()
        if w is self or (w is not None and self.isAncestorOf(w)):
            return False
        return isinstance(w, (QLineEdit, QTextEdit, QPlainTextEdit))

    def _anki_active(self) -> bool:
        app = QApplication.instance()
        if not app:
            return False
        if app.applicationState() == Qt.ApplicationState.ApplicationActive:
            return True
        # A nonactivating Cocoa panel may be key while Safari remains the
        # active application. Keep continuous keyboard review in that panel.
        try:
            return self.isVisible() and has_keyboard_focus(self)
        except Exception:
            return False

    def _hotkeys_allowed(self) -> bool:
        if not self.isVisible() or not self.controller.active or self.controller.card is None:
            return False
        if self._typing_in_field():
            return False
        return bool(self._hovered or self._pinned_reveal or self._cursor_over_self() or self._anki_active())

    def _handle_hotkey(self, key: str) -> bool:
        if not self._hotkeys_allowed():
            return False
        delete_key = key in self._delete_keys()
        ease = self._grade_map().get(key)
        reveal_key = key in self._reveal_keys()
        if not delete_key and not reveal_key and not ease:
            return False
        self._cancel_pending_click()
        self._refocus_click_required = False
        self._keyboard_session = True
        self._keep_keyboard_focus()
        # The leave/re-enter guard applies only to automatic mouse reveal.
        # A fresh keyboard press can always reveal the next card. While a new
        # page is loading, record reveal intent but never grade/delete unseen content.
        # Delete keys match grade keys: reveal first, act only when expanded.
        if not self._expanded() or not self._loaded:
            self._await_mouse_leave = False
            self._pinned_reveal = True
            self._grab_keys()
            self._relayout()
        elif delete_key:
            self._on_delete_card()
        else:
            self._on_grade(self._reveal_grade_ease() if reveal_key else ease)
        return True

    def _on_grade(self, ease: int) -> None:
        self._cancel_pending_click()
        ok = self.controller.answer(ease)
        if not self.controller.active:
            self.hide_overlay()
            self.closed.emit()
            return
        # Collapse the next card. Only automatic hover waits for mouse leave.
        self._await_mouse_leave = True
        self._hovered = False
        self._pinned_reveal = False
        self._release_keys()
        self.refresh()
        self._keep_keyboard_focus()
        if not ok and self.controller.card is None:
            self.refresh()

    def _on_delete_card(self) -> None:
        self._cancel_pending_click()
        ok = self.controller.delete_current_card()
        if not self.controller.active:
            self.hide_overlay()
            self.closed.emit()
            return
        self._await_mouse_leave = True
        self._hovered = False
        self._pinned_reveal = False
        self._release_keys()
        self.refresh()
        self._keep_keyboard_focus()
        if not ok and self.controller.card is None:
            self.refresh()

    def _begin_drag(self, global_pos: QPoint, double_click: bool = False) -> None:
        pending = self._pending_click
        continuing = bool(pending and self._click_timer.isActive() and
                          pending[0] is self.controller.card and pending[1] == self._document and
                          (global_pos - pending[5]).manhattanLength() <= QApplication.startDragDistance())
        if continuing:
            self._click_timer.stop()
            _, _, count, can_grade, focus_only, anchor = pending
            self._press_count = min(count + 1, 3)
            self._press_can_grade = can_grade
            self._press_focus_only = focus_only
            self._press_anchor = anchor
        else:
            self._cancel_pending_click()
            self._press_count = 2 if double_click else 1
            self._press_can_grade = bool(self.controller.active and self._expanded() and self._loaded and self._rendered_expanded)
            self._press_focus_only = self._refocus_click_required or not self._window_has_focus()
            self._press_anchor = QPoint(global_pos)
        self._press_card = self.controller.card
        self._drag_moved = False
        self._dragging = True
        self._drag_start_position = self.pos()
        self._drag_offset = global_pos - self.pos()
        self._keyboard_session = True
        self._focus_review_window()
        self.grabMouse()

    def _continue_drag(self, global_pos: QPoint) -> None:
        if self._dragging:
            target = global_pos - self._drag_offset
            if target != self.pos():
                self._drag_moved = True
                self._cancel_pending_click()
                self.move(target)

    def _cancel_drag(self) -> None:
        self._dragging = False
        if QWidget.mouseGrabber() is self:
            self.releaseMouse()

    def _finish_drag(self) -> None:
        if not self._dragging:
            return
        moved = self._drag_moved or self.pos() != self._drag_start_position
        self._cancel_drag()
        if moved:
            self._cancel_pending_click()
            self._save_geometry()
        elif self.controller.card is self._press_card and self.controller.active:
            self._refocus_click_required = False
            self._pending_click = (self._press_card, self._document, self._press_count,
                                   self._press_can_grade, self._press_focus_only, self._press_anchor)
            # Defer single AND double actions so a third click can supersede
            # them. A triple executes once on release; no intermediate grading.
            if self._press_count >= 3:
                self._commit_click_grade()
            else:
                self._click_timer.start(QApplication.doubleClickInterval() + 20)
            if not self._press_can_grade and self.controller.card is not None:
                self._focus_and_reveal()
        self._press_card = None
        self._press_can_grade = False
        self._queue_measure()

    def _quick_hide(self) -> None:
        self._cancel_drag()
        self._resizing = False
        self._left_handle.origin = self._right_handle.origin = None
        # No tooltip or notification: this action is meant for quick concealment.
        self.hide_overlay()

    def eventFilter(self, obj, event):  # noqa: N802
        et = event.type()
        if et in (QEvent.Type.WindowDeactivate, QEvent.Type.ApplicationDeactivate) and (obj is self or obj is QApplication.instance()):
            # Safari can remain the active app while our nonactivating panel
            # owns the keyboard. App inactivity alone is not a focus loss.
            if not self._window_has_focus():
                self._refocus_click_required = True
                self._cancel_pending_click()
        if et in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress) and self._undo_allowed() and event.matches(QKeySequence.StandardKey.Undo):
            if et == QEvent.Type.KeyPress and not event.isAutoRepeat():
                self._undo_answer()
            event.accept()
            return True
        if (self.isVisible() and et in (QEvent.Type.ApplicationActivate,
                QEvent.Type.ApplicationDeactivate, QEvent.Type.ApplicationStateChange) and
                obj is QApplication.instance()):
            # Qt/AppKit may adjust tool-window levels during activation. Restore
            # the policy once after the transition, without raising or moving.
            self._space_refresh.start()
            self._space_settled.start()
        # Chromium delivers mouse input to an internal child, not the
        # QWebEngineView itself. Filtering the application covers that child
        # and replacements created after page loads.
        own_mouse_target = (isinstance(obj, QWidget) and
                            (obj is self or self.isAncestorOf(obj)))
        if self.isVisible() and own_mouse_target:
            if et == QEvent.Type.Wheel:
                self._cancel_pending_click()
            if et == QEvent.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton:
                if obj not in (self._left_handle, self._right_handle) and not self._resizing:
                    self._begin_drag(event.globalPosition().toPoint(), double_click=True)
                    event.accept()
                    return True
            resize_target = obj in (self._left_handle, self._right_handle) or self._resizing
            if not resize_target:
                if et == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                    self._begin_drag(event.globalPosition().toPoint())
                    event.accept()
                    return True
                if et == QEvent.Type.MouseMove and self._dragging:
                    self._continue_drag(event.globalPosition().toPoint())
                    event.accept()
                    return True
                if et == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton and self._dragging:
                    self._finish_drag()
                    event.accept()
                    return True
        if et == QEvent.Type.KeyPress and self.isVisible():
            key = _key_from_event(event)
            if event.isAutoRepeat() and self._hotkeys_allowed() and (
                    key in self._reveal_keys() or key in self._grade_map() or
                    key in self._delete_keys()):
                event.accept()
                return True
            if self._handle_hotkey(key):
                event.accept()
                return True
        if et == QEvent.Type.ShortcutOverride and self._hotkeys_allowed():
            key = _key_from_event(event)
            if (key in self._reveal_keys() or key in self._grade_map() or
                    key in self._delete_keys()):
                event.accept()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._handle_hotkey(_key_from_event(event)):
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._begin_drag(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging:
            self._continue_drag(event.globalPosition().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._finish_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._begin_drag(event.globalPosition().toPoint(), double_click=True)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        # Separate capsules render their own background; there is no large card.
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.end()
