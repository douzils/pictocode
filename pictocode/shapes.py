# pictocode/shapes.py

from PyQt5.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsTextItem,
    QGraphicsPixmapItem,
    QGraphicsItem,
)
from PyQt5.QtGui import (
    QPen,
    QBrush,
    QColor,
    QPainterPath,
    QFont,
    QPixmap,
    QTransform,
)
import math
from PyQt5.QtCore import (
    Qt,
    QPointF,
    QRectF,
    QVariantAnimation,
)


class SnapToGridMixin:
    """Mixin ajoutant l'alignement à la grille lors du déplacement."""

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            view = self.scene().views()[0] if self.scene().views() else None
            if view and getattr(view, "snap_to_grid", False):
                scale = view.transform().m11() or 1
                grid = view.grid_size / scale
                value.setX(round(value.x() / grid) * grid)
                value.setY(round(value.y() / grid) * grid)
        return super().itemChange(change, value)


class SwingMoveMixin:

        # Do not call ``super().__init__`` to avoid initializing the
        # underlying ``QGraphicsItem`` twice. Each shape constructor will
        # explicitly invoke this initializer after creating the item.


    def __init__(self):
        super().__init__()
        self._dragging_swing = False
        self._base_rot = 0.0
        self._last_pos = QPointF()


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging_swing = True
            self._base_rot = self.rotation() if hasattr(self, "rotation") else 0.0

            self._last_pos = self.pos()

            if self._rot_anim:
                self._rot_anim.stop()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging_swing:
            self._dragging_swing = False

            self._animate_rotation(self._base_rot)

        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self._dragging_swing:
            value = super().itemChange(change, value)
            delta = value - self._last_pos
            self._last_pos = value
            angle = max(-10.0, min(10.0, delta.x()))
            self.setRotation(self._base_rot + angle)
            return value
        return super().itemChange(change, value)
    def _animate_rotation(self, rot):
        if self._rot_anim:
            self._rot_anim.stop()
        self._rot_anim = QVariantAnimation()
        self._rot_anim.setDuration(120)
        self._rot_anim.setStartValue(self.rotation())
        self._rot_anim.setEndValue(rot)
        self._rot_anim.valueChanged.connect(lambda v: self.setRotation(v))
        self._rot_anim.start()


