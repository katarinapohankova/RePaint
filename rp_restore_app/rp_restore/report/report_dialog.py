from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QPlainTextEdit, QVBoxLayout

from rp_restore.report.pdf_report import ReportMetadata


class ReportDialog(QDialog):
    """dialóg na zadanie voliteľných údajov pred vytvorením PDF reportu"""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Vytvořit report")
        self.resize(520, 420)

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.restorer_edit = QLineEdit(self)
        self.restorer_edit.setPlaceholderText("volitelné")
        form.addRow("Restaurátor:", self.restorer_edit)

        self.artwork_title_edit = QLineEdit(self)
        self.artwork_title_edit.setPlaceholderText("volitelné")
        form.addRow("Název díla:", self.artwork_title_edit)

        self.artwork_author_edit = QLineEdit(self)
        self.artwork_author_edit.setPlaceholderText("volitelné")
        form.addRow("Autor díla:", self.artwork_author_edit)

        layout.addLayout(form)

        self.notes_edit = QPlainTextEdit(self)
        self.notes_edit.setPlaceholderText("Volitelné poznámky...")
        layout.addWidget(self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText("Vytvořit report")
        buttons.button(QDialogButtonBox.Cancel).setText("Zrušit")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def metadata(self) -> ReportMetadata:
        """Vráti voliteľné údaje zadané používateľom."""
        return ReportMetadata(
            restorer_name=self.restorer_edit.text().strip(),
            artwork_title=self.artwork_title_edit.text().strip(),
            artwork_author=self.artwork_author_edit.text().strip(),
            user_notes=self.notes_edit.toPlainText().strip(),
        )