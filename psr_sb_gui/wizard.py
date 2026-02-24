from PySide6.QtWidgets import QWizard

from psr_sb_gui.models.observation import ObservationModel
from psr_sb_gui.pages.source_page import SourcePage
from psr_sb_gui.pages.freq_mode_page import FreqModePage
from psr_sb_gui.pages.flux_cal_page import FluxCalPage
from psr_sb_gui.pages.params_page import ParamsPage
from psr_sb_gui.pages.preview_page import PreviewPage
from psr_sb_gui.pages.save_page import SavePage

PAGE_SOURCE = 0
PAGE_FREQ_MODE = 1
PAGE_FLUX_CAL = 2
PAGE_PARAMS = 3
PAGE_PREVIEW = 4
PAGE_SAVE = 5


class PulsarObsWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.observation = ObservationModel()

        self.setWindowTitle("GBT Pulsar Observation Setup")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self.setPage(PAGE_SOURCE, SourcePage(self.observation, self))
        self.setPage(PAGE_FREQ_MODE, FreqModePage(self.observation, self))
        self.setPage(PAGE_FLUX_CAL, FluxCalPage(self.observation, self))
        self.setPage(PAGE_PARAMS, ParamsPage(self.observation, self))
        self.setPage(PAGE_PREVIEW, PreviewPage(self.observation, self))
        self.setPage(PAGE_SAVE, SavePage(self.observation, self))
