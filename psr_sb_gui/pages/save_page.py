from PySide6.QtWidgets import QLabel, QVBoxLayout, QWizardPage

from psr_sb_gui.models.observation import ObservationModel


class SavePage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Save")
        self.setSubTitle("Save the scheduling block to a file.")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Save options will go here."))
        self.setLayout(layout)

    def initializePage(self):
        pass

    def validatePage(self):
        return True
