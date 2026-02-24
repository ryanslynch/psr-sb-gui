import sys

from PySide6.QtWidgets import QApplication

from psr_sb_gui.wizard import PulsarObsWizard


def main():
    app = QApplication(sys.argv)
    wizard = PulsarObsWizard()
    wizard.show()
    sys.exit(app.exec())
