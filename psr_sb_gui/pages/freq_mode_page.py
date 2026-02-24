from PySide6.QtWidgets import QLabel, QVBoxLayout, QWizardPage

from psr_sb_gui.models.observation import ObservationModel


class FreqModePage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Frequency & Observing Mode")
        self.setSubTitle("Select the radio frequency range and observing mode.")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Frequency and mode selection widgets will go here."))
        self.setLayout(layout)

    def initializePage(self):
        pass

    def validatePage(self):
        return True
