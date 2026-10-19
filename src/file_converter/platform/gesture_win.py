"""Windows low-level drag-distance/lone-modifier gesture with Qt signals."""

import math
from PySide6.QtCore import QObject, Signal


class Gesture(QObject):
    event = Signal(str)
    mouse_released = Signal()
    status_changed = Signal(str)

    def __init__(self, visible):
        super().__init__()
        self.visible = visible
        self.down = False
        self.origin = (0, 0)
        self.moved = False
        self.held = set()
        self.pending = None
        self.status_text = "Gesture not started"
        self.mouse = None
        self.keyboard = None
        self.health_timer = None

    def start(self):
        from pynput import keyboard, mouse
        self.key_names = {keyboard.Key.shift: "Shift", keyboard.Key.shift_l: "Shift", keyboard.Key.shift_r: "Shift", keyboard.Key.ctrl: "Control", keyboard.Key.ctrl_l: "Control", keyboard.Key.ctrl_r: "Control", keyboard.Key.alt: "Alt", keyboard.Key.alt_l: "Alt", keyboard.Key.alt_r: "Alt", keyboard.Key.cmd: "Command", keyboard.Key.cmd_l: "Command", keyboard.Key.cmd_r: "Command"}
        self.mouse = mouse.Listener(on_click=self.on_click, on_move=self.on_move)
        self.keyboard = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.mouse.start()
        self.keyboard.start()
        self.mouse.wait()
        self.keyboard.wait()
        self.status_text = "Drag gestures enabled"
        self.status_changed.emit(self.status_text)
        from PySide6.QtCore import QTimer
        self.health_timer = QTimer(self)
        self.health_timer.timeout.connect(self.check_health)
        self.health_timer.start(1000)
        return True

    def check_health(self):
        if not self.mouse.is_alive() or not self.keyboard.is_alive():
            self.health_timer.stop()
            self.status_text = "Gesture off - a Windows input listener stopped"
            self.status_changed.emit(self.status_text)

    def on_click(self, x, y, button, pressed):
        from pynput.mouse import Button
        if button != Button.left:
            return
        self.down = pressed
        if pressed:
            self.origin = (x, y)
            self.moved = False
        else:
            self.mouse_released.emit()

    def on_move(self, x, y):
        if self.down and math.hypot(x - self.origin[0], y - self.origin[1]) > 10:
            self.moved = True

    def on_press(self, key):
        from pynput.keyboard import Key
        if key in self.key_names:
            if key in self.held:
                return
            self.pending = key if not self.held else None
            self.held.add(key)
            return
        self.pending = None
        if key == Key.esc:
            self.event.emit("escape")
        elif str(getattr(key, "char", "")).lower() == "r":
            self.event.emit("repeat")

    def on_release(self, key):
        if key not in self.held:
            return
        self.held.remove(key)
        pending = self.pending
        self.pending = None
        if pending == key and not self.held and self.down and self.moved:
            name = self.key_names[key]
            if name != "Command":
                self.event.emit(name)

    def stop(self):
        if self.health_timer:
            self.health_timer.stop()
        if self.keyboard:
            self.keyboard.stop()
        if self.mouse:
            self.mouse.stop()
