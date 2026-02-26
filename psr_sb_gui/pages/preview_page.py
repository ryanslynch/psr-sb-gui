import re
from collections import OrderedDict

from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

from psr_sb_gui.models.observation import (
    FREQ_BANDS,
    ObsMode,
    ObservationModel,
    Source,
    VegasParams,
)
from psr_sb_gui.pages.flux_cal_page import (
    _CALIBRATOR_BY_NAME,
    _format_dec,
    _format_ra,
)


def _safe_name(name: str) -> str:
    """Convert a source name to a valid Python identifier fragment."""
    return re.sub(r"[^A-Za-z0-9]", "_", name)


# ------------------------------------------------------------------
# Python syntax highlighter
# ------------------------------------------------------------------

class _PythonHighlighter(QSyntaxHighlighter):
    """Simple Python syntax highlighter for scheduling block scripts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        # Keywords
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#0000FF"))
        kw_fmt.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def",
            "del", "elif", "else", "except", "False", "finally", "for",
            "from", "global", "if", "import", "in", "is", "lambda",
            "None", "nonlocal", "not", "or", "pass", "raise", "return",
            "True", "try", "while", "with", "yield",
        ]
        for kw in keywords:
            pattern = QRegularExpression(rf"\b{kw}\b")
            self._rules.append((pattern, kw_fmt))

        # Built-in functions / Astrid commands
        builtin_fmt = QTextCharFormat()
        builtin_fmt.setForeground(QColor("#008080"))
        builtins = [
            "Catalog", "Configure", "Slew", "Track", "OnOff", "Balance",
            "ResetConfig", "AutoPeakFocus", "Offset",
        ]
        for b in builtins:
            pattern = QRegularExpression(rf"\b{b}\b")
            self._rules.append((pattern, builtin_fmt))

        # Numbers
        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#FF6600"))
        self._rules.append((
            QRegularExpression(r"\b[0-9]+\.?[0-9]*([eE][+-]?[0-9]+)?\b"),
            num_fmt,
        ))

        # Strings (single and double quoted, including triple-quoted)
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#008000"))
        self._rules.append((
            QRegularExpression(r'""".*?"""|\'\'\'.*?\'\'\''),
            str_fmt,
        ))
        self._rules.append((
            QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"|\'[^\'\\]*(\\.[^\'\\]*)*\''),
            str_fmt,
        ))

        # Comments
        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setForeground(QColor("#808080"))
        self._comment_fmt.setFontItalic(True)

        # Triple-quoted string state tracking
        self._triple_dq = QRegularExpression(r'"""')
        self._triple_sq = QRegularExpression(r"'''")

    def highlightBlock(self, text: str):
        # Apply single-line rules
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

        # Comments (override everything after #)
        comment_match = QRegularExpression(r"#[^\n]*").match(text)
        if comment_match.hasMatch():
            start = comment_match.capturedStart()
            length = comment_match.capturedLength()
            self.setFormat(start, length, self._comment_fmt)

        # Multi-line triple-quoted strings
        self._handle_multiline_strings(text)

    def _handle_multiline_strings(self, text: str):
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#008000"))

        # State: 0 = normal, 1 = inside """, 2 = inside '''
        prev_state = self.previousBlockState()
        if prev_state < 0:
            prev_state = 0

        offset = 0
        if prev_state == 1:
            # We're inside a """ string from a previous line
            match = self._triple_dq.match(text, offset)
            if match.hasMatch():
                end = match.capturedStart() + 3
                self.setFormat(0, end, str_fmt)
                offset = end
                prev_state = 0
            else:
                self.setFormat(0, len(text), str_fmt)
                self.setCurrentBlockState(1)
                return
        elif prev_state == 2:
            match = self._triple_sq.match(text, offset)
            if match.hasMatch():
                end = match.capturedStart() + 3
                self.setFormat(0, end, str_fmt)
                offset = end
                prev_state = 0
            else:
                self.setFormat(0, len(text), str_fmt)
                self.setCurrentBlockState(2)
                return

        # Scan for opening triple quotes
        while offset < len(text):
            dq_match = self._triple_dq.match(text, offset)
            sq_match = self._triple_sq.match(text, offset)

            dq_start = dq_match.capturedStart() if dq_match.hasMatch() else len(text)
            sq_start = sq_match.capturedStart() if sq_match.hasMatch() else len(text)

            if dq_start >= len(text) and sq_start >= len(text):
                break

            if dq_start <= sq_start:
                # Found opening """
                close_match = self._triple_dq.match(text, dq_start + 3)
                if close_match.hasMatch():
                    end = close_match.capturedStart() + 3
                    self.setFormat(dq_start, end - dq_start, str_fmt)
                    offset = end
                else:
                    self.setFormat(dq_start, len(text) - dq_start, str_fmt)
                    self.setCurrentBlockState(1)
                    return
            else:
                close_match = self._triple_sq.match(text, sq_start + 3)
                if close_match.hasMatch():
                    end = close_match.capturedStart() + 3
                    self.setFormat(sq_start, end - sq_start, str_fmt)
                    offset = end
                else:
                    self.setFormat(sq_start, len(text) - sq_start, str_fmt)
                    self.setCurrentBlockState(2)
                    return

        self.setCurrentBlockState(0)


