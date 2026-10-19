"""Non-activating radial drop surface; conversion is owned by the controller."""

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ..core.wheel_layout import CENTER, INNER, OUTER, SIZE, hit_test, label_center
from .palette import palette


class Wheel(QWidget):
    files_changed = Signal(list)
    committed = Signal(str, list)
    cancelled = Signal()
    repeat_requested = Signal()

    def __init__(self):
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.resize(SIZE, SIZE)
        self.slices = ()
        self.inputs = []
        self.wheel_name = "Convert"
        self.repeat = False
        self.selected = -1
        self.theme = None
        self.hint = "Drag files here"

    def set_model(self, slices, inputs, wheel_name, repeat=False):
        self.slices = slices
        self.inputs = list(inputs)
        self.wheel_name = wheel_name
        self.repeat = repeat
        self.selected = -1
        self.update()

    def show_at_cursor(self):
        cursor = QCursor.pos()
        screen = self.screen()
        from PySide6.QtGui import QGuiApplication
        target = QGuiApplication.screenAt(cursor)
        if target is not None:
            screen = target
        area = screen.availableGeometry()
        x = min(max(cursor.x() - SIZE // 2, area.left()), max(area.left(), area.right() - SIZE + 1))
        y = min(max(cursor.y() - SIZE // 2, area.top()), max(area.top(), area.bottom() - SIZE + 1))
        self.move(x, y)
        self.show()
        self.raise_()

    def paintEvent(self, event):
        colors = palette(self.theme)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(colors.line), 1))
        painter.setBrush(QColor(colors.background))
        painter.drawEllipse(QRectF(CENTER - 205, CENTER - 205, 410, 410))
        for index, segment in enumerate(self.slices):
            self.paint_slice(painter, index, segment, colors)
        self.paint_center(painter, colors)

    def paint_slice(self, painter, index, segment, colors):
        count = len(self.slices)
        selected = index == self.selected
        fill = colors.selected if selected and segment.availability.enabled else colors.sector
        painter.setBrush(QColor(fill))
        painter.setPen(QPen(QColor(colors.line), 1))
        painter.drawPath(sector_path(index, count))
        color = colors.text if segment.availability.enabled else colors.disabled
        painter.setPen(QColor(color))
        x, y = label_center(index, count)
        self.paint_icon(painter, x, y - 19, color)
        painter.setFont(QFont("Arial", 10 if count < 11 else 8))
        painter.drawText(QRectF(x - 49, y - 1, 98, 39), Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, segment.operation.label)

    def paint_icon(self, painter, x, y, color):
        painter.setPen(QPen(QColor(color), 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(x - 7, y - 9, 14, 17), 2, 2)
        painter.drawLine(QPoint(int(x - 3), int(y - 1)), QPoint(int(x + 4), int(y - 1)))
        painter.drawLine(QPoint(int(x - 3), int(y + 3)), QPoint(int(x + 4), int(y + 3)))

    def paint_center(self, painter, colors):
        painter.setBrush(QColor(colors.background))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(CENTER - INNER, CENTER - INNER, INNER * 2, INNER * 2))
        painter.setPen(QColor(colors.text))
        painter.setFont(QFont("Arial", 15, QFont.DemiBold))
        title = "Repeat" if self.repeat else self.wheel_name
        painter.drawText(QRectF(CENTER - 75, CENTER - 41, 150, 28), Qt.AlignCenter, title)
        painter.setFont(QFont("Arial", 10))
        painter.setPen(QColor(colors.muted))
        detail = self.center_detail()
        painter.drawText(QRectF(CENTER - 69, CENTER - 8, 138, 70), Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, detail)

    def center_detail(self):
        if 0 <= self.selected < len(self.slices):
            segment = self.slices[self.selected]
            if not segment.availability.enabled:
                return "\n".join(segment.availability.reasons)
            if self.repeat and self.hint.startswith("Destination:"):
                return self.hint
            return segment.operation.subtitle or "Drop to run\nCenter cancels"
        if self.inputs:
            return f"{len(self.inputs)} selected\nCenter cancels"
        return self.hint

    def update_selection(self, position):
        self.selected = hit_test(position.x(), position.y(), len(self.slices))
        if self.selected >= 0:
            current = self.slices[self.selected]
            detail = "\n".join(current.availability.reasons) or current.operation.subtitle
            self.setToolTip(self.hint if self.repeat and self.hint.startswith("Destination:") else detail)
        self.update()

    def mouseMoveEvent(self, event):
        self.update_selection(event.position())

    def mouseReleaseEvent(self, event):
        self.update_selection(event.position())
        self.commit(self.inputs)

    def dragEnterEvent(self, event):
        paths = local_paths(event.mimeData())
        if paths:
            self.files_changed.emit(paths)
            event.setDropAction(Qt.CopyAction)
            event.accept()
            self.update_selection(event.position())

    def dragMoveEvent(self, event):
        if local_paths(event.mimeData()):
            event.setDropAction(Qt.CopyAction)
            event.accept()
            self.update_selection(event.position())

    def dragLeaveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        paths = local_paths(event.mimeData())
        self.files_changed.emit(paths)
        self.update_selection(event.position())
        event.setDropAction(Qt.CopyAction)
        event.accept()
        self.commit(paths)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
        if event.key() == Qt.Key_R:
            self.repeat_requested.emit()

    def commit(self, paths):
        if self.selected < 0 or not paths:
            self.cancelled.emit()
            return
        selected = self.slices[self.selected]
        if selected.availability.enabled:
            identifier = selected.operation.id
            self.committed.emit(identifier, list(paths))


def local_paths(mime):
    if not mime.hasUrls():
        return []
    urls = mime.urls()
    if any(not url.isLocalFile() for url in urls):
        return []
    return [url.toLocalFile() for url in urls]


def sector_path(index, count):
    path = QPainterPath()
    outer = QRectF(CENTER - OUTER, CENTER - OUTER, OUTER * 2, OUTER * 2)
    inner = QRectF(CENTER - INNER, CENTER - INNER, INNER * 2, INNER * 2)
    if count == 1:
        path.addEllipse(outer)
        hole = QPainterPath()
        hole.addEllipse(inner)
        return path.subtracted(hole)
    span = 360 / count
    start = 90 + span / 2 - index * span - 0.5
    sweep = -span + 1
    path.arcMoveTo(outer, start)
    path.arcTo(outer, start, sweep)
    path.arcTo(inner, start + sweep, -sweep)
    path.closeSubpath()
    return path
