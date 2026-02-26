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


@dataclass
class VegasParams:
    numchan: int = 2048
    outbits: int = 8
    scale: float = 1.0
    polnmode: str = "FULL_STOKES"
    tint: float = 10.24e-6
    fold_bins: int = 2048
    fold_dumptime: float = 10.0
    dm: float = 0.0
    fold_parfile: str = ""
    bandwidth: float = 1500.0


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
    vegas_params: VegasParams = field(default_factory=VegasParams)
    generated_sb: str = ""
    output_path: str = ""
