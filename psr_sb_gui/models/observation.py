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
class Source:
    name: str = ""
    coord_system: CoordSystem = CoordSystem.J2000
    coord1: str = ""
    coord2: str = ""
    scan_length: Optional[float] = None
    freq_range: Optional[str] = None
    obs_mode: Optional[ObsMode] = None


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
    vegas_params: VegasParams = field(default_factory=VegasParams)
    generated_sb: str = ""
    output_path: str = ""
