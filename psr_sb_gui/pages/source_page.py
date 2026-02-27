import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
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
    # Column indices
    COL_CHECK = 0
    COL_NAME = 1
    COL_COORDSYS = 2
    COL_COORD1 = 3
    COL_COORD2 = 4
    COL_SCAN = 5

    # Characters not allowed in Linux filenames or that require escaping
    _INVALID_NAME_CHARS = set(' #/\\\0\'"!$&()*;<>?[]`{|}~^')

    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Sources")
        self.setSubTitle("Specify the sources you want to observe.")

        layout = QVBoxLayout()

        # --- Source table ---
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["", "Name", "Coord System", "Coord 1 (RA/l)", "Coord 2 (Dec/b)", "Scan Length (s)"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.table.setItemDelegateForColumn(self.COL_COORDSYS, CoordSystemDelegate(self.table))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_CHECK, QHeaderView.Fixed)
        self.table.setColumnWidth(self.COL_CHECK, 30)
        for col in range(self.COL_NAME, self.COL_SCAN + 1):
            header.setSectionResizeMode(col, QHeaderView.Stretch)
        self._header_checked = False
        header.sectionClicked.connect(self._on_header_clicked)
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
        self.name_edit.setToolTip("Name of the pulsar or astronomical source")
        row1.addWidget(self.name_edit)

        self.lookup_btn = QPushButton("Lookup Coordinates")
        self.lookup_btn.setToolTip("Look up coordinates from the ATNF pulsar catalog")
        self.lookup_btn.clicked.connect(self._lookup_atnf)
        row1.addWidget(self.lookup_btn)

        row1.addWidget(QLabel("Coord System:"))
        self.coord_system_combo = QComboBox()
        self.coord_system_combo.setToolTip("Coordinate system for source position")
        self._coord_system_dirty = False
        for cs in CoordSystem:
            self.coord_system_combo.addItem(cs.value, cs)
        self.coord_system_combo.currentIndexChanged.connect(self._update_coord_placeholders)
        self.coord_system_combo.currentIndexChanged.connect(self._mark_coord_system_dirty)
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
        self.scan_length_edit.setToolTip("On-source integration time in seconds")
        row2.addWidget(self.scan_length_edit)
        form_layout.addLayout(row2)

        layout.addLayout(form_layout)

        # Set initial placeholders
        self._update_coord_placeholders()

        # --- Action buttons ---
        button_row1 = QHBoxLayout()
        self.add_btn = QPushButton("Add Source")
        self.add_btn.setToolTip("Add a new source or update the selected source")
        self.add_btn.clicked.connect(self._add_or_update_source)
        button_row1.addWidget(self.add_btn)

        self.import_btn = QPushButton("Import from Catalog...")
        self.import_btn.setToolTip("Import sources from a GBT/Astrid catalog file")
        self.import_btn.clicked.connect(self._import_catalog)
        button_row1.addWidget(self.import_btn)

        self.clear_form_btn = QPushButton("Clear Form")
        self.clear_form_btn.setToolTip("Clear all form fields")
        self.clear_form_btn.clicked.connect(self._clear_form)
        button_row1.addWidget(self.clear_form_btn)

        layout.addLayout(button_row1)

        button_row2 = QHBoxLayout()
        self.apply_checked_btn = QPushButton("Apply to Selected")
        self.apply_checked_btn.setToolTip("Apply current form values to all selected sources")
        self.apply_checked_btn.clicked.connect(self._apply_to_checked)
        button_row2.addWidget(self.apply_checked_btn)

        self.remove_checked_btn = QPushButton("Remove Selected")
        self.remove_checked_btn.setToolTip("Remove all selected sources from the table")
        self.remove_checked_btn.clicked.connect(self._remove_checked)
        button_row2.addWidget(self.remove_checked_btn)

        layout.addLayout(button_row2)
        self.setLayout(layout)

    def _mark_coord_system_dirty(self):
        self._coord_system_dirty = True

    def _update_coord_placeholders(self):
        cs = self.coord_system_combo.currentData()
        if cs == CoordSystem.GALACTIC:
            self.coord1_edit.setPlaceholderText("l (degrees)")
            self.coord2_edit.setPlaceholderText("b (degrees)")
            self.coord1_edit.setToolTip("Galactic longitude (degrees)")
            self.coord2_edit.setToolTip("Galactic latitude (degrees)")
        else:
            self.coord1_edit.setPlaceholderText("HH:MM:SS.SS")
            self.coord2_edit.setPlaceholderText("\u00b1DD:MM:SS.SS")
            self.coord1_edit.setToolTip("Right Ascension (HH:MM:SS.S)")
            self.coord2_edit.setToolTip("Declination (DD:MM:SS.S)")

    def _clear_form(self):
        self.name_edit.clear()
        self.coord_system_combo.setCurrentIndex(0)
        self._coord_system_dirty = False
        self.coord1_edit.clear()
        self.coord2_edit.clear()
        self.scan_length_edit.clear()
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)

    def _lookup_atnf(self):
        """Look up source coordinates from the ATNF pulsar catalog."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Lookup", "Enter a source name first.")
            return

        cs = self.coord_system_combo.currentData()
        if cs == CoordSystem.B1950:
            QMessageBox.warning(
                self, "Lookup",
                "ATNF catalog lookup is not available for B1950 coordinates.\n"
                "Please select J2000 or Galactic."
            )
            return

        try:
            import psrqpy
        except ImportError:
            QMessageBox.warning(
                self, "Lookup",
                "The psrqpy package is required for ATNF lookups.\n"
                "Install it with: pip install psrqpy"
            )
            return

        # Build list of name variants to try
        variants = [name]
        if name.upper().startswith("PSR "):
            variants.append(name[4:])
        else:
            variants.append("PSR " + name)
        if name[0].isdigit():
            variants.append("J" + name)
            variants.append("B" + name)

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            result = None
            for variant in variants:
                try:
                    q = psrqpy.QueryATNF(
                        params=["JNAME", "BNAME", "RAJ", "DECJ", "GL", "GB"],
                        psrs=[variant],
                    )
                    if q.num_pulsars and q.num_pulsars > 0:
                        result = q
                        break
                except Exception:
                    continue
        finally:
            QApplication.restoreOverrideCursor()

        if result is None or result.num_pulsars == 0:
            QMessageBox.warning(
                self, "Lookup",
                f"Source '{name}' not found in the ATNF pulsar catalog."
            )
            return

        if cs == CoordSystem.GALACTIC:
            gl = result["GL"][0]
            gb = result["GB"][0]
            if gl is not None and gb is not None:
                self.coord1_edit.setText(str(float(gl)))
                self.coord2_edit.setText(str(float(gb)))
            else:
                QMessageBox.warning(self, "Lookup", "Galactic coordinates not available for this source.")
        else:
            raj = result["RAJ"][0]
            decj = result["DECJ"][0]
            if raj is not None and decj is not None:
                self.coord1_edit.setText(str(raj))
                self.coord2_edit.setText(str(decj))
            else:
                QMessageBox.warning(self, "Lookup", "J2000 coordinates not available for this source.")

    def _on_row_selected(self, row):
        if row < 0:
            return
        self.name_edit.setText(self.table.item(row, self.COL_NAME).text())
        cs_text = self.table.item(row, self.COL_COORDSYS).text()
        for i in range(self.coord_system_combo.count()):
            if self.coord_system_combo.itemText(i) == cs_text:
                self.coord_system_combo.setCurrentIndex(i)
                break
        self._coord_system_dirty = False
        self.coord1_edit.setText(self.table.item(row, self.COL_COORD1).text())
        self.coord2_edit.setText(self.table.item(row, self.COL_COORD2).text())
        self.scan_length_edit.setText(self.table.item(row, self.COL_SCAN).text())

    def _on_header_clicked(self, section):
        if section != self.COL_CHECK:
            return
        self._header_checked = not self._header_checked
        for row in range(self.table.rowCount()):
            self._set_row_checked(row, self._header_checked)

    def _checked_rows(self):
        """Return list of row indices where checkbox is checked."""
        rows = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_CHECK)
            if item and item.checkState() == Qt.Checked:
                rows.append(row)
        return rows

    def _set_row_checked(self, row, checked):
        item = self.table.item(row, self.COL_CHECK)
        if item:
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)

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
        if col == self.COL_CHECK:
            return
        item = self.table.item(row, col)
        self._pre_edit_value = item.text() if item else ""

    def _on_cell_edited(self, row, col):
        """Called when a cell value changes. Validates and reverts if invalid."""
        if self._editing_blocked:
            return
        if col == self.COL_CHECK:
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
            if not re.match(r"^\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?$", coord1):
                return "RA must be in HH:MM:SS.SS format (e.g. 17:13:49.53)."
            ra_hours = self._parse_sexagesimal(coord1)
            if ra_hours is None or not (0 <= ra_hours < 24):
                return "RA must be between 00:00:00 and 23:59:59.99."

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

        selected_row = self.table.currentRow()
        if selected_row >= 0:
            self._set_table_row(selected_row, name, cs.value, coord1, coord2, scan_text)
        else:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._set_table_row(row, name, cs.value, coord1, coord2, scan_text)

        self._clear_form()
        self.completeChanged.emit()

    def _set_table_row(self, row, name, cs_text, coord1, coord2, scan_text):
        self._editing_blocked = True
        # Checkbox column
        check_item = self.table.item(row, self.COL_CHECK)
        if check_item is None:
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check_item.setCheckState(Qt.Unchecked)
            self.table.setItem(row, self.COL_CHECK, check_item)
        # Data columns
        self.table.setItem(row, self.COL_NAME, QTableWidgetItem(name))
        self.table.setItem(row, self.COL_COORDSYS, QTableWidgetItem(cs_text))
        self.table.setItem(row, self.COL_COORD1, QTableWidgetItem(coord1))
        self.table.setItem(row, self.COL_COORD2, QTableWidgetItem(coord2))
        self.table.setItem(row, self.COL_SCAN, QTableWidgetItem(scan_text))
        self._editing_blocked = False

    def _apply_to_checked(self):
        checked = self._checked_rows()
        if not checked:
            QMessageBox.information(self, "Apply to Selected", "No sources are checked.")
            return

        name = self.name_edit.text().strip()
        coord1 = self.coord1_edit.text().strip()
        coord2 = self.coord2_edit.text().strip()
        scan_text = self.scan_length_edit.text().strip()
        apply_coord_system = self._coord_system_dirty
        apply_name = bool(name)

        # Nothing to apply?
        if not any([apply_name, apply_coord_system, coord1, coord2, scan_text]):
            QMessageBox.information(
                self, "Apply to Selected",
                "All form fields are empty. Enter values in the form fields you want to apply."
            )
            return

        # Validate non-empty fields using the first checked row as reference
        ref_row = checked[0]
        if apply_name:
            error = self._validate_cell(ref_row, self.COL_NAME, name)
            if error:
                QMessageBox.warning(self, "Validation Error", error)
                return
        if coord1:
            # Need coord system context — validate per-row later
            pass
        if coord2:
            pass
        if scan_text:
            error = self._validate_cell(ref_row, self.COL_SCAN, scan_text)
            if error:
                QMessageBox.warning(self, "Validation Error", error)
                return

        # Warn about duplicate names
        if apply_name and len(checked) > 1:
            reply = QMessageBox.warning(
                self, "Duplicate Names",
                f"This will set {len(checked)} sources to the same name \"{name}\", "
                "creating duplicates. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.No:
                apply_name = False

        # Apply to each checked row
        self._editing_blocked = True
        for row in checked:
            if apply_name:
                self.table.item(row, self.COL_NAME).setText(name)
            if apply_coord_system:
                cs_text = self.coord_system_combo.currentData().value
                self.table.item(row, self.COL_COORDSYS).setText(cs_text)
            if coord1:
                error = self._validate_cell(row, self.COL_COORD1, coord1)
                if error:
                    self._editing_blocked = False
                    QMessageBox.warning(
                        self, "Validation Error",
                        f"Row {row + 1}: {error}"
                    )
                    return
                self.table.item(row, self.COL_COORD1).setText(coord1)
            if coord2:
                error = self._validate_cell(row, self.COL_COORD2, coord2)
                if error:
                    self._editing_blocked = False
                    QMessageBox.warning(
                        self, "Validation Error",
                        f"Row {row + 1}: {error}"
                    )
                    return
                self.table.item(row, self.COL_COORD2).setText(coord2)
            if scan_text:
                self.table.item(row, self.COL_SCAN).setText(scan_text)
        self._editing_blocked = False
        self.completeChanged.emit()

    def _remove_checked(self):
        checked = self._checked_rows()
        if not checked:
            QMessageBox.information(self, "Remove Selected", "No sources are checked.")
            return

        reply = QMessageBox.question(
            self, "Remove Selected",
            f"Remove {len(checked)} checked source(s)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        for row in reversed(checked):
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
        """Parse a GBT/Astrid catalog file.

        Uses the HEAD directive to identify which columns contain the source
        name and coordinates.  Standard GBT column names are NAME, RA, DEC,
        GLON, and GLAT (case-insensitive).
        """
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
                        col_names = [c.upper() for c in value.split()]
                        in_data = True
                    continue

                if in_data:
                    parts = line.split()
                    if len(parts) < len(col_names):
                        continue

                    name_idx = self._find_col(col_names, ("NAME",))
                    glon_idx = self._find_col(col_names, ("GLON",))
                    glat_idx = self._find_col(col_names, ("GLAT",))
                    ra_idx = self._find_col(col_names, ("RA",))
                    dec_idx = self._find_col(col_names, ("DEC",))

                    if glon_idx is not None and glat_idx is not None:
                        c1_idx, c2_idx = glon_idx, glat_idx
                        coord_system = CoordSystem.GALACTIC
                    elif ra_idx is not None and dec_idx is not None:
                        c1_idx, c2_idx = ra_idx, dec_idx
                    else:
                        raise ValueError(
                            "Catalog HEAD line must contain coordinate "
                            "columns (RA/DEC or GLON/GLAT)."
                        )

                    if name_idx is None:
                        raise ValueError(
                            "Catalog HEAD line must contain a NAME column."
                        )

                    sources.append(
                        Source(
                            name=parts[name_idx],
                            coord_system=coord_system,
                            coord1=parts[c1_idx],
                            coord2=parts[c2_idx],
                            scan_length=None,
                        )
                    )

        return sources

    @staticmethod
    def _find_col(col_names, candidates):
        """Return the index of the first matching column name, or None."""
        for name in candidates:
            try:
                return col_names.index(name)
            except ValueError:
                continue
        return None

    def _sources_from_table(self):
        """Read all sources from the table widget."""
        sources = []
        for row in range(self.table.rowCount()):
            name = self.table.item(row, self.COL_NAME).text()
            cs_text = self.table.item(row, self.COL_COORDSYS).text()
            coord1 = self.table.item(row, self.COL_COORD1).text()
            coord2 = self.table.item(row, self.COL_COORD2).text()
            scan_text = self.table.item(row, self.COL_SCAN).text()

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
            scan_text = self.table.item(row, self.COL_SCAN).text().strip()
            name = self.table.item(row, self.COL_NAME).text()
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
