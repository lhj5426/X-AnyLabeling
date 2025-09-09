from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt


class LabelCategoryWidget(QtWidgets.QListWidget):
    """A widget to display a list of label categories with checkboxes."""

    category_selection_changed = QtCore.pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super(LabelCategoryWidget, self).__init__(parent)
        self.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.itemChanged.connect(self._on_item_changed)

    def add_category(self, category_name):
        """Adds a new category to the list if it doesn't exist."""
        if not self.findItems(category_name, Qt.MatchExactly):
            item = QtWidgets.QListWidgetItem(category_name, self)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.addItem(item)

    def remove_category(self, category_name):
        """Removes a category from the list."""
        items = self.findItems(category_name, Qt.MatchExactly)
        for item in items:
            self.takeItem(self.row(item))

    def get_checked_categories(self):
        """Returns a list of all checked category names."""
        checked = []
        for i in range(self.count()):
            item = self.item(i)
            if item.checkState() == Qt.Checked:
                checked.append(item.text())
        return checked

    def set_category_checked(self, category_name, checked):
        """Sets the checked state of a specific category."""
        items = self.findItems(category_name, Qt.MatchExactly)
        if items:
            # Block signals to prevent infinite loops
            self.blockSignals(True)
            items[0].setCheckState(Qt.Checked if checked else Qt.Unchecked)
            self.blockSignals(False)

    def clear_categories(self):
        """Clears all categories from the list."""
        self.clear()

    def _on_item_changed(self, item):
        """Emits a signal when an item's check state changes."""
        category_name = item.text()
        is_checked = item.checkState() == Qt.Checked
        self.category_selection_changed.emit(category_name, is_checked)