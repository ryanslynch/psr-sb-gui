import math
import numpy as np
from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWizardPage,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from psr_sb_gui.models.observation import FREQ_BANDS, ObservationModel


# ---------------------------------------------------------------------------
# Flux calibrator data (from share/fluxcal.cfg)
# ---------------------------------------------------------------------------

@dataclass
class FluxCalibrator:
    name: str
    ra_hours: float    # decimal hours, J2000
    dec_deg: float     # decimal degrees, J2000
    # Format 2: log10(S_Jy) = a0 + a1*log10(f_GHz) + a2*(log10(f_GHz))^2 + ...
    coeffs: list[float] = field(default_factory=list)
    # Format 1: power-law from reference frequency
    ref_freq_mhz: float = 0.0
    ref_flux_jy: float = 0.0
    spectral_index: float = 0.0

    def flux_at_freq(self, freq_mhz: float) -> float:
        """Return flux density in Jy at the given frequency in MHz."""
        if freq_mhz <= 0:
            return 0.0
        if self.coeffs:
            log_f = math.log10(freq_mhz / 1000.0)  # convert MHz to GHz
            log_s = sum(c * log_f ** i for i, c in enumerate(self.coeffs))
            return 10.0 ** log_s
        # Format 1: power-law
        if self.ref_freq_mhz > 0 and self.ref_flux_jy > 0:
            return self.ref_flux_jy * (freq_mhz / self.ref_freq_mhz) ** self.spectral_index
        return 0.0


def _parse_ra_to_hours(ra_str: str) -> float:
    """Parse 'HH:MM:SS.SSS' to decimal hours."""
    parts = ra_str.split(":")
    h = float(parts[0])
    m = float(parts[1]) if len(parts) > 1 else 0.0
    s = float(parts[2]) if len(parts) > 2 else 0.0
    return h + m / 60.0 + s / 3600.0


def _parse_dec_to_deg(dec_str: str) -> float:
    """Parse '±DD:MM:SS.SSS' to decimal degrees."""
    sign = -1 if dec_str.startswith("-") else 1
    parts = dec_str.lstrip("+-").split(":")
    d = float(parts[0])
    m = float(parts[1]) if len(parts) > 1 else 0.0
    s = float(parts[2]) if len(parts) > 2 else 0.0
    return sign * (d + m / 60.0 + s / 3600.0)


def _format_ra(hours: float) -> str:
    """Format decimal hours as HH:MM:SS.S."""
    h = int(hours)
    remainder = (hours - h) * 60
    m = int(remainder)
    s = (remainder - m) * 60
    return f"{h:02d}:{m:02d}:{s:04.1f}"


def _format_dec(deg: float) -> str:
    """Format decimal degrees as ±DD:MM:SS.S."""
    sign = "+" if deg >= 0 else "-"
    deg = abs(deg)
    d = int(deg)
    remainder = (deg - d) * 60
    m = int(remainder)
    s = (remainder - m) * 60
    return f"{sign}{d:02d}:{m:02d}:{s:04.1f}"


