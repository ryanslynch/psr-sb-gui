import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CoordSystem(Enum):
    J2000 = "J2000"
    B1950 = "B1950"
    GALACTIC = "Galactic"


class ObsMode(Enum):
    COHERENT_FOLD = "coherent_fold"
    COHERENT_SEARCH = "coherent_search"
    FOLD = "fold"
    SEARCH = "search"

    @property
    def is_coherent(self) -> bool:
        return self in (ObsMode.COHERENT_FOLD, ObsMode.COHERENT_SEARCH)

    @property
    def is_fold(self) -> bool:
        return self in (ObsMode.COHERENT_FOLD, ObsMode.FOLD)

    @property
    def display_label(self) -> str:
        labels = {
            ObsMode.COHERENT_FOLD: "Coherent Fold",
            ObsMode.COHERENT_SEARCH: "Coherent Search",
            ObsMode.FOLD: "Incoherent Fold",
            ObsMode.SEARCH: "Incoherent Search",
        }
        return labels[self]


@dataclass
class FreqBand:
    label: str
    receiver: str
    bandwidth: float  # MHz per window
    windows: list[float] = field(default_factory=list)  # center freqs in MHz
    center_freq: Optional[float] = None  # MHz, for single-window bands

    @property
    def description(self) -> str:
        if self.windows:
            win_str = ", ".join(f"{w} MHz" for w in self.windows)
            return (f"{self.receiver}  |  {len(self.windows)} windows "
                    f"@ {win_str}  |  {self.bandwidth} MHz BW each")
        return (f"{self.receiver}  |  {self.center_freq} MHz  "
                f"|  {self.bandwidth} MHz BW")


FREQ_BANDS: dict[str, FreqBand] = {
    "350 MHz": FreqBand("350 MHz", "Rcvr_342", 100, center_freq=350),
    "820 MHz": FreqBand("820 MHz", "Rcvr_800", 200, center_freq=820),
    "L-band": FreqBand("L-band", "Rcvr1_2", 800, center_freq=1500),
    "S-band": FreqBand("S-band", "Rcvr2_3", 1500, center_freq=2165),
    "UWBR": FreqBand("UWBR", "Rcvr_2500", 1500, windows=[1225, 2350, 3475]),
    "C-band": FreqBand("C-band", "Rcvr4_6", 1500,
                        windows=[4312.5, 5437.5, 6562.5, 7687.5]),
    "X-band": FreqBand("X-band", "Rcvr8_10", 1500,
                        windows=[8250, 9375, 10500, 11625]),
}

FREQ_BAND_NAMES = list(FREQ_BANDS.keys())


# ---------------------------------------------------------------------------
# Scale lookup tables from VPM documentation
# Keys: (bandwidth_mhz, numchan) -> scale
# ---------------------------------------------------------------------------

COHERENT_SCALE: dict[tuple[int, int], int] = {
    # 100 MHz bandwidth
    (100, 64): 820,
    (100, 128): 595,
    (100, 256): 1650,
    (100, 512): 2355,
    # 200 MHz bandwidth
    (200, 64): 605,
    (200, 128): 865,
    (200, 256): 620,
    (200, 512): 1720,
    (200, 1024): 2430,
    # 800 MHz bandwidth
    (800, 32): 375,
    (800, 64): 420,
    (800, 128): 800,
    (800, 256): 940,
    (800, 512): 1585,
    (800, 1024): 880,
    (800, 2048): 3155,
    (800, 4096): 4550,
    # 1500 MHz bandwidth
    (1500, 32): 365,
    (1500, 64): 530,
    (1500, 128): 730,
    (1500, 256): 1070,
    (1500, 512): 1450,
    (1500, 1024): 1085,
    (1500, 2048): 300,
    (1500, 4096): 3750,
}

INCOHERENT_SCALE: dict[tuple[int, int], int] = {
    # 100 MHz bandwidth
    (100, 512): 1875,
    (100, 1024): 4010,
    (100, 2048): 550,
    (100, 4096): 990,
    (100, 8192): 580,
    # 200 MHz bandwidth
    (200, 1024): 1920,
    (200, 2048): 1030,
    (200, 4096): 540,
    (200, 8192): 1045,
    # 800 MHz bandwidth
    (800, 32): 14830,
    (800, 64): 7240,
    (800, 128): 14690,
    (800, 256): 7340,
    (800, 512): 15320,
    (800, 1024): 7495,
    (800, 2048): 14300,
    (800, 4096): 7545,
    (800, 8192): 14725,
    # 1500 MHz bandwidth
    (1500, 32): 14675,
    (1500, 64): 6835,
    (1500, 128): 13485,
    (1500, 256): 6750,
    (1500, 512): 13345,
    (1500, 1024): 6655,
    (1500, 2048): 13035,
    (1500, 4096): 6595,
}


def get_valid_numchan_values(bandwidth_mhz: int, is_coherent: bool) -> list[int]:
    """Return sorted list of valid numchan values for a bandwidth/mode combo."""
    table = COHERENT_SCALE if is_coherent else INCOHERENT_SCALE
    return sorted(nc for (bw, nc) in table if bw == bandwidth_mhz)


