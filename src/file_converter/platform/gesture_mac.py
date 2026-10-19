"""Main-run-loop listen-only Quartz drag gesture, without pynput."""

from PySide6.QtCore import QObject, Signal


class Gesture(QObject):
    event = Signal(str)
    mouse_released = Signal()
    status_changed = Signal(str)

    def __init__(self, visible):
        super().__init__()
        self.visible = visible
        self.tap = None
        self.source = None
        self.callback_reference = self.callback
        self.down = False
        self.change_count = 0
        self.held = set()
        self.pending = None
        self.status_text = "Gesture not started"

    def permissions(self):
        import Quartz
        import ApplicationServices
        return bool(Quartz.CGPreflightListenEventAccess()), bool(ApplicationServices.AXIsProcessTrusted())

    def request_permission(self):
        import Quartz
        Quartz.CGRequestListenEventAccess()

    def start(self):
        import Quartz as q
        from AppKit import NSPasteboard, NSPasteboardNameDrag
        self.pasteboard = NSPasteboard.pasteboardWithName_(NSPasteboardNameDrag)
        types = (q.kCGEventLeftMouseDown, q.kCGEventLeftMouseUp, q.kCGEventFlagsChanged, q.kCGEventKeyDown)
        mask = sum(q.CGEventMaskBit(event) for event in types)
        self.tap = q.CGEventTapCreate(q.kCGSessionEventTap, q.kCGHeadInsertEventTap, q.kCGEventTapOptionListenOnly, mask, self.callback_reference, None)
        if self.tap is None:
            monitoring, trusted = self.permissions()
            reason = "Gesture off - grant Input Monitoring" if not monitoring else "Gesture off - Quartz event tap creation failed"
            self.set_status(reason)
            return False
        self.source = q.CFMachPortCreateRunLoopSource(None, self.tap, 0)
        q.CFRunLoopAddSource(q.CFRunLoopGetMain(), self.source, q.kCFRunLoopCommonModes)
        q.CGEventTapEnable(self.tap, True)
        if not q.CGEventTapIsEnabled(self.tap):
            self.set_status("Gesture off - Quartz event tap could not be enabled")
            return False
        self.set_status("Drag gestures enabled")
        return True

    def set_status(self, text):
        self.status_text = text
        self.status_changed.emit(text)

    def callback(self, proxy, event_type, event, reference):
        import Quartz as q
        if event_type in (q.kCGEventTapDisabledByTimeout, q.kCGEventTapDisabledByUserInput):
            q.CGEventTapEnable(self.tap, True)
            if not q.CGEventTapIsEnabled(self.tap):
                self.set_status("Gesture off - event tap disabled and could not be re-enabled")
            return event
        handlers = {q.kCGEventLeftMouseDown: self.mouse_down, q.kCGEventLeftMouseUp: self.mouse_up, q.kCGEventFlagsChanged: self.flags_changed, q.kCGEventKeyDown: self.key_down}
        handler = handlers.get(event_type)
        if handler:
            handler(event)
        return event

    def mouse_down(self, event):
        self.down = True
        self.change_count = self.pasteboard.changeCount()
        self.pending = None

    def mouse_up(self, event):
        self.down = False
        self.mouse_released.emit()

    def flags_changed(self, event):
        import Quartz as q
        code = q.CGEventGetIntegerValueField(event, q.kCGKeyboardEventKeycode)
        keys = {56: "Shift", 60: "Shift", 59: "Control", 62: "Control", 58: "Alt", 61: "Alt", 55: "Command", 54: "Command"}
        if code not in keys:
            self.pending = None
            return
        if code in self.held:
            self.held.remove(code)
            key = self.pending
            self.pending = None
            if key == code and not self.held and self.dragging() and keys[code] != "Command":
                self.event.emit(keys[code])
        else:
            self.pending = code if not self.held else None
            self.held.add(code)

    def dragging(self):
        return self.down and self.pasteboard.changeCount() != self.change_count

    def key_down(self, event):
        import Quartz as q
        self.pending = None
        if not self.visible() or q.CGEventGetIntegerValueField(event, q.kCGKeyboardEventAutorepeat):
            return
        key = q.CGEventGetIntegerValueField(event, q.kCGKeyboardEventKeycode)
        if key in {15, 53}:
            self.event.emit("repeat" if key == 15 else "escape")

    def stop(self):
        import Quartz as q
        if self.tap:
            q.CGEventTapEnable(self.tap, False)
        if self.source:
            q.CFRunLoopRemoveSource(q.CFRunLoopGetMain(), self.source, q.kCFRunLoopCommonModes)
