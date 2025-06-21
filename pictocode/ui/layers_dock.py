"""UI widgets for browsing and editing the layer hierarchy."""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QAction,
    QAbstractItemView,
    QGraphicsItem,
    QGraphicsItemGroup,
    QHeaderView,
    QFrame,
    QStyle,
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QTimer
from PyQt5.QtWidgets import QGraphicsObject, QDrag
from PyQt5.QtGui import QBrush, QColor, QTransform
from .animated_menu import AnimatedMenu


VISIBLE_ICON = "\U0001F441"  # eye
HIDDEN_ICON = "\u274C"      # cross mark
LOCK_ICON = "\U0001F512"    # closed lock
UNLOCK_ICON = "\U0001F513"  # open lock


class LayersTreeWidget(QTreeWidget):
    """Tree widget used for the layer hierarchy."""

    def __init__(
        self,
        parent=None,
        *,
        drop_color: QColor | None = None,
        group_color: QColor | None = None,
        **kwargs,
    ):

        """Initialize the tree and set up drop highlighting colors."""

        super().__init__(parent, **kwargs)
        self._parent = parent
        pal = self.palette()
        self.drop_color = drop_color or pal.highlight().color()
        self.group_color = group_color or pal.highlight().color()
        self._drop_line = QFrame(self.viewport())
        self._drop_line.setFixedHeight(2)
        self._drop_line.setStyleSheet(f"background:{self.drop_color.name()};")
        self._drop_line.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._drop_line.hide()
        # Use a custom drop indicator to avoid flicker with Qt's built-in one
        self.setDropIndicatorShown(False)
        self._highlight_item = None

    def mousePressEvent(self, event):

        if event.button() == Qt.LeftButton:
            col = self.columnAt(event.pos().x())
            item = self.itemAt(event.pos())
            super().mousePressEvent(event)
            if item is not None and col == 0:
                # Rely on Qt's default behaviour to start dragging only
                # when the user actually moves the mouse.  This avoids
                # accidental drops triggered by a simple click which could
                # reorder layers unexpectedly or create unwanted groups.
                return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_Up:
                if self._parent:
                    self._parent.move_current_item_up()
                event.accept()
                return
            elif event.key() == Qt.Key_Down:
                if self._parent:
                    self._parent.move_current_item_down()
                event.accept()
                return
        super().keyPressEvent(event)

    def _clear_highlight(self):
        if self._highlight_item:
            # The QTreeWidgetItem may have been removed from the tree during
            # a drop operation. When this happens Qt deletes the underlying C++
            # object and calling methods on it raises a RuntimeError. Guard by
            # checking that the item still belongs to a tree before clearing
            # its background colors. The call to ``treeWidget`` itself can
            # raise ``RuntimeError`` if the wrapped C++ object has been
            # deleted, so we also protect against that case.
            try:
                if self._highlight_item.treeWidget() is not None:
                    for c in range(self.columnCount()):
                        self._highlight_item.setBackground(c, QBrush())
            except RuntimeError:
                # The underlying item was deleted; nothing to clear.
                pass
        self._highlight_item = None

    def startDrag(self, supported_actions):
        """Start a drag with a slightly rotated pixmap for a swinging effect."""
        item = self.currentItem()
        if not item:
            super().startDrag(supported_actions)
            return

        rect = self.visualItemRect(item)
        pixmap = self.viewport().grab(rect)
        transform = QTransform()
        transform.rotate(8)
        pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
        drag = QDrag(self)
        drag.setMimeData(self.mimeData(self.selectedItems()))
        drag.setPixmap(pixmap)
        drag.setHotSpot(pixmap.rect().center())
        drag.exec_(Qt.MoveAction)

    def dragEnterEvent(self, event):
        """Ensure drags initiated outside the tree are accepted."""
        event.setDropAction(Qt.MoveAction)
        super().dragEnterEvent(event)
        event.accept()

    def dragMoveEvent(self, event):
        """Highlight potential drop targets while dragging."""
        event.setDropAction(Qt.MoveAction)
        super().dragMoveEvent(event)
        event.accept()
        item = self.itemAt(event.pos())
        pos = self.dropIndicatorPosition()

        if (
            pos in (QAbstractItemView.AboveItem, QAbstractItemView.BelowItem)
            and item
        ):
            rect = self.visualItemRect(item)
            y = (
                rect.top()
                if pos == QAbstractItemView.AboveItem
                else rect.bottom()
            )
            self._drop_line.setGeometry(0, y, self.viewport().width(), 2)
            self._drop_line.show()
        else:
            self._drop_line.hide()

        if pos == QAbstractItemView.OnItem and item:
            if self._highlight_item is not item:
                self._clear_highlight()
                self._highlight_item = item
                brush = QBrush(self.group_color)
                for c in range(self.columnCount()):
                    item.setBackground(c, brush)
        elif item is not self._highlight_item:
            self._clear_highlight()

    def dropEvent(self, event):
        """Handle a drop and notify the parent widget."""
        # Force move semantics so the underlying QTreeWidget reorders items
        # instead of duplicating them on some platforms.  The actual update of
        # the QGraphicsScene hierarchy happens in ``_handle_tree_drop``.
        event.setDropAction(Qt.MoveAction)
        self._handle_tree_drop(event)

    def _handle_tree_drop(self, event):
        self._drop_line.hide()
        self._clear_highlight()
        super().dropEvent(event)
        if self._parent and hasattr(self._parent, "_handle_tree_drop"):
            self._parent._handle_tree_drop(event)

    def dragLeaveEvent(self, event):
        """Remove any drop indicators when the drag leaves the widget."""
        self._drop_line.hide()
        self._clear_highlight()
        super().dragLeaveEvent(event)