# ------------------------------------------------------------------
# Page 4: Scheduling Block Preview
# ------------------------------------------------------------------

class PreviewPage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Scheduling Block Preview")
        self.setSubTitle(
            "Review the generated Astrid scheduling blocks. "
            "Select a block on the left to view and edit."
        )

        self._current_label: str = ""

        # Main layout with splitter
        layout = QVBoxLayout()
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Left panel: SB list
        self._sb_list = QListWidget()
        self._splitter.addWidget(self._sb_list)

        # Right panel: editor + restore button
        right_widget = QWidget()
        right_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Restore defaults button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._restore_btn = QPushButton("Restore Defaults")
        self._restore_btn.clicked.connect(self._restore_current)
        btn_row.addWidget(self._restore_btn)
        right_layout.addLayout(btn_row)

        # Monospace text editor with syntax highlighting
        self._editor = QPlainTextEdit()
        self._editor.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        mono_font = QFont("Monospace")
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self._editor.setFont(mono_font)
        self._highlighter = _PythonHighlighter(self._editor.document())
        right_layout.addWidget(self._editor)

        self._splitter.addWidget(right_widget)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 3)

        layout.addWidget(self._splitter)
        self.setLayout(layout)

        self._sb_list.currentTextChanged.connect(self._on_sb_selected)

    # ------------------------------------------------------------------
    # Page lifecycle
    # ------------------------------------------------------------------

    def initializePage(self):
        self._generate_all_sbs()

        self._sb_list.blockSignals(True)
        self._sb_list.clear()
        for label in self.observation.generated_sbs:
            self._sb_list.addItem(label)
        self._sb_list.blockSignals(False)

        self._current_label = ""
        if self.observation.generated_sbs:
            self._sb_list.setCurrentRow(0)

    def validatePage(self):
        self._save_current_sb()
        return True

    # ------------------------------------------------------------------
    # SB switching
    # ------------------------------------------------------------------

    def _on_sb_selected(self, label: str):
        if not label:
            return
        self._save_current_sb()
        self._current_label = label
        self._load_sb(label)

    def _save_current_sb(self):
        if self._current_label and self._current_label in self.observation.generated_sbs:
            self.observation.generated_sbs[self._current_label] = (
                self._editor.toPlainText()
            )

    def _load_sb(self, label: str):
        text = self.observation.generated_sbs.get(label, "")
        self._editor.setPlainText(text)

    def _restore_current(self):
        if not self._current_label:
            return
        self._generate_all_sbs()
        self._load_sb(self._current_label)

    # ------------------------------------------------------------------
    # Helpers: source band/mode resolution
    # ------------------------------------------------------------------

    def _get_source_band(self, src: Source) -> str:
        if self.observation.per_source_config and src.freq_range:
            return src.freq_range
        return self.observation.global_freq_range

    def _get_source_mode(self, src: Source) -> ObsMode:
        if self.observation.per_source_config and src.obs_mode:
            return src.obs_mode
        return self.observation.global_obs_mode

    def _get_source_pol_cal(self, src: Source) -> bool:
        if self.observation.per_source_config:
            return src.include_pol_cal
        return self.observation.include_pol_cal

    # ------------------------------------------------------------------
    # SB generation
    # ------------------------------------------------------------------

    def _generate_all_sbs(self):
        sbs: OrderedDict[str, str] = OrderedDict()

        # Group sources by receiver
        receiver_groups: dict[str, list[Source]] = {}
        receiver_band_label: dict[str, str] = {}
        for src in self.observation.sources:
            band_label = self._get_source_band(src)
            band = FREQ_BANDS[band_label]
            rcvr = band.receiver
            receiver_groups.setdefault(rcvr, []).append(src)
            if rcvr not in receiver_band_label:
                receiver_band_label[rcvr] = band_label

        # Generate pulsar SBs
        for rcvr, sources in receiver_groups.items():
            band_label = receiver_band_label[rcvr]
            label = f"{band_label} Pulsars"
            sbs[label] = self._generate_pulsar_sb(rcvr, band_label, sources)

        # Generate flux cal SBs
        if self.observation.include_flux_cal:
            for rcvr, sources in receiver_groups.items():
                band_label = receiver_band_label[rcvr]
                label = f"{band_label} Flux Cal"
                sbs[label] = self._generate_flux_cal_sb(
                    rcvr, band_label, sources
                )

        self.observation.generated_sbs = sbs

    def _generate_pulsar_sb(
        self, receiver: str, band_label: str, sources: list[Source]
    ) -> str:
        lines: list[str] = []

        # Header
        lines.append(f"# GBT Pulsar Observation — {band_label}")
        lines.append("# Generated by PSR-SB-GUI")
        lines.append("")

        # Catalog entries grouped by coord_system
        lines.extend(self._generate_catalog_entries(sources))

        # Configuration variables
        for src in sources:
            lines.extend(self._generate_source_config(src))

        # Observation sequence
        lines.append("# === Observation Sequence ===")
        lines.append("")
        lines.append("ResetConfig()")
        first_name = sources[0].name
        lines.append(f"AutoPeakFocus(location='{first_name}')")
        lines.append("")

        for src in sources:
            safe = _safe_name(src.name)
            scan_length = int(src.scan_length) if src.scan_length else 120
            has_pol_cal = self._get_source_pol_cal(src)

            lines.append(f"# --- {src.name} ---")
            lines.append(f"Slew('{src.name}')")

            if has_pol_cal:
                lines.append(f"Configure(config_{safe}_cal)")
                lines.append("Balance()")
                lines.append(f"Track('{src.name}', None, 95)")
                lines.append(f"Configure(config_{safe})")
                lines.append(f"Track('{src.name}', None, {scan_length})")
            else:
                lines.append(f"Configure(config_{safe})")
                lines.append("Balance()")
                lines.append(f"Track('{src.name}', None, {scan_length})")

            lines.append("")

        return "\n".join(lines)

    def _generate_flux_cal_sb(
        self, receiver: str, band_label: str, sources: list[Source]
    ) -> str:
        lines: list[str] = []

        # Header
        lines.append(f"# GBT Flux Calibration — {band_label}")
        lines.append("# Generated by PSR-SB-GUI")
        lines.append("")

        # Flux cal source catalog entry
        cal_name = self.observation.flux_cal_source
        cal = _CALIBRATOR_BY_NAME.get(cal_name)
        if cal:
            ra_str = _format_ra(cal.ra_hours)
            dec_str = _format_dec(cal.dec_deg)
            lines.append('Catalog("""')
            lines.append("format=spherical")
            lines.append("coordmode=J2000")
            lines.append("HEAD = NAME    RA              DEC")
            lines.append(f"{cal_name:32s} {ra_str}  {dec_str}")
            lines.append('""")')
            lines.append("")

        # Find unique backend configs among these sources
        unique_configs = self._get_unique_flux_cal_configs(sources)

        # Generate config variables for each unique config
        for i, (config_key, src) in enumerate(unique_configs, 1):
            config_name = f"config_fluxcal_{i}"
            lines.extend(
                self._generate_config_block(
                    config_name, src, self._get_source_band(src),
                    self._get_source_mode(src), is_flux_cal=True
                )
            )

        # Observation sequence
        lines.append("# === Observation Sequence ===")
        lines.append("")
        lines.append("ResetConfig()")
        lines.append(f"AutoPeakFocus(location='{cal_name}')")
        lines.append("")
        lines.append(f"Slew('{cal_name}')")

        dur = int(self.observation.flux_cal_scan_duration)

        for i, (config_key, src) in enumerate(unique_configs, 1):
            config_name = f"config_fluxcal_{i}"
            lines.append(f"Configure({config_name})")
            lines.append("Balance()")
            lines.append(
                f"OnOff('{cal_name}', Offset('AzEl', 1.0, 0.0), {dur})"
            )
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Catalog generation
    # ------------------------------------------------------------------

    def _generate_catalog_entries(self, sources: list[Source]) -> list[str]:
        from psr_sb_gui.models.observation import CoordSystem

        lines: list[str] = []

        # Group by coord system
        by_coord: dict[CoordSystem, list[Source]] = {}
        for src in sources:
            by_coord.setdefault(src.coord_system, []).append(src)

        for coord_sys, srcs in by_coord.items():
            if coord_sys == CoordSystem.J2000:
                cat_lines = [
                    "format=spherical",
                    "coordmode=J2000",
                    "HEAD = NAME    RA              DEC",
                ]
            elif coord_sys == CoordSystem.B1950:
                cat_lines = [
                    "format=spherical",
                    "coordmode=B1950",
                    "HEAD = NAME    RA              DEC",
                ]
            else:
                cat_lines = [
                    "format=spherical",
                    "coordmode=Galactic",
                    "HEAD = NAME    GLON            GLAT",
                ]

            for src in srcs:
                cat_lines.append(
                    f"{src.name:32s} {src.coord1}  {src.coord2}"
                )

            lines.append('Catalog("""')
            lines.extend(cat_lines)
            lines.append('""")')
            lines.append("")

        return lines

    # ------------------------------------------------------------------
    # Config block generation
    # ------------------------------------------------------------------

    def _generate_source_config(self, src: Source) -> list[str]:
        """Generate config variable(s) for a single source."""
        lines: list[str] = []
        band_label = self._get_source_band(src)
        obs_mode = self._get_source_mode(src)
        safe = _safe_name(src.name)

        # Main config
        lines.extend(
            self._generate_config_block(
                f"config_{safe}", src, band_label, obs_mode
            )
        )

        # Cal config if pol cal enabled
        if self._get_source_pol_cal(src):
            lines.extend(
                self._generate_config_block(
                    f"config_{safe}_cal", src, band_label, obs_mode,
                    is_cal=True
                )
            )

        return lines

    def _generate_config_block(
        self,
        config_name: str,
        src: Source,
        band_label: str,
        obs_mode: ObsMode,
        is_cal: bool = False,
        is_flux_cal: bool = False,
    ) -> list[str]:
        """Generate a single config_xxx = \"\"\"...\"\"\" block."""
        band = FREQ_BANDS[band_label]
        p = src.vegas_params
        if p is None:
            return []

        # Center frequencies
        if p.center_freqs:
            center_freqs = p.center_freqs
        elif band.windows:
            center_freqs = list(band.windows)
        else:
            center_freqs = [band.center_freq]

        rest_freq_str = ", ".join(str(f) for f in center_freqs)
        doppler_freq = center_freqs[0]

        # Determine vegas.obsmode string
        if is_cal or is_flux_cal:
            if obs_mode.is_coherent:
                vegas_obsmode = "coherent_cal"
            else:
                vegas_obsmode = "cal"
        else:
            vegas_obsmode = obs_mode.value

        # swmode and noisecal
        if is_cal or is_flux_cal:
            swmode = "tp"
            noisecal = "lo"
        else:
            swmode = "tp_nocal"
            noisecal = "off"

        # ifbw
        ifbw = 80 if band_label == "350 MHz" else 0

        lines: list[str] = []
        lines.append(f'{config_name} = """')
        lines.append("    obstype = 'Pulsar'")
        lines.append("    backend = 'VEGAS'")
        lines.append(f"    receiver = '{band.receiver}'")
        lines.append(f"    restfreq = {rest_freq_str}")
        lines.append(f"    bandwidth = {band.bandwidth}")
        lines.append(f"    dopplertrackfreq = {doppler_freq}")
        lines.append(f"    swmode = '{swmode}'")
        lines.append(f"    noisecal = '{noisecal}'")
        lines.append("    swper = 0.04")
        lines.append(f"    tint = {p.tint}")
        lines.append(f"    ifbw = {ifbw}")

        lines.append(f"    vegas.obsmode = '{vegas_obsmode}'")
        lines.append(f"    vegas.numchan = {p.numchan}")
        lines.append(f"    vegas.outbits = {p.outbits}")
        lines.append(f"    vegas.scale = {p.scale}")
        lines.append(f"    vegas.polnmode = '{p.polnmode.lower()}'")
        lines.append("    vegas.subband = 1")

        # Fold-specific params
        if obs_mode.is_fold and not is_flux_cal:
            lines.append(f"    vegas.fold_parfile = '{src.parfile}'")
            lines.append(f"    vegas.fold_bins = {p.fold_bins}")
            lines.append(f"    vegas.fold_dumptime = {p.fold_dumptime}")

        # DM for coherent search (coherent fold reads from parfile)
        if obs_mode == ObsMode.COHERENT_SEARCH and not is_flux_cal:
            dm_val = src.dm if src.dm is not None else 0.0
            lines.append(f"    vegas.dm = {dm_val}")

        lines.append('"""')
        lines.append("")

        return lines

    # ------------------------------------------------------------------
    # Unique config detection for flux cal
    # ------------------------------------------------------------------

    def _get_unique_flux_cal_configs(
        self, sources: list[Source]
    ) -> list[tuple[tuple, Source]]:
        """Return list of (config_key, representative_source) for unique
        flux calibration configurations among the given sources.

        Uniqueness is based on receiver, observing frequencies, bandwidth,
        number of channels, and dedispersion mode (coherent vs incoherent).
        """
        seen: dict[tuple, Source] = {}
        for src in sources:
            p = src.vegas_params
            if p is None:
                continue
            obs_mode = self._get_source_mode(src)
            band_label = self._get_source_band(src)
            band = FREQ_BANDS[band_label]
            center_freqs = tuple(p.center_freqs) if p.center_freqs else ()
            key = (
                band.receiver,
                center_freqs,
                band.bandwidth,
                p.numchan,
                obs_mode.is_coherent,
            )
            if key not in seen:
                seen[key] = src
        return list(seen.items())