# Calibrators from share/fluxcal.cfg (excluding SCP)
CALIBRATORS = [
    # Format 1
    FluxCalibrator("1413+1509",
                   _parse_ra_to_hours("14:13:41.660"),
                   _parse_dec_to_deg("+15:09:39.524"),
                   ref_freq_mhz=4850.0, ref_flux_jy=0.41, spectral_index=0.20),
    # Format 2
    FluxCalibrator("3C48",
                   _parse_ra_to_hours("01:37:41.300"),
                   _parse_dec_to_deg("+33:09:35.13"),
                   coeffs=[1.3253, -0.7553, -0.1914, 0.0498]),
    FluxCalibrator("3C123",
                   _parse_ra_to_hours("04:37:04.375"),
                   _parse_dec_to_deg("+29:40:13.82"),
                   coeffs=[1.8017, -0.7884, -0.1035, -0.0248, 0.0090]),
    FluxCalibrator("J0444-2809",
                   _parse_ra_to_hours("04:44:37.708"),
                   _parse_dec_to_deg("-28:09:54.403"),
                   coeffs=[0.9710, -0.8938, -0.1176]),
    FluxCalibrator("J0519-4546",
                   _parse_ra_to_hours("05:19:49.723"),
                   _parse_dec_to_deg("-45:46:43.855"),
                   coeffs=[1.9380, -0.7470, -0.0739]),
    FluxCalibrator("3C138",
                   _parse_ra_to_hours("05:21:09.900"),
                   _parse_dec_to_deg("+16:38:22.12"),
                   coeffs=[1.0088, -0.4981, -0.1552, -0.0102, 0.0223]),
    FluxCalibrator("3C147",
                   _parse_ra_to_hours("05:42:36.127"),
                   _parse_dec_to_deg("+49:51:07.23"),
                   coeffs=[1.4516, -0.6961, -0.2007, 0.0640, -0.0464, 0.0289]),
    FluxCalibrator("3C190",
                   _parse_ra_to_hours("08:01:33.52"),
                   _parse_dec_to_deg("+14:14:42.2"),
                   coeffs=[0.52853867, -0.93526655, -0.0181853, 0.03045624]),
    FluxCalibrator("3C196",
                   _parse_ra_to_hours("08:13:36.056"),
                   _parse_dec_to_deg("+48:13:02.64"),
                   coeffs=[1.2872, -0.8530, -0.1534, -0.0200, 0.0201]),
    FluxCalibrator("3C218",
                   _parse_ra_to_hours("09:18:05.669"),
                   _parse_dec_to_deg("-12:05:43.95"),
                   coeffs=[1.7795, -0.9176, -0.0843, -0.0139, 0.0295]),
    FluxCalibrator("3C274",
                   _parse_ra_to_hours("12:30:49.423"),
                   _parse_dec_to_deg("+12:23:28.04"),
                   coeffs=[2.4466, -0.8116, -0.0483]),
    FluxCalibrator("3C286",
                   _parse_ra_to_hours("13:31:08.284"),
                   _parse_dec_to_deg("+30:30:32.94"),
                   coeffs=[1.2481, -0.4507, -0.1798, 0.0357]),
    FluxCalibrator("3C295",
                   _parse_ra_to_hours("14:11:20.647"),
                   _parse_dec_to_deg("+52:12:09.04"),
                   coeffs=[1.4701, -0.7658, -0.2780, -0.0347, 0.0399]),
    FluxCalibrator("3C348",
                   _parse_ra_to_hours("16:51:08.024"),
                   _parse_dec_to_deg("+04:59:34.91"),
                   coeffs=[1.8298, -1.0247, -0.0951]),
    FluxCalibrator("3C353",
                   _parse_ra_to_hours("17:20:28.150"),
                   _parse_dec_to_deg("-00:58:46.80"),
                   coeffs=[1.8627, -0.6938, -0.0998, -0.0732]),
    FluxCalibrator("3C380",
                   _parse_ra_to_hours("18:29:31.781"),
                   _parse_dec_to_deg("+48:44:46.159"),
                   coeffs=[1.2320, -0.7909, 0.0947, 0.0976, -0.1794, -0.1566]),
    FluxCalibrator("3C394",
                   _parse_ra_to_hours("18:59:23.3"),
                   _parse_dec_to_deg("+12:59:12"),
                   coeffs=[0.585309, -0.843126, -0.1062818, -0.0806427]),
    FluxCalibrator("3C405",
                   _parse_ra_to_hours("19:59:28.357"),
                   _parse_dec_to_deg("+40:44:02.097"),
                   coeffs=[3.3498, -1.0022, -0.2246, 0.0227, 0.0425]),
    FluxCalibrator("3C444",
                   _parse_ra_to_hours("22:14:25.752"),
                   _parse_dec_to_deg("-17:01:36.290"),
                   coeffs=[1.1064, -1.0052, -0.0750, -0.0767]),
    FluxCalibrator("1445+0958",
                   _parse_ra_to_hours("14:45:16.440"),
                   _parse_dec_to_deg("+09:58:35.040"),
                   coeffs=[0.389314, -0.0280647, -0.600809, 0.0262127]),
    FluxCalibrator("3C43",
                   _parse_ra_to_hours("01:29:59.79"),
                   _parse_dec_to_deg("+23:38:19.4"),
                   coeffs=[0.55884, -0.732646, 0.00253868, 0.00141399]),
    FluxCalibrator("B2209+080",
                   _parse_ra_to_hours("22:12:01.5685"),
                   _parse_dec_to_deg("+08:19:15.5868"),
                   coeffs=[0.336, -0.706, 0.0]),
    FluxCalibrator("NGC7027",
                   _parse_ra_to_hours("21:07:01.530"),
                   _parse_dec_to_deg("+42:14:11.500"),
                   coeffs=[-0.19127711, 2.73384804, -2.54098431, 0.77220705]),
    FluxCalibrator("PKS1934-63",
                   _parse_ra_to_hours("19:39:25.02671"),
                   _parse_dec_to_deg("-63:42:45.6255"),
                   coeffs=[1.1704, 0.2486, -1.6497, 0.605334]),
    FluxCalibrator("PKS0408-65",
                   _parse_ra_to_hours("04:08:20.37884"),
                   _parse_dec_to_deg("-65:45:09.0806"),
                   coeffs=[1.3499, -1.0387, -0.3467, 0.0861]),
]

