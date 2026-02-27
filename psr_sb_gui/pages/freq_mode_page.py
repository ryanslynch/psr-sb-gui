from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
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
    QWidget,
    QWizardPage,
)

from psr_sb_gui.models.observation import (
    FREQ_BAND_NAMES,
    FREQ_BANDS,
    ObsMode,
    ObservationModel,
)

# Per-source table column indices
COL_NAME = 0
COL_BAND = 1
COL_MODE = 2
COL_COHERENT = 3
COL_POLCAL = 4
COL_EPHEM = 5
COL_DM = 6

MODE_LABELS = ["Fold", "Search"]


class FreqBandDelegate(QStyledItemDelegate):
    """Delegate providing a combobox for the frequency band column."""

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        for name in FREQ_BAND_NAMES:
            combo.addItem(name)
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


class ObsModeDelegate(QStyledItemDelegate):
    """Delegate providing a combobox for the obs mode (Fold/Search) column."""

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        for label in MODE_LABELS:
            combo.addItem(label)
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


class FreqModePage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Frequency & Observing Mode")
        self.setSubTitle(
            "Select the radio frequency range and observing mode for your observations."
        )

        layout = QVBoxLayout()

        # --- Global settings group ---
        self.global_group = QGroupBox("Global Settings")
        global_group = self.global_group
        global_layout = QVBoxLayout()

        # Frequency band row
        band_row = QHBoxLayout()
        band_row.addWidget(QLabel("Frequency Band:"))
        self.band_combo = QComboBox()
        self.band_combo.setToolTip("Radio frequency band and receiver")
        for name in FREQ_BAND_NAMES:
            self.band_combo.addItem(name)
        self.band_combo.currentTextChanged.connect(self._update_band_info)
        band_row.addWidget(self.band_combo)
        band_row.addStretch()
        global_layout.addLayout(band_row)

        # Band info label
        self.band_info_label = QLabel()
        self.band_info_label.setStyleSheet("color: gray; margin-left: 10px;")
        global_layout.addWidget(self.band_info_label)

        # Obs mode row
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Obs. Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.setToolTip(
            "Pulsar observing mode (Fold for timing, Search for surveys, "
            "new pulsars, and single-pulse studies)"
        )
        for label in MODE_LABELS:
            self.mode_combo.addItem(label)
        mode_row.addWidget(self.mode_combo)
        self.coherent_check = QCheckBox("Coherent Dedispersion")
        self.coherent_check.setToolTip(
            "Apply coherent dedispersion to remove interstellar dispersion in real time"
        )
        self.coherent_check.setChecked(True)
        mode_row.addWidget(self.coherent_check)
        mode_row.addStretch()
        global_layout.addLayout(mode_row)

        # Pol cal checkbox
        self.pol_cal_check = QCheckBox("Include polarization calibration scan")
        self.pol_cal_check.setToolTip("Include a noise diode scan for polarization calibration")
        global_layout.addWidget(self.pol_cal_check)

        global_group.setLayout(global_layout)
        layout.addWidget(global_group)

        # --- Per-source config ---
        self.per_source_check = QCheckBox("Configure frequency/mode per source")
        self.per_source_check.setToolTip("Override global settings with per-source frequency band and mode")
        self.per_source_check.toggled.connect(self._toggle_per_source)
        layout.addWidget(self.per_source_check)

        # Per-source table (initially hidden)
        self.per_source_group = QGroupBox("Per-Source Configuration")
        ps_layout = QVBoxLayout()

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Source", "Freq Band", "Obs. Mode", "Coherent DD",
             "Pol Cal", "Ephemeris", "DM"]
        )
        header_tooltips = [
            "Source name",
            "Radio frequency band for this source",
            "Observing mode for this source",
            "Enable coherent dedispersion for this source",
            "Include polarization calibration for this source",
            "Pulsar ephemeris file (required for fold modes)",
            "Dispersion measure in pc/cm\u00b3 (required for coherent search)",
        ]
        for col, tip in enumerate(header_tooltips):
            self.table.horizontalHeaderItem(col).setToolTip(tip)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.table.setItemDelegateForColumn(COL_BAND, FreqBandDelegate(self.table))
        self.table.setItemDelegateForColumn(COL_MODE, ObsModeDelegate(self.table))

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_BAND, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_MODE, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_COHERENT, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_POLCAL, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_EPHEM, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_DM, QHeaderView.ResizeToContents)

        self.table.cellChanged.connect(self._on_cell_changed)

        ps_layout.addWidget(self.table)
        self.per_source_group.setLayout(ps_layout)
        self.per_source_group.setVisible(False)
        layout.addWidget(self.per_source_group)

        layout.addStretch()
        self.setLayout(layout)

        # Initialize band info
        self._update_band_info()

    # --- Helpers ---

    def _update_band_info(self):
        band_name = self.band_combo.currentText()
        band = FREQ_BANDS.get(band_name)
        if band:
            self.band_info_label.setText(band.description)
        else:
            self.band_info_label.setText("")

    def _obs_mode_from_ui(self, mode_text, coherent):
        """Map UI controls to ObsMode enum."""
        if mode_text == "Fold":
            return ObsMode.COHERENT_FOLD if coherent else ObsMode.FOLD
        return ObsMode.COHERENT_SEARCH if coherent else ObsMode.SEARCH

    def _obs_mode_to_ui(self, obs_mode):
        """Map ObsMode enum to (mode_text, coherent_bool)."""
        if obs_mode in (ObsMode.FOLD, ObsMode.COHERENT_FOLD):
            mode_text = "Fold"
        else:
            mode_text = "Search"
        coherent = obs_mode in (ObsMode.COHERENT_FOLD, ObsMode.COHERENT_SEARCH)
        return mode_text, coherent

    def _toggle_per_source(self, checked):
        self.global_group.setEnabled(not checked)
        self.per_source_group.setVisible(checked)
        if checked:
            self._populate_table()

    def _populate_table(self):
        """Populate the per-source table from observation.sources with current global defaults."""
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        global_band = self.band_combo.currentText()
        global_mode_text = self.mode_combo.currentText()
        global_coherent = self.coherent_check.isChecked()

        for src in self.observation.sources:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Source name (read-only)
            name_item = QTableWidgetItem(src.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, COL_NAME, name_item)

            # Freq band — use per-source override or global default
            band = src.freq_range if src.freq_range else global_band
            self.table.setItem(row, COL_BAND, QTableWidgetItem(band))

            # Obs mode — use per-source override or global default
            if src.obs_mode:
                mode_text, coherent = self._obs_mode_to_ui(src.obs_mode)
            else:
                mode_text = global_mode_text
                coherent = global_coherent
            self.table.setItem(row, COL_MODE, QTableWidgetItem(mode_text))

            # Coherent DD checkbox
            self._set_coherent_widget(row, coherent)

            # Pol cal checkbox
            self._set_polcal_widget(row, src.include_pol_cal)

            # Ephemeris — button + path label (or N/A placeholder)
            self._set_ephemeris_widget(row, src.parfile)

            # DM (or N/A placeholder)
            dm_text = str(src.dm) if src.dm is not None else ""
            self.table.setItem(row, COL_DM, QTableWidgetItem(dm_text))

        self.table.blockSignals(False)
        self._update_column_visibility()

    def _set_coherent_widget(self, row, checked):
        """Set a centered checkbox widget in the Coherent DD column."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)
        cb = QCheckBox()
        cb.setChecked(checked)
        cb.toggled.connect(lambda *_: self._update_column_visibility())
        layout.addWidget(cb)
        self.table.setCellWidget(row, COL_COHERENT, container)

    def _get_coherent_checked(self, row):
        """Return whether the coherent checkbox is checked for a row."""
        container = self.table.cellWidget(row, COL_COHERENT)
        if container:
            cb = container.findChild(QCheckBox)
            if cb:
                return cb.isChecked()
        return False

    def _set_polcal_widget(self, row, checked):
        """Set a centered checkbox widget in the Pol Cal column."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)
        cb = QCheckBox()
        cb.setChecked(checked)
        layout.addWidget(cb)
        self.table.setCellWidget(row, COL_POLCAL, container)

    def _get_polcal_checked(self, row):
        """Return whether the pol cal checkbox is checked for a row."""
        container = self.table.cellWidget(row, COL_POLCAL)
        if container:
            cb = container.findChild(QCheckBox)
            if cb:
                return cb.isChecked()
        return False

    def _set_ephemeris_widget(self, row, path=""):
        """Set a browse button + path label in the ephemeris column."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 0, 2, 0)
        path_label = QLabel(path)
        path_label.setToolTip(path)
        path_label.setStyleSheet("color: gray;")
        btn = QPushButton("Browse...")
        btn.setFixedWidth(70)
        btn.clicked.connect(lambda *_, r=row: self._browse_ephemeris(r))
        layout.addWidget(path_label, stretch=1)
        layout.addWidget(btn)
        self.table.setCellWidget(row, COL_EPHEM, container)

    def _get_ephemeris_path(self, row):
        """Return the ephemeris path for a row."""
        container = self.table.cellWidget(row, COL_EPHEM)
        if container:
            label = container.findChild(QLabel)
            if label:
                return label.text()
        return ""

    def _browse_ephemeris(self, row):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Ephemeris File", "",
            "Par Files (*.par);;All Files (*)"
        )
        if file_path:
            container = self.table.cellWidget(row, COL_EPHEM)
            if container:
                label = container.findChild(QLabel)
                if label:
                    label.setText(file_path)
                    label.setToolTip(file_path)

    def _on_cell_changed(self, row, col):
        """React to mode column changes to update column visibility."""
        if col == COL_MODE:
            self._update_column_visibility()

    def _update_column_visibility(self):
        """Show/hide ephemeris and DM columns based on per-source modes.

        When columns are visible due to mixed modes, rows that don't need
        the field show a disabled 'N/A' marker instead of an editable widget.
        """
        any_fold = False
        any_coherent_search = False

        # First pass: determine which columns are needed
        row_modes = []
        for row in range(self.table.rowCount()):
            mode_item = self.table.item(row, COL_MODE)
            mode_text = mode_item.text() if mode_item else "Fold"
            coherent = self._get_coherent_checked(row)
            is_fold = mode_text == "Fold"
            is_coherent_search = mode_text == "Search" and coherent
            row_modes.append((is_fold, is_coherent_search))
            if is_fold:
                any_fold = True
            if is_coherent_search:
                any_coherent_search = True

        self.table.setColumnHidden(COL_EPHEM, not any_fold)
        self.table.setColumnHidden(COL_DM, not any_coherent_search)

        # Second pass: set N/A for non-applicable rows
        self.table.blockSignals(True)
        for row, (is_fold, is_coherent_search) in enumerate(row_modes):
            # Ephemeris column
            if any_fold:
                if is_fold:
                    # Ensure a browse widget is present (not N/A)
                    container = self.table.cellWidget(row, COL_EPHEM)
                    if not container or not container.findChild(QPushButton):
                        path = self._get_ephemeris_path(row)
                        self._set_ephemeris_widget(row, path)
                else:
                    # Show N/A label
                    self._set_na_widget(row, COL_EPHEM)

            # DM column
            if any_coherent_search:
                dm_item = self.table.item(row, COL_DM)
                if is_coherent_search:
                    # Ensure editable (restore from N/A if needed)
                    if dm_item and dm_item.text() == "N/A":
                        dm_item.setText("")
                        dm_item.setFlags(dm_item.flags() | Qt.ItemIsEditable | Qt.ItemIsEnabled)
                        dm_item.setForeground(Qt.black)
                else:
                    # Show N/A
                    if dm_item is None:
                        dm_item = QTableWidgetItem("N/A")
                        self.table.setItem(row, COL_DM, dm_item)
                    else:
                        dm_item.setText("N/A")
                    dm_item.setFlags(dm_item.flags() & ~Qt.ItemIsEditable)
                    dm_item.setForeground(Qt.gray)
        self.table.blockSignals(False)

    def _set_na_widget(self, row, col):
        """Set a read-only 'N/A' label in a cell widget column."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        label = QLabel("N/A")
        label.setStyleSheet("color: gray;")
        layout.addWidget(label)
        self.table.setCellWidget(row, col, container)

    # --- Page lifecycle ---

    def initializePage(self):
        """Populate UI from model."""
        # Global freq band
        band_idx = self.band_combo.findText(self.observation.global_freq_range)
        if band_idx >= 0:
            self.band_combo.setCurrentIndex(band_idx)

        # Global obs mode
        mode_text, coherent = self._obs_mode_to_ui(self.observation.global_obs_mode)
        mode_idx = self.mode_combo.findText(mode_text)
        if mode_idx >= 0:
            self.mode_combo.setCurrentIndex(mode_idx)
        self.coherent_check.setChecked(coherent)

        # Pol cal
        self.pol_cal_check.setChecked(self.observation.include_pol_cal)

        # Per-source config
        self.per_source_check.setChecked(self.observation.per_source_config)
        if self.observation.per_source_config:
            self._populate_table()

    def validatePage(self):
        """Validate and save to model."""
        # Save global settings
        self.observation.global_freq_range = self.band_combo.currentText()
        global_mode_text = self.mode_combo.currentText()
        global_coherent = self.coherent_check.isChecked()
        self.observation.global_obs_mode = self._obs_mode_from_ui(
            global_mode_text, global_coherent
        )
        self.observation.include_pol_cal = self.pol_cal_check.isChecked()
        self.observation.per_source_config = self.per_source_check.isChecked()

        if self.per_source_check.isChecked():
            # Validate and save per-source config
            missing_ephem = []
            missing_dm = []

            for row in range(self.table.rowCount()):
                src = self.observation.sources[row]
                src.freq_range = self.table.item(row, COL_BAND).text()

                mode_item = self.table.item(row, COL_MODE)
                mode_text = mode_item.text() if mode_item else "Fold"
                coherent = self._get_coherent_checked(row)
                src.obs_mode = self._obs_mode_from_ui(mode_text, coherent)
                src.include_pol_cal = self._get_polcal_checked(row)

                # Ephemeris — only applicable for fold modes
                if mode_text == "Fold":
                    src.parfile = self._get_ephemeris_path(row)
                    if not src.parfile:
                        missing_ephem.append(src.name)
                else:
                    src.parfile = ""

                # DM — only applicable for coherent search
                if mode_text == "Search" and coherent:
                    dm_text = self.table.item(row, COL_DM).text().strip()
                    if not dm_text or dm_text == "N/A":
                        missing_dm.append(src.name)
                    else:
                        try:
                            dm_val = float(dm_text)
                            if dm_val <= 0:
                                missing_dm.append(src.name)
                            else:
                                src.dm = dm_val
                        except ValueError:
                            missing_dm.append(src.name)
                else:
                    src.dm = None

            if missing_ephem:
                QMessageBox.warning(
                    self, "Validation Error",
                    "An ephemeris file is required for sources in Fold mode.\n\n"
                    f"Missing: {', '.join(missing_ephem)}"
                )
                return False

            if missing_dm:
                QMessageBox.warning(
                    self, "Validation Error",
                    "A DM value (> 0) is required for sources in Coherent Search mode.\n\n"
                    f"Missing or invalid: {', '.join(missing_dm)}"
                )
                return False
        else:
            # Clear per-source overrides
            for src in self.observation.sources:
                src.freq_range = None
                src.obs_mode = None
                src.parfile = ""
                src.dm = None
                src.include_pol_cal = False

        return True
