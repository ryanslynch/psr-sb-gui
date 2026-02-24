import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWizardPage,
)

from psr_sb_gui.models.observation import CoordSystem, ObservationModel, Source


class CoordSystemDelegate(QStyledItemDelegate):
    """Delegate that provides a combobox editor for the Coord System column."""

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        for cs in CoordSystem:
            combo.addItem(cs.value)
        return combo

    def setEditorData(self, editor, index):
        value = index.data(Qt.DisplayRole)
        idx = editor.findText(value)
        if idx >= 0:
            editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class SourcePage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Sources")
        self.setSubTitle("Specify the sources you want to observe.")

        layout = QVBoxLayout()

        # --- Source table ---
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Coord System", "Coord 1 (RA/l)", "Coord 2 (Dec/b)", "Scan Length (s)"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.table.setItemDelegateForColumn(1, CoordSystemDelegate(self.table))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.table.currentCellChanged.connect(lambda row, *_: self._on_row_selected(row))
        self._editing_blocked = False
        self._pre_edit_value = ""
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.cellChanged.connect(self._on_cell_edited)
        layout.addWidget(self.table)

        # --- Entry form ---
        form_layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(32)
        self.name_edit.setPlaceholderText("Source name (e.g. J1713+0747)")
        row1.addWidget(self.name_edit)

        row1.addWidget(QLabel("Coord System:"))
        self.coord_system_combo = QComboBox()
        for cs in CoordSystem:
            self.coord_system_combo.addItem(cs.value, cs)
        self.coord_system_combo.currentIndexChanged.connect(self._update_coord_placeholders)
        row1.addWidget(self.coord_system_combo)
        form_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Coord 1:"))
        self.coord1_edit = QLineEdit()
        row2.addWidget(self.coord1_edit)

        row2.addWidget(QLabel("Coord 2:"))
        self.coord2_edit = QLineEdit()
        row2.addWidget(self.coord2_edit)

        row2.addWidget(QLabel("Scan Length (s):"))
        self.scan_length_edit = QLineEdit()
        self.scan_length_edit.setPlaceholderText("seconds")
        row2.addWidget(self.scan_length_edit)
        form_layout.addLayout(row2)

        layout.addLayout(form_layout)

        # Set initial placeholders
        self._update_coord_placeholders()

        # --- Action buttons ---
        button_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Source")
        self.add_btn.clicked.connect(self._add_or_update_source)
        button_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self._remove_selected)
        button_layout.addWidget(self.remove_btn)

        self.import_btn = QPushButton("Import from Catalog...")
        self.import_btn.clicked.connect(self._import_catalog)
        button_layout.addWidget(self.import_btn)

        self.clear_form_btn = QPushButton("Clear Form")
        self.clear_form_btn.clicked.connect(self._clear_form)
        button_layout.addWidget(self.clear_form_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _update_coord_placeholders(self):
        cs = self.coord_system_combo.currentData()
        if cs == CoordSystem.GALACTIC:
            self.coord1_edit.setPlaceholderText("l (degrees)")
            self.coord2_edit.setPlaceholderText("b (degrees)")
        else:
            self.coord1_edit.setPlaceholderText("HH:MM:SS.SS")
            self.coord2_edit.setPlaceholderText("\u00b1DD:MM:SS.SS")

    def _clear_form(self):
        self.name_edit.clear()
        self.coord_system_combo.setCurrentIndex(0)
        self.coord1_edit.clear()
        self.coord2_edit.clear()
        self.scan_length_edit.clear()
        self.table.clearSelection()

    def _on_row_selected(self, row):
        if row < 0:
            return
        self.name_edit.setText(self.table.item(row, 0).text())
        # Find the matching CoordSystem enum
        cs_text = self.table.item(row, 1).text()
        for i in range(self.coord_system_combo.count()):
            if self.coord_system_combo.itemText(i) == cs_text:
                self.coord_system_combo.setCurrentIndex(i)
                break
        self.coord1_edit.setText(self.table.item(row, 2).text())
        self.coord2_edit.setText(self.table.item(row, 3).text())
        self.scan_length_edit.setText(self.table.item(row, 4).text())

    # Characters not allowed in Linux filenames or that require escaping
    _INVALID_NAME_CHARS = set(' #/\\\0\'"!$&()*;<>?[]`{|}~^')

    # Column indices
    COL_NAME, COL_COORDSYS, COL_COORD1, COL_COORD2, COL_SCAN = range(5)

    def _get_coord_system_for_row(self, row):
        """Return the CoordSystem enum for a table row."""
        cs_text = self.table.item(row, self.COL_COORDSYS).text()
        for member in CoordSystem:
            if member.value == cs_text:
                return member
        return CoordSystem.J2000

    def _validate_cell(self, row, col, value):
        """Validate a single cell value. Returns error message or None."""
        if col == self.COL_NAME:
            if not value:
                return "Source name is required."
            if len(value) > 32:
                return "Source name must be 32 characters or fewer."
            bad_chars = self._INVALID_NAME_CHARS.intersection(value)
            if bad_chars:
                return f"Source name contains invalid characters: {' '.join(sorted(bad_chars))}"

        elif col == self.COL_COORDSYS:
            valid = [cs.value for cs in CoordSystem]
            if value not in valid:
                return f"Coordinate system must be one of: {', '.join(valid)}"

        elif col == self.COL_COORD1:
            if not value:
                return "Coordinate 1 is required."
            cs = self._get_coord_system_for_row(row)
            if cs == CoordSystem.GALACTIC:
                try:
                    l_val = float(value)
                except ValueError:
                    return "Galactic longitude (l) must be a number in degrees."
                if not (0 <= l_val <= 360):
                    return "Galactic longitude (l) must be between 0 and 360 degrees."
            else:
                if not re.match(r"^\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?$", value):
                    return "RA must be in HH:MM:SS.SS format (e.g. 17:13:49.53)."
                ra_hours = self._parse_sexagesimal(value)
                if ra_hours is None or not (0 <= ra_hours < 24):
                    return "RA must be between 00:00:00 and 23:59:59.99."

        elif col == self.COL_COORD2:
            if not value:
                return "Coordinate 2 is required."
            cs = self._get_coord_system_for_row(row)
            if cs == CoordSystem.GALACTIC:
                try:
                    b_val = float(value)
                except ValueError:
                    return "Galactic latitude (b) must be a number in degrees."
                if not (-90 <= b_val <= 90):
                    return "Galactic latitude (b) must be between -90 and +90 degrees."
            else:
                if not re.match(r"^[+-]?\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?$", value):
                    return "Dec must be in \u00b1DD:MM:SS.SS format (e.g. +07:47:37.48)."
                dec_deg = self._parse_sexagesimal(value)
                if dec_deg is None or not (-90 <= dec_deg <= 90):
                    return "Dec must be between -90:00:00 and +90:00:00."

        elif col == self.COL_SCAN:
            if value:
                try:
                    val = float(value)
                except ValueError:
                    return "Scan length must be a number."
                if val <= 0:
                    return "Scan length must be greater than zero."

        return None

    def _on_cell_double_clicked(self, row, col):
        """Capture the current cell value before editing begins."""
        item = self.table.item(row, col)
        self._pre_edit_value = item.text() if item else ""

    def _on_cell_edited(self, row, col):
        """Called when a cell value changes. Validates and reverts if invalid."""
        if self._editing_blocked:
            return
        item = self.table.item(row, col)
        if item is None:
            return
        new_value = item.text().strip()
        error = self._validate_cell(row, col, new_value)
        if error:
            QMessageBox.warning(self, "Validation Error", error)
            self._editing_blocked = True
            item.setText(self._pre_edit_value)
            self._editing_blocked = False
        self.completeChanged.emit()

    @staticmethod
    def _parse_sexagesimal(text):
        """Parse HH:MM:SS.SS or DD:MM:SS.SS and return total value in the base unit (hours or degrees)."""
        parts = text.lstrip("+-").split(":")
        if len(parts) < 2 or len(parts) > 3:
            return None
        try:
            vals = [float(p) for p in parts]
        except ValueError:
            return None
        if vals[0] != int(vals[0]) or vals[0] < 0:
            return None
        if vals[1] != int(vals[1]) or not (0 <= vals[1] < 60):
            return None
        if len(vals) == 3 and not (0 <= vals[2] < 60):
            return None
        total = vals[0] + vals[1] / 60.0
        if len(vals) == 3:
            total += vals[2] / 3600.0
        if text.startswith("-"):
            total = -total
        return total

    def _validate_form(self):
        """Validate the entry form fields. Returns error message or None."""
        name = self.name_edit.text().strip()
        if not name:
            return "Source name is required."
        if len(name) > 32:
            return "Source name must be 32 characters or fewer."
        bad_chars = self._INVALID_NAME_CHARS.intersection(name)
        if bad_chars:
            return f"Source name contains invalid characters: {' '.join(sorted(bad_chars))}"

        coord1 = self.coord1_edit.text().strip()
        coord2 = self.coord2_edit.text().strip()
        if not coord1:
            return "Coordinate 1 is required."
        if not coord2:
            return "Coordinate 2 is required."

        cs = self.coord_system_combo.currentData()
        if cs == CoordSystem.GALACTIC:
            try:
                l_val = float(coord1)
            except ValueError:
                return "Galactic longitude (l) must be a number in degrees."
            if not (0 <= l_val <= 360):
                return "Galactic longitude (l) must be between 0 and 360 degrees."
            try:
                b_val = float(coord2)
            except ValueError:
                return "Galactic latitude (b) must be a number in degrees."
            if not (-90 <= b_val <= 90):
                return "Galactic latitude (b) must be between -90 and +90 degrees."
        else:
            # RA must be in sexagesimal HH:MM:SS.SS format
            if not re.match(r"^\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?$", coord1):
                return "RA must be in HH:MM:SS.SS format (e.g. 17:13:49.53)."
            ra_hours = self._parse_sexagesimal(coord1)
            if ra_hours is None or not (0 <= ra_hours < 24):
                return "RA must be between 00:00:00 and 23:59:59.99."

            # Dec must be in sexagesimal ±DD:MM:SS.SS format
            if not re.match(r"^[+-]?\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?$", coord2):
                return "Dec must be in \u00b1DD:MM:SS.SS format (e.g. +07:47:37.48)."
            dec_deg = self._parse_sexagesimal(coord2)
            if dec_deg is None or not (-90 <= dec_deg <= 90):
                return "Dec must be between -90:00:00 and +90:00:00."

        scan_text = self.scan_length_edit.text().strip()
        if scan_text:
            try:
                val = float(scan_text)
            except ValueError:
                return "Scan length must be a number."
            if val <= 0:
                return "Scan length must be greater than zero."

        return None

    def _add_or_update_source(self):
        error = self._validate_form()
        if error:
            QMessageBox.warning(self, "Validation Error", error)
            return

        name = self.name_edit.text().strip()
        cs = self.coord_system_combo.currentData()
        coord1 = self.coord1_edit.text().strip()
        coord2 = self.coord2_edit.text().strip()
        scan_text = self.scan_length_edit.text().strip()
        scan_length = float(scan_text) if scan_text else None

        selected_row = self.table.currentRow()
        if selected_row >= 0:
            # Update existing row
            self._set_table_row(selected_row, name, cs.value, coord1, coord2, scan_text)
        else:
            # Add new row
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._set_table_row(row, name, cs.value, coord1, coord2, scan_text)

        self._clear_form()
        self.completeChanged.emit()

    def _set_table_row(self, row, name, cs_text, coord1, coord2, scan_text):
        self._editing_blocked = True
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(cs_text))
        self.table.setItem(row, 2, QTableWidgetItem(coord1))
        self.table.setItem(row, 3, QTableWidgetItem(coord2))
        self.table.setItem(row, 4, QTableWidgetItem(scan_text))
        self._editing_blocked = False

    def _remove_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._clear_form()
            self.completeChanged.emit()

    def _import_catalog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Catalog File", "", "Catalog Files (*.cat *.txt);;All Files (*)"
        )
        if not file_path:
            return

        try:
            sources = self._parse_catalog(file_path)
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to parse catalog:\n{e}")
            return

        if not sources:
            QMessageBox.information(self, "Import", "No sources found in catalog file.")
            return

        for src in sources:
            row = self.table.rowCount()
            self.table.insertRow(row)
            scan_text = str(src.scan_length) if src.scan_length is not None else ""
            self._set_table_row(row, src.name, src.coord_system.value, src.coord1, src.coord2, scan_text)

        self.completeChanged.emit()
        QMessageBox.information(
            self,
            "Import Complete",
            f"Imported {len(sources)} source(s).\n\n"
            "Please set scan lengths for imported sources before proceeding.",
        )

    def _parse_catalog(self, file_path):
        """Parse a GBT/Astrid catalog file."""
        sources = []
        coord_system = CoordSystem.J2000  # default
        in_data = False
        col_names = []

        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Parse header directives
                if "=" in line and not in_data:
                    key, _, value = line.partition("=")
                    key = key.strip().lower()
                    value = value.strip()

                    if key == "coordmode":
                        value_upper = value.upper()
                        if value_upper == "GALACTIC":
                            coord_system = CoordSystem.GALACTIC
                        elif value_upper == "B1950":
                            coord_system = CoordSystem.B1950
                        else:
                            coord_system = CoordSystem.J2000

                    if key == "head":
                        col_names = value.split()
                        in_data = True
                    continue

                if in_data:
                    parts = line.split()
                    if len(parts) >= 3:
                        sources.append(
                            Source(
                                name=parts[0],
                                coord_system=coord_system,
                                coord1=parts[1],
                                coord2=parts[2],
                                scan_length=None,
                            )
                        )

        return sources

    def _sources_from_table(self):
        """Read all sources from the table widget."""
        sources = []
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text()
            cs_text = self.table.item(row, 1).text()
            coord1 = self.table.item(row, 2).text()
            coord2 = self.table.item(row, 3).text()
            scan_text = self.table.item(row, 4).text()

            cs = CoordSystem.J2000
            for member in CoordSystem:
                if member.value == cs_text:
                    cs = member
                    break

            scan_length = float(scan_text) if scan_text else None
            sources.append(Source(name=name, coord_system=cs, coord1=coord1, coord2=coord2, scan_length=scan_length))
        return sources

    def initializePage(self):
        """Populate table from model."""
        self.table.setRowCount(0)
        for src in self.observation.sources:
            row = self.table.rowCount()
            self.table.insertRow(row)
            scan_text = str(src.scan_length) if src.scan_length is not None else ""
            self._set_table_row(row, src.name, src.coord_system.value, src.coord1, src.coord2, scan_text)
        self._clear_form()

    def validatePage(self):
        """Validate and save sources to model."""
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Validation Error", "At least one source is required.")
            return False

        # Check all sources have scan lengths
        missing = []
        for row in range(self.table.rowCount()):
            scan_text = self.table.item(row, 4).text().strip()
            name = self.table.item(row, 0).text()
            if not scan_text:
                missing.append(name)
            else:
                try:
                    val = float(scan_text)
                    if val <= 0:
                        missing.append(name)
                except ValueError:
                    missing.append(name)

        if missing:
            QMessageBox.warning(
                self,
                "Validation Error",
                f"Scan length is required for all sources.\n\n"
                f"Missing or invalid: {', '.join(missing)}",
            )
            return False

        self.observation.sources = self._sources_from_table()
        return True

    def isComplete(self):
        return self.table.rowCount() > 0