_CALIBRATOR_BY_NAME = {c.name: c for c in CALIBRATORS}


def _parse_sexagesimal(text: str) -> float | None:
    """Parse HH:MM:SS.SS or DD:MM:SS.SS to decimal value (hours or degrees)."""
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


def _get_observing_freq(observation: ObservationModel) -> float:
    """Return the representative observing frequency in MHz for flux display."""
    band_name = observation.global_freq_range
    band = FREQ_BANDS.get(band_name)
    if not band:
        return 1500.0  # fallback
    if band.windows:
        return sum(band.windows) / len(band.windows)
    return band.center_freq


def _angular_separation(ra1_h: float, dec1_d: float,
                        ra2_h: float, dec2_d: float) -> float:
    """Approximate angular separation in degrees between two positions.

    RA in hours, Dec in degrees.  Handles RA wraparound.
    """
    dra = ra1_h - ra2_h
    # Use shorter path around 24h circle
    if dra > 12:
        dra -= 24
    elif dra < -12:
        dra += 24
    mean_dec_rad = math.radians((dec1_d + dec2_d) / 2.0)
    dra_deg = dra * 15.0 * math.cos(mean_dec_rad)
    ddec = dec1_d - dec2_d
    return math.sqrt(dra_deg ** 2 + ddec ** 2)


def _find_nearest_calibrator(ra_h: float, dec_d: float) -> str:
    """Return name of the calibrator nearest to the given position."""
    best_name = CALIBRATORS[0].name
    best_sep = float("inf")
    for cal in CALIBRATORS:
        sep = _angular_separation(ra_h, dec_d, cal.ra_hours, cal.dec_deg)
        if sep < best_sep:
            best_sep = sep
            best_name = cal.name
    return best_name


# ---------------------------------------------------------------------------
# Page 2: Flux Calibration
# ---------------------------------------------------------------------------

