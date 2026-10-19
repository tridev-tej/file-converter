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


def finder_is_frontmost():
    """Return True when Finder (including the Desktop) is the active app."""
    from AppKit import NSWorkspace
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app is not None and app.bundleIdentifier() == "com.apple.finder"


def finder_selection():
    """Return POSIX paths of the files selected in Finder, asking Finder over Apple Events."""
    import subprocess
    script = (
        'set out to ""\n'
        'tell application "Finder" to set picked to selection as alias list\n'
        'repeat with f in picked\n'
        ' set out to out & POSIX path of f & linefeed\n'
        'end repeat\n'
        'return out'
    )
    result = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Finder did not return its selection")
    return [line.rstrip("/") or "/" for line in result.stdout.splitlines() if line]
