# psr-sb-gui

**THIS TOOL IS IN DEVELOPMENT AND SHOULD NOT YET BE USED BY OBSERVERS TO CREATE ASTRID SCHEDULING BLOCKS**

A wizard-style GUI for generating [Green Bank Telescope](https://greenbankobservatory.org/science/gbt/) (GBT) pulsar scheduling blocks. It guides observers through the process of specifying sources, frequency bands, observing modes, and calibration settings, then produces ready-to-use [Astrid](https://gbtdocs.readthedocs.io/en/latest/references/astrid.html) scheduling blocks.

## Features

- **Source entry** -- Add sources manually, import from GBT/Astrid catalog files, or look up pulsar coordinates from the [ATNF Pulsar Catalogue](https://www.atnf.csiro.au/research/pulsar/psrcat/)
- **Frequency & mode selection** -- Choose from standard GBT receiver bands (350 MHz through X-band) and observing modes (fold/search with optional coherent dedispersion), globally or per-source
- **Flux calibration** -- Select from 25 standard calibrators with an interactive Aitoff sky plot showing source and calibrator positions; auto-selects the nearest calibrator
- **Backend parameters** -- Review and customize VEGAS pulsar mode parameters with sensible defaults
- **Scheduling block preview** -- View and edit the generated Astrid scheduling block before saving
- **Save** -- Export scheduling blocks to files

## Requirements

- Python 3.10+
- A working display (X11, Wayland, or macOS) for the Qt GUI

## Installation

```bash
git clone https://github.com/your-username/psr-sb-gui.git
cd psr-sb-gui
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

## Usage

After installation, run:

```bash
psr-sb-gui
```

Or run as a module:

```bash
python -m psr_sb_gui
```

The wizard will guide you through the following steps:

1. **Sources** -- Enter source names, coordinates (J2000, B1950, or Galactic), and scan lengths. Use "Lookup Coordinates" to query the ATNF catalog.
2. **Frequency & Observing Mode** -- Select the receiver band and mode (Fold or Search). Optionally configure per-source settings.
3. **Flux Calibration** -- Optionally include a flux calibration scan. The sky plot helps visualize source and calibrator positions.
4. **Backend Parameters** -- Review default VEGAS parameters and adjust if needed.
5. **Preview** -- Review the generated Astrid scheduling block.
6. **Save** -- Save the scheduling block to a file.

## Project Structure

```
psr-sb-gui/
  pyproject.toml            # Package metadata and dependencies
  requirements.txt          # pip requirements
  psr_sb_gui/
    __init__.py
    __main__.py             # python -m entry point
    app.py                  # QApplication setup
    wizard.py               # Main QWizard with page routing
    models/
      observation.py        # Data model (sources, bands, parameters)
    pages/
      source_page.py        # Page 0: Source entry
      freq_mode_page.py     # Page 1: Frequency & mode selection
      flux_cal_page.py      # Page 2: Flux calibration
      params_page.py        # Page 3: Backend parameters
      preview_page.py       # Page 4: SB preview
      save_page.py          # Page 5: Save
```

## License

BSD 3-Clause. See [LICENSE](LICENSE) for details.