class FluxCalPage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Flux Calibration")
        self.setSubTitle("Choose whether to include a flux calibration observation.")

        layout = QVBoxLayout()

        # --- Enable toggle ---
        self.enable_check = QCheckBox("Include flux calibration observation")
        self.enable_check.setToolTip(
            "Include a flux calibration observation using a known calibrator source"
        )
        self.enable_check.toggled.connect(self._toggle_settings)
        layout.addWidget(self.enable_check)

        # --- Settings group ---
        self.settings_group = QGroupBox("Flux Calibration Settings")
        settings_layout = QVBoxLayout()

        # Calibrator source combo
        cal_row = QHBoxLayout()
        cal_row.addWidget(QLabel("Calibrator Source:"))
        self.cal_combo = QComboBox()
        self.cal_combo.setToolTip("Select a standard flux calibrator source near your targets")
        for cal in CALIBRATORS:
            self.cal_combo.addItem(cal.name)
        self.cal_combo.currentTextChanged.connect(self._update_info)
        cal_row.addWidget(self.cal_combo)
        cal_row.addStretch()
        settings_layout.addLayout(cal_row)

        # Info label
        self.info_label = QLabel()
        self.info_label.setStyleSheet("color: gray; margin-left: 10px;")
        settings_layout.addWidget(self.info_label)

        # Sky plot (Aitoff projection)
        self.figure = Figure(figsize=(6, 3))
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(200)
        settings_layout.addWidget(self.canvas)

        # Label toggle checkboxes
        label_row = QHBoxLayout()
        self.show_source_labels = QCheckBox("Show source labels")
        self.show_source_labels.setToolTip("Display names next to source markers on the sky plot")
        self.show_source_labels.toggled.connect(self._update_plot)
        label_row.addWidget(self.show_source_labels)
        self.show_cal_labels = QCheckBox("Show calibrator labels")
        self.show_cal_labels.setToolTip("Display names next to calibrator markers on the sky plot")
        self.show_cal_labels.toggled.connect(self._update_plot)
        label_row.addWidget(self.show_cal_labels)
        label_row.addStretch()
        settings_layout.addLayout(label_row)

        # Scan duration
        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Scan duration (seconds):"))
        self.duration_edit = QLineEdit("95.0")
        self.duration_edit.setToolTip("Duration of each flux calibration scan in seconds")
        self.duration_edit.setFixedWidth(80)
        dur_row.addWidget(self.duration_edit)
        dur_row.addStretch()
        settings_layout.addLayout(dur_row)

        self.settings_group.setLayout(settings_layout)
        layout.addWidget(self.settings_group)

        # --- Visibility note ---
        note_label = QLabel(
            "Remember to always verify that your flux calibration source "
            "will be above the horizon during your observing session."
        )
        note_label.setStyleSheet(
            "color: #555; background-color: #f0f0f0; padding: 8px; "
            "border-radius: 4px;"
        )
        note_label.setWordWrap(True)
        layout.addWidget(note_label)

        layout.addStretch()
        self.setLayout(layout)

    def _toggle_settings(self, checked):
        self.settings_group.setEnabled(checked)

    def _get_source_equatorial_positions(self):
        """Return list of (name, ra_hours, dec_deg) for all science sources."""
        from psr_sb_gui.models.observation import CoordSystem
        positions = []
        for src in self.observation.sources:
            if src.coord_system == CoordSystem.GALACTIC:
                try:
                    l_deg = float(src.coord1)
                    b_deg = float(src.coord2)
                except ValueError:
                    continue
                from astropy.coordinates import SkyCoord
                import astropy.units as u
                sc = SkyCoord(l=l_deg * u.deg, b=b_deg * u.deg, frame="galactic")
                icrs = sc.icrs
                positions.append((src.name, icrs.ra.hour, icrs.dec.deg))
            else:
                ra_h = _parse_sexagesimal(src.coord1)
                dec_d = _parse_sexagesimal(src.coord2)
                if ra_h is not None and dec_d is not None:
                    positions.append((src.name, ra_h, dec_d))
        return positions

    def _update_plot(self):
        """Redraw the Aitoff sky plot."""
        self.figure.clear()
        ax = self.figure.add_subplot(111, projection="aitoff")
        ax.grid(True, alpha=0.3)

        selected_cal_name = self.cal_combo.currentText()

        # Plot other calibrators (gray triangles)
        other_ra = []
        other_dec = []
        other_names = []
        sel_ra = sel_dec = None
        for cal in CALIBRATORS:
            ra_rad = (cal.ra_hours * 15.0 - 180.0) * np.pi / 180.0
            dec_rad = cal.dec_deg * np.pi / 180.0
            if cal.name == selected_cal_name:
                sel_ra = ra_rad
                sel_dec = dec_rad
            else:
                other_ra.append(ra_rad)
                other_dec.append(dec_rad)
                other_names.append(cal.name)

        if other_ra:
            ax.scatter(other_ra, other_dec, marker="^", c="gray", s=30,
                       alpha=0.6, label="Calibrators", zorder=2)
        if self.show_cal_labels.isChecked():
            for name, ra, dec in zip(other_names, other_ra, other_dec):
                ax.annotate(name, (ra, dec), fontsize=6, alpha=0.6,
                            xytext=(3, 3), textcoords="offset points")

        # Plot selected calibrator (red star)
        if sel_ra is not None:
            ax.scatter([sel_ra], [sel_dec], marker="*", c="red", s=150,
                       edgecolors="darkred", linewidths=0.5,
                       label=f"Selected: {selected_cal_name}", zorder=4)
            if self.show_cal_labels.isChecked():
                ax.annotate(selected_cal_name, (sel_ra, sel_dec), fontsize=7,
                            color="red", fontweight="bold",
                            xytext=(5, 5), textcoords="offset points")

        # Plot science sources (blue circles)
        source_positions = self._get_source_equatorial_positions()
        if source_positions:
            src_ra = [(ra_h * 15.0 - 180.0) * np.pi / 180.0 for _, ra_h, _ in source_positions]
            src_dec = [dec_d * np.pi / 180.0 for _, _, dec_d in source_positions]
            src_names = [name for name, _, _ in source_positions]
            ax.scatter(src_ra, src_dec, marker="o", c="royalblue", s=40,
                       edgecolors="navy", linewidths=0.5,
                       label="Sources", zorder=3)
            if self.show_source_labels.isChecked():
                for name, ra, dec in zip(src_names, src_ra, src_dec):
                    ax.annotate(name, (ra, dec), fontsize=7, color="navy",
                                xytext=(5, 5), textcoords="offset points")

        ax.set_xlabel("RA", fontsize=8)
        ax.set_ylabel("Dec", fontsize=8)
        # Label RA ticks in hours (Aitoff x-axis runs -180° to +180°, centered on 0°)
        ra_tick_degs = np.array([-150, -120, -90, -60, -30, 0, 30, 60, 90, 120, 150])
        ra_tick_hours = ((ra_tick_degs + 180) / 15).astype(int)  # map to 0h–24h
        ax.set_xticklabels([f"{h}h" for h in ra_tick_hours], fontsize=7)
        ax.tick_params(axis="y", labelsize=7)
        ax.legend(loc="lower right", fontsize=7, framealpha=0.8)
        self.figure.tight_layout()
        self.canvas.draw()

    def _update_info(self):
        """Update the info label for the currently selected calibrator."""
        cal_name = self.cal_combo.currentText()
        cal = _CALIBRATOR_BY_NAME.get(cal_name)
        if not cal:
            self.info_label.setText("")
            return
        freq = _get_observing_freq(self.observation)
        flux = cal.flux_at_freq(freq)
        ra_str = _format_ra(cal.ra_hours)
        dec_str = _format_dec(cal.dec_deg)
        self.info_label.setText(
            f"RA: {ra_str}  |  Dec: {dec_str}  |  "
            f"S_obs: {flux:.2f} Jy at {freq:.0f} MHz"
        )
        self._update_plot()

    def _compute_mean_position(self) -> tuple[float, float]:
        """Compute mean RA (hours) and Dec (degrees) of all science sources.

        Converts galactic coordinates to equatorial using astropy.
        """
        ra_list = []
        dec_list = []
        from psr_sb_gui.models.observation import CoordSystem

        for src in self.observation.sources:
            if src.coord_system == CoordSystem.GALACTIC:
                try:
                    l_deg = float(src.coord1)
                    b_deg = float(src.coord2)
                except ValueError:
                    continue
                from astropy.coordinates import SkyCoord
                import astropy.units as u
                sc = SkyCoord(l=l_deg * u.deg, b=b_deg * u.deg, frame="galactic")
                icrs = sc.icrs
                ra_list.append(icrs.ra.hour)
                dec_list.append(icrs.dec.deg)
            else:
                # J2000 or B1950 — parse sexagesimal
                ra_h = _parse_sexagesimal(src.coord1)
                dec_d = _parse_sexagesimal(src.coord2)
                if ra_h is not None and dec_d is not None:
                    ra_list.append(ra_h)
                    dec_list.append(dec_d)

        if not ra_list:
            return 0.0, 0.0

        # Mean RA with wraparound handling via unit vectors
        sin_sum = sum(math.sin(math.radians(ra * 15)) for ra in ra_list)
        cos_sum = sum(math.cos(math.radians(ra * 15)) for ra in ra_list)
        mean_ra_deg = math.degrees(math.atan2(sin_sum, cos_sum))
        if mean_ra_deg < 0:
            mean_ra_deg += 360
        mean_ra_h = mean_ra_deg / 15.0

        mean_dec = sum(dec_list) / len(dec_list)
        return mean_ra_h, mean_dec

    # --- Page lifecycle ---

    def initializePage(self):
        """Populate UI from model."""
        # Enable checkbox
        self.enable_check.setChecked(self.observation.include_flux_cal)
        self.settings_group.setEnabled(self.observation.include_flux_cal)

        # Calibrator selection
        if (self.observation.flux_cal_source
                and self.cal_combo.findText(self.observation.flux_cal_source) >= 0):
            self.cal_combo.setCurrentText(self.observation.flux_cal_source)
        else:
            # Compute nearest calibrator to mean source position
            mean_ra, mean_dec = self._compute_mean_position()
            nearest = _find_nearest_calibrator(mean_ra, mean_dec)
            self.cal_combo.setCurrentText(nearest)

        # Scan duration
        self.duration_edit.setText(str(self.observation.flux_cal_scan_duration))

        # Update info label
        self._update_info()

    def validatePage(self):
        """Validate and save to model."""
        self.observation.include_flux_cal = self.enable_check.isChecked()

        if self.enable_check.isChecked():
            self.observation.flux_cal_source = self.cal_combo.currentText()

            # Validate scan duration
            dur_text = self.duration_edit.text().strip()
            try:
                dur = float(dur_text)
            except ValueError:
                QMessageBox.warning(
                    self, "Validation Error",
                    "Scan duration must be a number."
                )
                return False
            if dur <= 0:
                QMessageBox.warning(
                    self, "Validation Error",
                    "Scan duration must be greater than zero."
                )
                return False
            self.observation.flux_cal_scan_duration = dur
        else:
            self.observation.flux_cal_source = ""
            self.observation.flux_cal_scan_duration = 95.0

        return True
