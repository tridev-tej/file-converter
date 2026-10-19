"""macOS window placement for the wheel: live cursor position and visibility over every Space."""


def cursor_position():
    """Return the global cursor position in Qt's top-left point coordinates."""
    import Quartz
    location = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
    return int(location.x), int(location.y)


def float_over_spaces(widget):
    """Let the widget's window appear above full-screen apps and on the active Space."""
    import AppKit
    import objc
    view = objc.objc_object(c_void_p=int(widget.winId()))
    window = view.window()
    behavior = (
        AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
        | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
        | AppKit.NSWindowCollectionBehaviorStationary
    )
    window.setCollectionBehavior_(behavior)
    window.setLevel_(AppKit.NSPopUpMenuWindowLevel)
    window.setHidesOnDeactivate_(False)