class ResizableMixin:
    """Ajoute des poignées de redimensionnement et la logique associée."""

    handle_size = 12
    handle_color = Qt.black
    handle_shape = "circle"  # or "circle"

    rotation_handle_size = 12
    rotation_handle_color = Qt.red
    rotation_handle_shape = "circle"
    rotation_offset = 20

    def __init__(self):
        super().__init__()
        self._resizing = False
        self._rotating = False
        self._start_scene_pos = QPointF()
        self._start_rect = QRectF()
        self._start_item_pos = QPointF()
        self._start_center = QPointF()
        # 0: TL, 1: TR, 2: BR, 3: BL, 4: T, 5: R, 6: B, 7: L, 8: rotation
        self._active_handle = None
        self._start_angle = 0.0

    # -- Geometry ----------------------------------------------------
    def boundingRect(self):
        """Extend the base bounding rect so handles are always repainted."""
        br = super().boundingRect()
        pad = self.handle_size
        rot_pad = self.rotation_offset + self.rotation_handle_size
        return br.adjusted(-pad, -rot_pad, pad, pad)

    def shape(self):
        """Extend the shape with resize and rotation handles for hit tests."""
        path = super().shape()
        r = self.rect()
        s = self.handle_size
        extra = QPainterPath()
        handles = [
            QRectF(r.left() - s / 2, r.top() - s / 2, s, s),
            QRectF(r.right() - s / 2, r.top() - s / 2, s, s),
            QRectF(r.right() - s / 2, r.bottom() - s / 2, s, s),
            QRectF(r.left() - s / 2, r.bottom() - s / 2, s, s),
            QRectF(r.center().x() - s / 2, r.top() - s / 2, s, s),
            QRectF(r.right() - s / 2, r.center().y() - s / 2, s, s),
            QRectF(r.center().x() - s / 2, r.bottom() - s / 2, s, s),
            QRectF(r.left() - s / 2, r.center().y() - s / 2, s, s),
        ]
        for h in handles:
            if self.handle_shape == "circle":
                extra.addEllipse(h)
            else:
                extra.addRect(h)

        rot_s = self.rotation_handle_size
        rot_handle = QRectF(
            r.center().x() - rot_s / 2,
            r.top() - self.rotation_offset - rot_s / 2,
            rot_s,
            rot_s,
        )
        if self.rotation_handle_shape == "circle":
            extra.addEllipse(rot_handle)
        else:
            extra.addRect(rot_handle)

        return path.united(extra)

    def _shape_path(self):
        """Return a QPainterPath representing the pure shape (without
        handles)."""
        if hasattr(self, "path"):
            return QPainterPath(self.path())
        if hasattr(self, "line"):
            l = self.line()
            p = QPainterPath()
            p.moveTo(l.p1())
            p.lineTo(l.p2())
            return p
        if hasattr(self, "rect"):
            p = QPainterPath()
            p.addRect(self.rect())
            return p
        return QPainterPath()

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self.isSelected():
            # custom selection outline following the shape
            painter.setPen(QPen(Qt.blue, 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(self._shape_path())

            r = self.rect()
            s = self.handle_size
            painter.setBrush(QBrush(Qt.white))
            painter.setPen(QPen(self.handle_color))
            handles = [
                QRectF(r.left() - s / 2, r.top() - s / 2, s, s),
                QRectF(r.right() - s / 2, r.top() - s / 2, s, s),
                QRectF(r.right() - s / 2, r.bottom() - s / 2, s, s),
                QRectF(r.left() - s / 2, r.bottom() - s / 2, s, s),
                QRectF(r.center().x() - s / 2, r.top() - s / 2, s, s),
                QRectF(r.right() - s / 2, r.center().y() - s / 2, s, s),
                QRectF(r.center().x() - s / 2, r.bottom() - s / 2, s, s),
                QRectF(r.left() - s / 2, r.center().y() - s / 2, s, s),
            ]
            for handle in handles:
                if self.handle_shape == 'circle':
                    painter.drawEllipse(handle)
                else:
                    painter.drawRect(handle)

            rot_s = self.rotation_handle_size
            rot_handle = QRectF(
                r.center().x() - rot_s / 2,
                r.top() - self.rotation_offset - rot_s / 2,
                rot_s,
                rot_s,
            )
            painter.setPen(QPen(self.rotation_handle_color))
            painter.setBrush(QBrush(Qt.white))
            if self.rotation_handle_shape == 'circle':
                painter.drawEllipse(rot_handle)
            else:
                painter.drawRect(rot_handle)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isSelected():
            r = self.rect()
            s = self.handle_size
            handles = [
                QRectF(r.left() - s / 2, r.top() - s / 2, s, s),  # 0 TL
                QRectF(r.right() - s / 2, r.top() - s / 2, s, s),  # 1 TR
                QRectF(r.right() - s / 2, r.bottom() - s / 2, s, s),  # 2 BR
                QRectF(r.left() - s / 2, r.bottom() - s / 2, s, s),  # 3 BL
                QRectF(r.center().x() - s / 2, r.top() - s / 2, s, s),  # 4 T
                QRectF(r.right() - s / 2, r.center().y() - s / 2, s, s),  # 5 R
                QRectF(r.center().x() - s / 2,
                       r.bottom() - s / 2, s, s),  # 6 B
                QRectF(r.left() - s / 2, r.center().y() - s / 2, s, s),  # 7 L
            ]
            rot_s = self.rotation_handle_size
            rot_handle = QRectF(
                r.center().x() - rot_s / 2,
                r.top() - self.rotation_offset - rot_s / 2,
                rot_s,
                rot_s,
            )
            for idx, handle in enumerate(handles):
                if handle.contains(event.pos()):
                    self._resizing = True
                    self._active_handle = idx
                    self._start_scene_pos = event.scenePos()
                    self._start_rect = QRectF(r)
                    self._start_item_pos = QPointF(self.pos())
                    self._start_center = self.mapToScene(r.center())
                    event.accept()
                    return
            if rot_handle.contains(event.pos()):
                self._rotating = True
                self._active_handle = 8
                self._start_scene_pos = event.scenePos()
                self._start_angle = self.rotation()
                self._start_center = self.mapToScene(r.center())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            # Compute movement both in item coordinates and scene coordinates
            # to keep the handle aligned with the mouse even when the item is
            # rotated.
            start_local = self.mapFromScene(self._start_scene_pos)
            current_local = self.mapFromScene(event.scenePos())
            delta_item = current_local - start_local
            delta_scene = self.mapToScene(
                current_local) - self.mapToScene(start_local)

            x = self._start_item_pos.x()
            y = self._start_item_pos.y()
            w = self._start_rect.width()
            h = self._start_rect.height()

            if self._active_handle == 0:  # top-left
                x += delta_scene.x()
                y += delta_scene.y()
                w -= delta_item.x()
                h -= delta_item.y()
            elif self._active_handle == 1:  # top-right
                y += delta_scene.y()
                w += delta_item.x()
                h -= delta_item.y()
            elif self._active_handle == 2:  # bottom-right
                w += delta_item.x()
                h += delta_item.y()
            elif self._active_handle == 3:  # bottom-left
                x += delta_scene.x()
                w -= delta_item.x()
                h += delta_item.y()
            elif self._active_handle == 4:  # top
                y += delta_scene.y()
                h -= delta_item.y()
            elif self._active_handle == 5:  # right
                w += delta_item.x()
            elif self._active_handle == 6:  # bottom
                h += delta_item.y()
            elif self._active_handle == 7:  # left
                x += delta_scene.x()
                w -= delta_item.x()
            if event.modifiers() & Qt.ShiftModifier and w and h:
                aspect = self._start_rect.width() / self._start_rect.height()
                if abs(w) / aspect > abs(h):
                    h = abs(w) / aspect * (1 if h >= 0 else -1)
                else:
                    w = abs(h) * aspect * (1 if w >= 0 else -1)
            self.setRect(x, y, w, h)
            event.accept()
            return
        SwingMoveMixin.__init__(self)
        SwingMoveMixin.__init__(self)
            start_vec = self._start_scene_pos - center
            current_vec = event.scenePos() - center
            start_angle = math.degrees(
                math.atan2(start_vec.y(), start_vec.x()))
            curr_angle = math.degrees(math.atan2(
                current_vec.y(), current_vec.x()))
            self.setRotation(self._start_angle + curr_angle - start_angle)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing or self._rotating:
            self._resizing = False
            self._rotating = False
            self._active_handle = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


class Rect(SwingMoveMixin, ResizableMixin, SnapToGridMixin, QGraphicsRectItem):
    """Rectangle déplaçable, sélectionnable et redimensionnable."""

    def __init__(self, x, y, w, h, color: QColor = QColor("black")):
        # Initialise explicitement les différentes bases pour
        # éviter que ``ResizableMixin`` ne reçoive des arguments
        # inattendus via ``super()``.
        SwingMoveMixin.__init__(self)
        ResizableMixin.__init__(self)
        QGraphicsRectItem.__init__(self, 0, 0, w, h)
        self.setPos(x, y)
        pen = QPen(color)
        pen.setWidth(2)
        self.setPen(pen)
        self.setBrush(QBrush(Qt.white))
        self.setFlags(
            QGraphicsRectItem.ItemIsMovable
            | QGraphicsRectItem.ItemIsSelectable
            | QGraphicsRectItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.var_name = ""
        self.setToolTip("Clique droit pour modifier")

    def rect(self):
        return QGraphicsRectItem.rect(self)

    def setRect(self, x, y, w, h):
        r = QRectF(x, y, w, h).normalized()
        QGraphicsRectItem.setRect(self, 0, 0, r.width(), r.height())
        self.setPos(r.x(), r.y())
        self.setTransformOriginPoint(r.width() / 2, r.height() / 2)


class Ellipse(SwingMoveMixin, ResizableMixin, SnapToGridMixin, QGraphicsEllipseItem):
    """Ellipse déplaçable, sélectionnable et redimensionnable."""

    def __init__(self, x, y, w, h, color: QColor = QColor("black")):
        SwingMoveMixin.__init__(self)
        ResizableMixin.__init__(self)
        QGraphicsEllipseItem.__init__(self, 0, 0, w, h)
        self.setPos(x, y)
        pen = QPen(color)
        pen.setWidth(2)
        self.setPen(pen)
        self.setBrush(QBrush(Qt.white))
        self.setFlags(
            QGraphicsEllipseItem.ItemIsMovable
            | QGraphicsEllipseItem.ItemIsSelectable
            | QGraphicsEllipseItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.var_name = ""
        self.setToolTip("Clique droit pour modifier")

    def rect(self):
        return QGraphicsEllipseItem.rect(self)

    def setRect(self, x, y, w, h):
        r = QRectF(x, y, w, h).normalized()
        QGraphicsEllipseItem.setRect(self, 0, 0, r.width(), r.height())
        self.setPos(r.x(), r.y())
        self.setTransformOriginPoint(r.width() / 2, r.height() / 2)


class LineResizableMixin:
    """Ajoute des poignées de redimensionnement pour les lignes."""

    handle_size = 12

    def __init__(self):
        super().__init__()
        self._resizing = False
        self._active = None
        self._start_scene_pos = QPointF()
        self._start_line = None

    def paint(self, painter, option, widget=None):
        # Draw the line without the default Qt selection rectangle.
        painter.setPen(self.pen())
        painter.drawLine(self.line())
        if self.isSelected():
            line = self.line()
            s = self.handle_size
            painter.setBrush(QBrush(Qt.white))
            painter.setPen(QPen(Qt.black))
            handles = [
                QRectF(line.p1().x() - s / 2, line.p1().y() - s / 2, s, s),
                QRectF(line.p2().x() - s / 2, line.p2().y() - s / 2, s, s),
            ]
            for h in handles:
                painter.drawRect(h)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isSelected():
            line = self.line()
            s = self.handle_size
            handles = [
                QRectF(line.p1().x() - s / 2, line.p1().y() - s / 2, s, s),
                QRectF(line.p2().x() - s / 2, line.p2().y() - s / 2, s, s),
            ]
            for idx, h in enumerate(handles):
                if h.contains(event.pos()):
                    self._resizing = True
                    self._active = idx
                    self._start_scene_pos = event.scenePos()
                    self._start_line = self.line()
        SwingMoveMixin.__init__(self)
        SwingMoveMixin.__init__(self)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            delta = event.scenePos() - self._start_scene_pos
            line = self._start_line
            if self._active == 0:
                p1 = line.p1() + delta
                self.setLine(p1.x(), p1.y(), line.p2().x(), line.p2().y())
            else:
                p2 = line.p2() + delta
                self.setLine(line.p1().x(), line.p1().y(), p2.x(), p2.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            self._active = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


class Line(SwingMoveMixin, LineResizableMixin, SnapToGridMixin, QGraphicsLineItem):
    """Ligne déplaçable, sélectionnable et redimensionnable."""

    def __init__(self, x1, y1, x2, y2, color: QColor = QColor("black")):
        SwingMoveMixin.__init__(self)
        LineResizableMixin.__init__(self)
        QGraphicsLineItem.__init__(self, x1, y1, x2, y2)
        pen = QPen(color)
        pen.setWidth(2)
        self.setPen(pen)
        self.setFlags(
            QGraphicsLineItem.ItemIsMovable
            | QGraphicsLineItem.ItemIsSelectable
            | QGraphicsLineItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.var_name = ""
        self.setToolTip("Clique droit pour modifier")


class FreehandPath(SwingMoveMixin, ResizableMixin, SnapToGridMixin, QGraphicsPathItem):
    """
    Tracé libre.
    Utilisez `from_points` pour construire à partir d’une liste de QPointF.
    """

    def __init__(
        self,
        path=None,
        pen_color: QColor = QColor("black"),
        pen_width: int = 2,
    ):
        SwingMoveMixin.__init__(self)
        ResizableMixin.__init__(self)
        QGraphicsPathItem.__init__(self)
        pen = QPen(pen_color)
        pen.setWidth(pen_width)
        self.setPen(pen)
        if path is not None:
            self.setPath(path)
        self.setFlags(
            QGraphicsPathItem.ItemIsMovable
            | QGraphicsPathItem.ItemIsSelectable
            | QGraphicsPathItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.var_name = ""
        self.setToolTip("Clique droit pour modifier")

    def rect(self):
        return self.path().boundingRect()

    def setRect(self, x, y, w, h):
        br = self.path().boundingRect()
        if br.width() == 0 or br.height() == 0:
            return
        sx = w / br.width()
        sy = h / br.height()
        transform = QTransform()
        transform.scale(sx, sy)
        SwingMoveMixin.__init__(self)
        SwingMoveMixin.__init__(self)
        self.setPos(x, y)
        self.setTransformOriginPoint(w / 2, h / 2)

    @classmethod
    def from_points(
        cls,
        points: list[QPointF],
        pen_color: QColor = QColor("black"),
        pen_width: int = 2,
    ):
        painter_path = QPainterPath()
        if points:
            painter_path.moveTo(points[0])
            for pt in points[1:]:
                painter_path.lineTo(pt)
        return cls(painter_path, pen_color, pen_width)


class TextItem(SwingMoveMixin, ResizableMixin, SnapToGridMixin, QGraphicsTextItem):
    """Bloc de texte éditable, déplaçable et redimensionnable."""

    def __init__(
        self,
        x: float,
        y: float,
        text: str = "",
        font_size: int = 12,
        color: QColor = QColor("black"),
    ):
        SwingMoveMixin.__init__(self)
        ResizableMixin.__init__(self)
        QGraphicsTextItem.__init__(self, text)
        font = QFont()
        font.setPointSize(font_size)
        self.setFont(font)
        self.setDefaultTextColor(color)
        self.setPos(x, y)
        # Permet l’édition au double-clic
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFlags(
            QGraphicsTextItem.ItemIsMovable
            | QGraphicsTextItem.ItemIsSelectable
            | QGraphicsTextItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.var_name = ""
        self.alignment = "left"
        self.setToolTip("Clique droit pour modifier")

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            view = self.scene().views()[0] if self.scene().views() else None
            if view and getattr(view, "snap_to_grid", False):
                scale = view.transform().m11() or 1
                grid = view.grid_size / scale
                value.setX(round(value.x() / grid) * grid)
                value.setY(round(value.y() / grid) * grid)
        return super().itemChange(change, value)

    def rect(self):
        return self.boundingRect()

    def setRect(self, x, y, w, h):
        self.setPos(x, y)
        self.setTextWidth(w)
        br = self.boundingRect()
        if br.height() != 0:
            self.setScale(h / br.height())
        self.setTransformOriginPoint(w / 2, h / 2)


class ImageItem(SwingMoveMixin, ResizableMixin, SnapToGridMixin, QGraphicsPixmapItem):
    """Image insérée dans le canvas."""

    def __init__(self, x: float, y: float, path: str):
        self.path = path
        pix = QPixmap(path)
        SwingMoveMixin.__init__(self)
        ResizableMixin.__init__(self)
        QGraphicsPixmapItem.__init__(self, pix)
        self._orig_pixmap = pix
        self.setPos(x, y)
        self.setFlags(
            QGraphicsPixmapItem.ItemIsMovable
            | QGraphicsPixmapItem.ItemIsSelectable
            | QGraphicsPixmapItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.var_name = ""

    def rect(self):
        return QRectF(0, 0, self.pixmap().width(), self.pixmap().height())

    def setRect(self, x, y, w, h):
        self.setPos(x, y)
        if w > 0 and h > 0:
            scaled = self._orig_pixmap.scaled(
                w,
                h,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.setPixmap(scaled)
        self.setTransformOriginPoint(w / 2, h / 2)
