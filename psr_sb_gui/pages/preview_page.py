from PySide6.QtWidgets import QLabel, QVBoxLayout, QWizardPage

from psr_sb_gui.models.observation import ObservationModel


class PreviewPage(QWizardPage):
    def __init__(self, observation: ObservationModel, parent=None):
        super().__init__(parent)
        self.observation = observation
        self.setTitle("Scheduling Block Preview")
        self.setSubTitle("Review the generated Astrid scheduling block.")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Scheduling block preview will go here."))
        self.setLayout(layout)

    def initializePage(self):
        pass

    def validatePage(self):
        return True
