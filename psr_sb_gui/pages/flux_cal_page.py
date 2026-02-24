from PySide6.QtWidgets import QLabel, QVBoxLayout, QWizardPage

from psr_sb_gui.models.observation import ObservationModel


class FluxCalPage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Flux Calibration")
        self.setSubTitle("Choose whether to include a flux calibration observation.")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Flux calibration options will go here."))
        self.setLayout(layout)

    def initializePage(self):
        pass

    def validatePage(self):
        return True