class LayersWidget(QWidget):
    """Affiche la liste des objets du canvas avec options de calque."""

    def __init__(self, parent=None):
        """Create the widget and configure the tree view."""
        super().__init__(parent)
        self.canvas = None
        self.tree = LayersTreeWidget(self)
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Nom", "Vis", "Lock"])
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
        )
        self.tree.setAlternatingRowColors(True)
        header = self.tree.header()
        # Ensure the layer name column stretches to fill the available space
        # rather than the last column.
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        fm = self.tree.fontMetrics()
        icon_w = max(
            fm.boundingRect(VISIBLE_ICON).width(),
            fm.boundingRect(HIDDEN_ICON).width(),
            fm.boundingRect(LOCK_ICON).width(),
            fm.boundingRect(UNLOCK_ICON).width(),
        ) + 4
        header.resizeSection(1, icon_w)
        header.resizeSection(2, icon_w)
        header.hide()
        layout = QVBoxLayout(self)
        layout.addWidget(self.tree)

        self._apply_styles()

        self._updating = False

        # Keep track of ongoing z-value animations to avoid repeatedly
        # re-triggering them when scene updates occur while an
        # animation is already running.
        self._z_anims = {}

        # Connect signals once during initialization. "apply_theme" will only
        # re-apply styles without re-connecting to avoid duplicate callbacks.
        self.tree.itemPressed.connect(self._on_item_pressed)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._open_menu)
        self.tree.viewport().setAcceptDrops(True)

        # Map QGraphicsItems to their corresponding tree items for quick lookups
        self._item_map: dict[QGraphicsItem, QTreeWidgetItem] = {}

    def apply_theme(self):
        """Re-apply styles when the application theme changes."""
        self._apply_styles()

    def _on_item_pressed(self, titem, column):
        """Ensure the pressed item becomes current before dragging."""
        self.tree.setCurrentItem(titem)

    def _apply_styles(self):
        """Apply a darker style reminiscent of Blender's Outliner."""
        pal = self.tree.palette()
        base = "#2b2b2b"
        alt = "#353535"
        text = "#f0f0f0"
        highlight = pal.highlight().color().name()
        highlight_text = pal.highlightedText().color().name()
        header_bg = "#2b2b2b"
        border = pal.mid().color().name()

        self.tree.setStyleSheet(
            f"""
            QTreeWidget {{
                background: {base};
                alternate-background-color: {alt};
                color: {text};
                border: 1px solid {border};
            }}
            QTreeWidget::item {{
                padding: 4px 1px 4px 4px;
            }}
            QTreeWidget::item:selected {{
                background: {highlight};
                color: {highlight_text};
            }}
            QHeaderView::section {{
                background: {header_bg};
                padding: 2px;
                border: none;
            }}
            """
        )

    # ------------------------------------------------------------------
    def update_layers(self, canvas):
        """Rebuild the tree view to reflect the current scene layers."""
        self.canvas = canvas
        # Preserve current selection to restore it after rebuilding the tree
        selected = None
        if canvas:
            items = canvas.scene.selectedItems()
            selected = items[0] if items else None

        self._updating = True
        # Reset the item map when rebuilding the tree
        self._item_map.clear()

        expanded = {}

        def record_state(tparent):
            for i in range(tparent.childCount()):
                child = tparent.child(i)
                g = child.data(0, Qt.UserRole)
                if g:
                    expanded[g] = child.isExpanded()
                record_state(child)

        record_state(self.tree.invisibleRootItem())
        self.tree.clear()
        if not canvas:
            self._updating = False
            return

        project_name = getattr(canvas, "current_meta",
                               {}).get("name") or "Projet"
        root_item = QTreeWidgetItem(self.tree)
        root_item.setText(0, project_name)
        root_item.setData(0, Qt.UserRole, None)
        root_item.setExpanded(expanded.get(None, True))
        root_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsDropEnabled)
        root_item.setFirstColumnSpanned(True)

        def _sort_z(item):
            return self._z_anims.get(item, item.zValue())

        def add_item(gitem, parent=root_item):
            if gitem is getattr(canvas, "_frame_item", None):
                return
            qitem = QTreeWidgetItem(parent)
            name = getattr(gitem, "layer_name", type(gitem).__name__)
            qitem.setText(0, name)
            qitem.setData(0, Qt.UserRole, gitem)
            # Keep a reference for quick lookups later
            self._item_map[gitem] = qitem
            flags = (
                qitem.flags()
                | Qt.ItemIsEditable
                | Qt.ItemIsDragEnabled
                | Qt.ItemIsDropEnabled
            )
            qitem.setFlags(flags)
            qitem.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
            qitem.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
            qitem.setText(1, VISIBLE_ICON if gitem.isVisible() else HIDDEN_ICON)

            locked = not (gitem.flags() & QGraphicsItem.ItemIsMovable)
            qitem.setText(2, LOCK_ICON if locked else UNLOCK_ICON)
            if isinstance(gitem, QGraphicsItemGroup):
                icon = self.style().standardIcon(QStyle.SP_DirIcon)
            else:
                icon = self.style().standardIcon(QStyle.SP_FileIcon)
            qitem.setIcon(0, icon)
            if isinstance(gitem, QGraphicsItemGroup):
                qitem.setExpanded(expanded.get(gitem, True))
                for child in sorted(gitem.childItems(), key=_sort_z):
                    add_item(child, qitem)

        # ajoute seulement les top-level (pas déjà dans un groupe)
        for it in sorted(canvas.scene.items(), key=_sort_z):
            if it is getattr(canvas, "_frame_item", None):
                continue
            if it.parentItem() is None:
                add_item(it)

        self._sync_scene_from_tree()
        if selected:
            self.highlight_item(selected)
        self._updating = False

    # ------------------------------------------------------------------
    def highlight_item(self, item):
        """Select ``item`` in the tree if it is present."""
        qitem = self._item_map.get(item)
        if qitem:
            self.tree.setCurrentItem(qitem)
            return
        # Fallback: traverse the tree if mapping is missing
        def walk(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.data(0, Qt.UserRole) is item:
                    self.tree.setCurrentItem(child)
                    return True
                if walk(child):
                    return True
            return False

        walk(self.tree.invisibleRootItem())

    def _propagate_state(self, tparent, *, visible=None, locked=None):
        """Apply visibility or lock state to ``tparent`` and all its children."""
        queue = [tparent]
        while queue:
            current = queue.pop(0)
            gchild = current.data(0, Qt.UserRole)
            if gchild and current is not tparent:
                if visible is not None:
                    gchild.setVisible(visible)
                    current.setText(1, VISIBLE_ICON if visible else HIDDEN_ICON)
                if locked is not None:
                    gchild.setFlag(QGraphicsItem.ItemIsMovable, not locked)
                    gchild.setFlag(QGraphicsItem.ItemIsSelectable, not locked)
                    current.setText(2, LOCK_ICON if locked else UNLOCK_ICON)
            for i in range(current.childCount()):
                queue.append(current.child(i))

    # ------------------------------------------------------------------
    def _on_item_clicked(self, titem, column):
        self.tree.setCurrentItem(titem)
        if self._updating:
            return
        gitem = titem.data(0, Qt.UserRole)
        if not gitem:
            return
        if column == 1:
            vis = not gitem.isVisible()
            gitem.setVisible(vis)
            titem.setText(1, VISIBLE_ICON if vis else HIDDEN_ICON)
            if isinstance(gitem, QGraphicsItemGroup):
                self._propagate_state(titem, visible=vis)
        elif column == 2:
            locked = not bool(gitem.flags() & QGraphicsItem.ItemIsMovable)
            locked = not locked
            gitem.setFlag(QGraphicsItem.ItemIsMovable, not locked)
            gitem.setFlag(QGraphicsItem.ItemIsSelectable, not locked)
            titem.setText(2, LOCK_ICON if locked else UNLOCK_ICON)
            if isinstance(gitem, QGraphicsItemGroup):
                self._propagate_state(titem, locked=locked)

    def _on_item_changed(self, titem, column):
        if self._updating:
            return
        gitem = titem.data(0, Qt.UserRole)
        if not gitem:
            return
        if column == 0:
            gitem.layer_name = titem.text(0)

    def _on_selection_changed(self):
        if not self.canvas:
            return
        items = self.tree.selectedItems()
        if items:
            gitem = items[0].data(0, Qt.UserRole)
            if gitem:
                self.canvas.scene.clearSelection()
                gitem.setSelected(True)

    # --- Layer reordering utilities ---------------------------------
    def move_current_item_up(self):
        item = self.tree.currentItem()
        if not item:
            return
        parent = item.parent() or self.tree.invisibleRootItem().child(0)
        idx = parent.indexOfChild(item)
        if idx > 0:
            parent.takeChild(idx)
            parent.insertChild(idx - 1, item)
            self._sync_scene_from_tree()

    def move_current_item_down(self):
        item = self.tree.currentItem()
        if not item:
            return
        parent = item.parent() or self.tree.invisibleRootItem().child(0)
        idx = parent.indexOfChild(item)
        if idx < parent.childCount() - 1:
            parent.takeChild(idx)
            parent.insertChild(idx + 1, item)
            self._sync_scene_from_tree()

    def _open_menu(self, pos):
        if not self.canvas:
            return

        item = self.tree.itemAt(pos)
        root = self.tree.invisibleRootItem().child(0)

        def insert_group(index: int):
            group = self.canvas.create_collection()
            self.update_layers(self.canvas)
            root_item = self.tree.invisibleRootItem().child(0)
            self.highlight_item(group)
            qitem = self.tree.currentItem()
            if root_item and qitem:
                root_item.takeChild(root_item.indexOfChild(qitem))
                root_item.insertChild(index, qitem)
                self._sync_scene_from_tree()

        if item is None:
            menu = AnimatedMenu(self)
            act_new_group = QAction("Nouvelle collection", menu)
            menu.addAction(act_new_group)
            if menu.exec_(self.tree.mapToGlobal(pos)) == act_new_group:
                idx = self.tree.indexAt(pos).row()
                if idx < 0:
                    root_item = self.tree.invisibleRootItem().child(0)
                    idx = root_item.childCount() if root_item else 0
                insert_group(idx)
            return

        gitem = item.data(0, Qt.UserRole)
        if gitem is None:
            menu = AnimatedMenu(self)
            act_new_group = QAction("Nouvelle collection", menu)
            menu.addAction(act_new_group)
            if menu.exec_(self.tree.mapToGlobal(pos)) == act_new_group:
                root_item = self.tree.invisibleRootItem().child(0)
                count = root_item.childCount() if root_item else 0
                insert_group(count)
            return
        menu = AnimatedMenu(self)
        act_delete = QAction("Supprimer", menu)
        menu.addAction(act_delete)
        act_dup = QAction("Dupliquer", menu)
        menu.addAction(act_dup)
        act_rename = QAction("Renommer", menu)
        menu.addAction(act_rename)
        menu.addSeparator()
        act_new_group = QAction("Nouvelle collection", menu)
        menu.addAction(act_new_group)
        menu.addSeparator()
        act_up = QAction("Monter", menu)
        menu.addAction(act_up)
        act_down = QAction("Descendre", menu)
        menu.addAction(act_down)
        act_group = QAction("Grouper la sélection", menu)
        menu.addAction(act_group)
        if isinstance(gitem, QGraphicsItemGroup):
            act_ungroup = QAction("Dégrouper", menu)
            menu.addAction(act_ungroup)
        else:
            act_ungroup = None
        action = menu.exec_(self.tree.mapToGlobal(pos))
        if action is act_delete:
            self.canvas.scene.removeItem(gitem)
            self.update_layers(self.canvas)
        elif action is act_dup:
            self.canvas.scene.clearSelection()
            gitem.setSelected(True)
            self.canvas.duplicate_selected()
            new_item = self.canvas.scene.selectedItems()[0]
            self.update_layers(self.canvas)
            self.highlight_item(new_item)
        elif action is act_rename:
            self.tree.editItem(item, 0)
        elif action is act_new_group:
            root_item = self.tree.invisibleRootItem().child(0)
            count = root_item.childCount() if root_item else 0
            insert_group(count)
        elif action is act_up:
            self.move_current_item_up()
        elif action is act_down:
            self.move_current_item_down()
        elif action is act_group:
            group = self.canvas.group_selected()
            if group:
                self.update_layers(self.canvas)
                self.highlight_item(group)
        elif action is act_ungroup:
            self.canvas.ungroup_item(gitem)
            self.update_layers(self.canvas)

    # ------------------------------------------------------------------
    def _handle_tree_drop(self, event):
        target_item = self.tree.itemAt(event.pos())
        drop_pos = self.tree.dropIndicatorPosition()
        selected = [
            it.data(0, Qt.UserRole) for it in self.tree.selectedItems()
        ]

        if (
            target_item
            and drop_pos == QAbstractItemView.OnItem
            and selected
            and target_item not in self.tree.selectedItems()
            and self.canvas
        ):
            target_gitem = target_item.data(0, Qt.UserRole)
            if (
                target_gitem
                and not isinstance(target_gitem, QGraphicsItemGroup)
            ):
                items = [target_gitem] + sorted(
                    selected, key=lambda g: g.zValue()
                )
                group = self.canvas.group_selected(items, sort_items=False)
                if group:
                    event.accept()
                    self.update_layers(self.canvas)
                    self.highlight_item(group)
                    return

        super().dropEvent(event)
        self._sync_scene_from_tree()

    def _sync_scene_from_tree(self):
        """Apply the current tree hierarchy to the QGraphicsScene."""
        if not self.canvas:
            return

        z_index = 0

        root = self.tree.invisibleRootItem()
        if (
            root.childCount() == 1
            and root.child(0).data(0, Qt.UserRole) is None
        ):
            root = root.child(0)

        stack = [(root, None)]
        while stack:
            tparent, gparent = stack.pop()
            for idx in range(tparent.childCount()):
                child = tparent.child(idx)
                gitem = child.data(0, Qt.UserRole)
                if gitem:
                    target_parent = gparent if isinstance(
                        gparent, QGraphicsItemGroup) else None
                    if gitem.parentItem() is not target_parent:
                        gitem.setParentItem(target_parent)
                        gitem.setFlag(
                            QGraphicsItem.ItemIsMovable,
                            gitem.flags() & QGraphicsItem.ItemIsMovable,
                        )
                        gitem.setFlag(
                            QGraphicsItem.ItemIsSelectable,
                            gitem.flags() & QGraphicsItem.ItemIsSelectable,
                        )
                    self._animate_z(gitem, z_index)
                    z_index += 1
                stack.append((child, gitem))

    def _animate_z(self, gitem, z):
        """Animate z-value changes while avoiding animation loops."""
        if gitem.zValue() == z:
            return
        if isinstance(gitem, QGraphicsObject):
            # Do not restart an animation that is already running towards
            # the same target value, otherwise the opacity effect will keep
            # toggling and the items will appear to bounce indefinitely.
            current_target = self._z_anims.get(gitem)
            if current_target == z:
                return
            anim = QPropertyAnimation(gitem, b"zValue", self)
            anim.setDuration(150)
            anim.setStartValue(gitem.zValue())
            anim.setEndValue(z)

            def _cleanup():
                self._z_anims.pop(gitem, None)

            anim.finished.connect(_cleanup)
            self._z_anims[gitem] = z
            anim.start(QPropertyAnimation.DeleteWhenStopped)
        else:
            gitem.setZValue(z)
