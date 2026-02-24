from PySide6.QtWidgets import QLabel, QVBoxLayout, QWizardPage

from psr_sb_gui.models.observation import ObservationModel


class ParamsPage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Backend Parameters")
        self.setSubTitle("Review and adjust VEGAS backend parameters.")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Backend parameter widgets will go here."))
        self.setLayout(layout)

    def initializePage(self):
        pass

    def validatePage(self):
        return True
