from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

from psr_sb_gui.models.observation import (
    FREQ_BANDS,
    POLN_DISPLAY,
    POLN_INTERNAL,
    ObsMode,
    ObservationModel,
    compute_tint,
    get_default_vegas_params,
    get_recommended_scale,
    get_valid_acclen_values,
    get_valid_numchan_values,
)


class ParamsPage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Backend Parameters")
        self.setSubTitle(
            "Review and adjust VEGAS backend parameters for each source. "
            "Select a source on the left to view and edit its parameters."
        )

        self._current_index: int = -1

        # Main layout with splitter
        layout = QVBoxLayout()
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: source list
        self._source_list = QListWidget()
        self._source_list.setToolTip("Select a source to view and edit its VEGAS backend parameters")
        self._splitter.addWidget(self._source_list)

        # Right panel: detail area
        self._detail_widget = QWidget()
        self._detail_layout = QVBoxLayout(self._detail_widget)
        self._detail_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._splitter.addWidget(self._detail_widget)

        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 3)

        layout.addWidget(self._splitter)
        self.setLayout(layout)

        # Widget references for currently displayed source
        self._header_label: QLabel = None
        self._bw_label: QLabel = None
        self._center_freq_spins: list[QDoubleSpinBox] = []
        self._numchan_combo: QComboBox = None
        self._tint_combo: QComboBox = None
        self._scale_label: QLabel = None
        self._poln_combo: QComboBox = None
        self._data_rate_label: QLabel = None
        self._fold_bins_spin: QDoubleSpinBox = None
        self._fold_dumptime_spin: QDoubleSpinBox = None
        self._detail_group: QGroupBox = None

        # Cached state for current source
        self._cur_bandwidth_mhz: int = 0
        self._cur_is_coherent: bool = False
        self._cur_is_fold: bool = False

        self._source_list.currentRowChanged.connect(self._on_source_changed)

    def initializePage(self):
        """Initialize per-source VegasParams and populate the source list."""
        for src in self.observation.sources:
            band_label = self._get_source_band(src)
            obs_mode = self._get_source_mode(src)
            if (src.vegas_params is None
                    or src.vegas_params._band_label != band_label
                    or src.vegas_params._obs_mode_value != obs_mode.value):
                src.vegas_params = get_default_vegas_params(band_label, obs_mode)

        # Populate source list
        self._source_list.blockSignals(True)
        self._source_list.clear()
        for src in self.observation.sources:
            self._source_list.addItem(src.name)
        self._source_list.blockSignals(False)

        self._current_index = -1
        if self.observation.sources:
            self._source_list.setCurrentRow(0)

    def validatePage(self):
        """Save current source and validate all sources."""
        self._save_current_source()

        for src in self.observation.sources:
            p = src.vegas_params
            if p is None:
                continue

            obs_mode = self._get_source_mode(src)
            if obs_mode.is_fold:
                if p.fold_bins <= 0:
                    QMessageBox.warning(
                        self, "Validation Error",
                        f"Fold bins must be > 0 for {src.name}."
                    )
                    return False
                if p.fold_dumptime <= 0:
                    QMessageBox.warning(
                        self, "Validation Error",
                        f"Fold dump time must be > 0 for {src.name}."
                    )
                    return False

            for i, cf in enumerate(p.center_freqs):
                if cf <= 0:
                    QMessageBox.warning(
                        self, "Validation Error",
                        f"Center frequency must be > 0 for {src.name} "
                        f"(window {i + 1})."
                    )
                    return False

        return True

    # ------------------------------------------------------------------
    # Source switching
    # ------------------------------------------------------------------

    def _on_source_changed(self, row: int):
        """Handle source list selection change."""
        if row < 0 or row >= len(self.observation.sources):
            return
        self._save_current_source()
        self._current_index = row
        self._load_source(row)

    def _save_current_source(self):
        """Read widget values into the current source's VegasParams."""
        if self._current_index < 0:
            return
        if self._current_index >= len(self.observation.sources):
            return

        src = self.observation.sources[self._current_index]
        p = src.vegas_params
        if p is None or self._numchan_combo is None:
            return

        p.numchan = self._numchan_combo.currentData() or p.numchan
        p.tint = self._tint_combo.currentData() or p.tint
        p.scale = int(self._scale_label.text())
        display_poln = self._poln_combo.currentText()
        p.polnmode = POLN_INTERNAL.get(display_poln, p.polnmode)

        # Center frequencies
        for i, spin in enumerate(self._center_freq_spins):
            if i < len(p.center_freqs):
                p.center_freqs[i] = spin.value()

        # Fold params
        if self._cur_is_fold and self._fold_bins_spin is not None:
            p.fold_bins = int(self._fold_bins_spin.value())
            p.fold_dumptime = self._fold_dumptime_spin.value()

    def _load_source(self, index: int):
        """Rebuild the detail panel for the source at the given index."""
        src = self.observation.sources[index]
        band_label = self._get_source_band(src)
        obs_mode = self._get_source_mode(src)
        band = FREQ_BANDS[band_label]
        bw = int(band.bandwidth)
        p = src.vegas_params

        self._cur_bandwidth_mhz = bw
        self._cur_is_coherent = obs_mode.is_coherent
        self._cur_is_fold = obs_mode.is_fold

        # Clear existing detail widgets
        self._clear_detail_panel()

        # Header
        self._header_label = QLabel(f"{band_label} — {obs_mode.display_label}")
        self._header_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self._detail_layout.addWidget(self._header_label)

        # Form in a group box
        self._detail_group = QGroupBox()
        form = QFormLayout()

        # Bandwidth with window count
        n_windows = len(p.center_freqs)
        if n_windows > 1:
            bw_text = f"{bw} MHz per window ({n_windows} windows)"
        else:
            bw_text = f"{bw} MHz (1 window)"
        self._bw_label = QLabel(bw_text)
        form.addRow("Bandwidth:", self._bw_label)

        # Center frequencies
        self._center_freq_spins = []
        for i, cf in enumerate(p.center_freqs):
            spin = QDoubleSpinBox()
            spin.setRange(1.0, 99999.0)
            spin.setDecimals(1)
            spin.setSuffix(" MHz")
            spin.setValue(cf)
            spin.setToolTip("Center frequency for this spectral window in MHz")
            self._center_freq_spins.append(spin)
            if n_windows > 1:
                label = f"Window {i + 1} Center Freq:"
            else:
                label = "Center Frequency:"
            form.addRow(label, spin)

        # Num Channels
        self._numchan_combo = QComboBox()
        self._numchan_combo.setToolTip(
            "Number of spectral channels per window (more channels = finer frequency resolution)"
        )
        valid_nc = get_valid_numchan_values(bw, obs_mode.is_coherent)
        for nc in valid_nc:
            self._numchan_combo.addItem(str(nc), nc)
        idx = self._numchan_combo.findData(p.numchan)
        if idx >= 0:
            self._numchan_combo.setCurrentIndex(idx)
        form.addRow("Channels per Window:", self._numchan_combo)

        # Integration Time
        self._tint_combo = QComboBox()
        self._tint_combo.setToolTip(
            "Integration time per sample (shorter = better time resolution but higher data rate)"
        )
        self._populate_tint_combo(p.numchan, p.tint)
        form.addRow("Integration Time:", self._tint_combo)

        # Scale (read-only)
        self._scale_label = QLabel(str(p.scale))
        self._scale_label.setStyleSheet("font-weight: bold;")
        form.addRow("Scale:", self._scale_label)

        # Polarization — only incoherent search allows Total Intensity
        self._poln_combo = QComboBox()
        self._poln_combo.setToolTip("Polarization recording mode")
        if obs_mode == ObsMode.SEARCH:
            self._poln_combo.addItems(list(POLN_DISPLAY.values()))
            display_poln = POLN_DISPLAY.get(p.polnmode, "Full Stokes")
            self._poln_combo.setCurrentText(display_poln)
        else:
            self._poln_combo.addItem("Full Stokes")
            self._poln_combo.setEnabled(False)
        form.addRow("Polarization:", self._poln_combo)

        # Data rate warning
        self._data_rate_label = QLabel("")
        self._data_rate_label.setWordWrap(True)
        self._data_rate_label.setStyleSheet("color: orange;")
        self._data_rate_label.setVisible(False)
        form.addRow("", self._data_rate_label)

        # Fold-specific fields
        self._fold_bins_spin = None
        self._fold_dumptime_spin = None
        if obs_mode.is_fold:
            self._fold_bins_spin = QDoubleSpinBox()
            self._fold_bins_spin.setRange(1, 65536)
            self._fold_bins_spin.setDecimals(0)
            self._fold_bins_spin.setValue(p.fold_bins)
            self._fold_bins_spin.setToolTip("Number of pulse phase bins for folded profiles")
            form.addRow("Fold Bins:", self._fold_bins_spin)

            self._fold_dumptime_spin = QDoubleSpinBox()
            self._fold_dumptime_spin.setRange(0.1, 600.0)
            self._fold_dumptime_spin.setDecimals(1)
            self._fold_dumptime_spin.setSuffix(" s")
            self._fold_dumptime_spin.setValue(p.fold_dumptime)
            self._fold_dumptime_spin.setToolTip(
                "Time interval between folded profile outputs in seconds"
            )
            form.addRow("Fold Dump Time:", self._fold_dumptime_spin)

        self._detail_group.setLayout(form)
        self._detail_layout.addWidget(self._detail_group)

        # Connect signals
        self._numchan_combo.currentIndexChanged.connect(self._on_numchan_changed)
        self._tint_combo.currentIndexChanged.connect(self._on_tint_changed)
        self._poln_combo.currentIndexChanged.connect(
            lambda: self._update_data_rate_warning()
        )

        # Initial data rate check
        self._update_data_rate_warning()

    def _clear_detail_panel(self):
        """Remove all widgets from the detail panel."""
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._center_freq_spins = []
        self._numchan_combo = None
        self._tint_combo = None
        self._scale_label = None
        self._poln_combo = None
        self._data_rate_label = None
        self._fold_bins_spin = None
        self._fold_dumptime_spin = None
        self._header_label = None
        self._detail_group = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_source_band(self, src) -> str:
        if self.observation.per_source_config and src.freq_range:
            return src.freq_range
        return self.observation.global_freq_range

    def _get_source_mode(self, src) -> ObsMode:
        if self.observation.per_source_config and src.obs_mode:
            return src.obs_mode
        return self.observation.global_obs_mode

    def _populate_tint_combo(self, numchan: int, current_tint: float):
        """Fill the tint combo with valid values for the current numchan."""
        self._tint_combo.blockSignals(True)
        self._tint_combo.clear()
        valid_acclens = get_valid_acclen_values(self._cur_is_coherent)
        best_idx = 0
        best_diff = float("inf")
        for i, acclen in enumerate(valid_acclens):
            tint = compute_tint(acclen, numchan, self._cur_bandwidth_mhz)
            label = self._format_tint(tint)
            self._tint_combo.addItem(label, tint)
            diff = abs(tint - current_tint)
            if diff < best_diff:
                best_diff = diff
                best_idx = i
        self._tint_combo.setCurrentIndex(best_idx)
        self._tint_combo.blockSignals(False)

    def _on_numchan_changed(self):
        """Handle numchan change: update scale, recompute tint options."""
        numchan = self._numchan_combo.currentData()
        if numchan is None:
            return

        new_scale = get_recommended_scale(
            self._cur_bandwidth_mhz, numchan, self._cur_is_coherent
        )
        self._scale_label.setText(str(new_scale))

        old_tint = self._tint_combo.currentData() or 0.0
        self._populate_tint_combo(numchan, old_tint)
        self._update_data_rate_warning()

    def _on_tint_changed(self):
        """Handle tint change: update data rate warning."""
        self._update_data_rate_warning()

    def _update_data_rate_warning(self):
        """Check data rate and acclen, show warnings if needed."""
        if self._numchan_combo is None or self._tint_combo is None:
            return
        numchan = self._numchan_combo.currentData()
        tint = self._tint_combo.currentData()
        if numchan is None or tint is None or tint <= 0:
            self._data_rate_label.setVisible(False)
            return

        display_poln = self._poln_combo.currentText()
        poln = POLN_INTERNAL.get(display_poln, "FULL_STOKES")
        n_pol = 4 if poln == "FULL_STOKES" else 2

        warnings = []

        rate_bytes_per_sec = n_pol * numchan / tint
        rate_mb_per_sec = rate_bytes_per_sec / 1e6
        if rate_mb_per_sec > 400:
            warnings.append(
                f"Data rate ({rate_mb_per_sec:.0f} MB/s) exceeds "
                f"400 MB/s per bank limit."
            )

        if not self._cur_is_coherent:
            acclen = round(tint * self._cur_bandwidth_mhz * 1e6 / numchan)
            if acclen > 64:
                warnings.append(
                    f"Large accumulation length ({acclen}) may cause "
                    f"loss of numerical resolution."
                )

        if warnings:
            self._data_rate_label.setText("Warning: " + " ".join(warnings))
            self._data_rate_label.setVisible(True)
        else:
            self._data_rate_label.setVisible(False)

    @staticmethod
    def _format_tint(tint_seconds: float) -> str:
        """Format tint for display in the combo box."""
        tint_us = tint_seconds * 1e6
        if tint_us >= 1000:
            return f"{tint_us / 1000:.4g} ms ({tint_us:.4g} µs)"
        return f"{tint_us:.4g} µs"