def get_recommended_scale(bandwidth_mhz: int, numchan: int,
                          is_coherent: bool) -> int:
    """Look up the recommended scale factor from the VPM tables."""
    table = COHERENT_SCALE if is_coherent else INCOHERENT_SCALE
    return table[(bandwidth_mhz, numchan)]


def compute_tint(acclen: int, numchan: int, bandwidth_mhz: float) -> float:
    """Compute integration time in seconds: tint = acclen * numchan / (BW_Hz)."""
    return acclen * numchan / (bandwidth_mhz * 1e6)


def get_valid_acclen_values(is_coherent: bool) -> list[int]:
    """Return sorted list of valid acclen values (powers of 2)."""
    if is_coherent:
        return [4, 8, 16]
    return [2**i for i in range(11)]  # 1 .. 1024


def _nearest_power_of_2(x: float) -> int:
    """Return the power of 2 nearest to x (minimum 1)."""
    if x <= 1:
        return 1
    log2 = math.log2(x)
    low = 2 ** int(math.floor(log2))
    high = 2 ** int(math.ceil(log2))
    return low if abs(x - low) <= abs(x - high) else high


def get_default_vegas_params(band_label: str, obs_mode: ObsMode) -> "VegasParams":
    """Compute default VegasParams for a (band, mode) combination."""
    band = FREQ_BANDS[band_label]
    bw = int(band.bandwidth)
    is_coherent = obs_mode.is_coherent
    is_fold = obs_mode.is_fold

    # Default numchan
    if is_coherent:
        # ~1.5 MHz channels: nearest power-of-2 to bandwidth / 1.5
        numchan = _nearest_power_of_2(bw / 1.5)
        valid = get_valid_numchan_values(bw, True)
        if numchan not in valid:
            # Pick closest valid value
            numchan = min(valid, key=lambda v: abs(v - numchan))
    else:
        numchan = 4096
        valid = get_valid_numchan_values(bw, False)
        if numchan not in valid:
            numchan = max(valid)

    # Default tint via acclen
    if is_coherent:
        # Use maximum allowed acclen = 16
        acclen = 16
    else:
        # Find acclen closest to 80 µs target
        target_acclen = 80e-6 * bw * 1e6 / numchan
        acclen = _nearest_power_of_2(target_acclen)
        acclen = max(1, min(acclen, 1024))  # clamp to valid range

    tint = compute_tint(acclen, numchan, bw)

    # Scale from table
    scale = get_recommended_scale(bw, numchan, is_coherent)

    # Polarization mode
    if obs_mode == ObsMode.SEARCH:
        polnmode = "TOTAL_INTENSITY"
    else:
        polnmode = "FULL_STOKES"

    # Fold parameters
    if is_fold:
        fold_bins = 2048 if is_coherent else 256
        fold_dumptime = 10.0
    else:
        fold_bins = 2048
        fold_dumptime = 10.0

    # Center frequencies from band definition
    if band.windows:
        center_freqs = list(band.windows)
    else:
        center_freqs = [band.center_freq]

    return VegasParams(
        numchan=numchan,
        outbits=8,
        scale=scale,
        polnmode=polnmode,
        tint=tint,
        fold_bins=fold_bins,
        fold_dumptime=fold_dumptime,
        center_freqs=center_freqs,
        _band_label=band_label,
        _obs_mode_value=obs_mode.value,
    )


POLN_DISPLAY = {"FULL_STOKES": "Full Stokes", "TOTAL_INTENSITY": "Total Intensity"}
POLN_INTERNAL = {"Full Stokes": "FULL_STOKES", "Total Intensity": "TOTAL_INTENSITY"}


@dataclass
class Source:
    name: str = ""
    coord_system: CoordSystem = CoordSystem.J2000
    coord1: str = ""
    coord2: str = ""
    scan_length: Optional[float] = None
    freq_range: Optional[str] = None
    obs_mode: Optional[ObsMode] = None
    parfile: str = ""
    dm: Optional[float] = None
    include_pol_cal: bool = False
    vegas_params: Optional["VegasParams"] = None


@dataclass
class VegasParams:
    numchan: int = 512
    outbits: int = 8
    scale: int = 1585
    polnmode: str = "FULL_STOKES"
    tint: float = 10.24e-6
    fold_bins: int = 2048
    fold_dumptime: float = 10.0
    center_freqs: list[float] = field(default_factory=list)  # per-window center freqs (MHz)
    # Track what band/mode these defaults were generated for
    _band_label: str = ""
    _obs_mode_value: str = ""


@dataclass
class ObservationModel:
    sources: list[Source] = field(default_factory=list)
    global_freq_range: str = "L-band"
    global_obs_mode: ObsMode = ObsMode.COHERENT_FOLD
    per_source_config: bool = False
    include_pol_cal: bool = False
    include_flux_cal: bool = False
    flux_cal_source: str = ""
    flux_cal_scan_duration: float = 95.0
    generated_sbs: dict[str, str] = field(default_factory=dict)
    output_path: str = ""
