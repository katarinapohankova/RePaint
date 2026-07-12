from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from rp_restore.core.remote_restoration_config import RemoteRestorationConfigError, clear_remote_restoration_config, load_remote_restoration_config, save_remote_restoration_config


class RemoteRestorationSettingsDialog(QDialog):
    """
    Dialóg pre nastavenie prístupu k remote realistickému doplneniu

    API kľúč sa po uložení uloží do systémového úložiska používateľa cez keyring,
    nie do projektu ani do bežného konfiguračného súboru
    """

    def __init__(self, parent=None, require_complete: bool = False, message: str | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Nastavení remote realistického doplnění")

        layout = QVBoxLayout(self)

        if message is not None:
            info = QLabel(message)
        elif require_complete:
            info = QLabel(
                "Pro použití realistického doplnění je potřeba nastavit "
                "endpoint URL a API klíč remote služby."
            )
        else:
            info = QLabel("Zde můžete nastavit přístupové údaje pro remote realistické doplnění.")

        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()

        self.endpoint_edit = QLineEdit()
        self.endpoint_edit.setPlaceholderText("https://...modal.run/v1/restore/stream")
        form.addRow("Endpoint URL:", self.endpoint_edit)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("API klíč")
        form.addRow("API klíč:", self.api_key_edit)

        layout.addLayout(form)

        self.show_key_checkbox = QCheckBox("Zobrazit API klíč")
        self.show_key_checkbox.toggled.connect(self._on_show_key_toggled)
        layout.addWidget(self.show_key_checkbox)

        warning = QLabel(
            "API klíč se ukládá lokálně do systémového úložiště uživatele. "
            "Neukládá se do projektu ani do exportovaných souborů."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("Uložit")
        self.buttons.button(QDialogButtonBox.Cancel).setText("Zrušit")

        self.clear_button = QPushButton("Odstranit uložené údaje")
        self.buttons.addButton(self.clear_button, QDialogButtonBox.ActionRole)

        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.clear_button.clicked.connect(self._on_clear_clicked)

        self._load_existing_values()

    def _load_existing_values(self) -> None:
        """Predvyplní dialóg aktuálne uloženými hodnotami"""
        try:
            config = load_remote_restoration_config()
        except RemoteRestorationConfigError as e:
            QMessageBox.warning(self, "Nastavení remote služby", str(e))
            return

        self.endpoint_edit.setText(config.endpoint_url)
        self.api_key_edit.setText(config.api_key)

    def _on_show_key_toggled(self, checked: bool) -> None:
        """Prepne zobrazenie alebo skrytie API kľúča"""
        if checked:
            self.api_key_edit.setEchoMode(QLineEdit.Normal)
        else:
            self.api_key_edit.setEchoMode(QLineEdit.Password)

    def _on_clear_clicked(self) -> None:
        """Odstráni uložené údaje z keyringu"""
        reply = QMessageBox.question(
            self,
            "Odstranit uložené údaje",
            "Opravdu chcete odstranit uložený endpoint URL a API klíč?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        try:
            clear_remote_restoration_config()
        except RemoteRestorationConfigError as e:
            QMessageBox.warning(self, "Nastavení remote služby", str(e))
            return

        self.endpoint_edit.clear()
        self.api_key_edit.clear()

        QMessageBox.information(
            self,
            "Nastavení remote služby",
            "Uložené údaje byly odstraněny.",
        )

    def accept(self) -> None:
        """Skontroluje a uloží nastavenia remote služby"""
        endpoint_url = self.endpoint_edit.text().strip()
        api_key = self.api_key_edit.text().strip()

        if not endpoint_url:
            QMessageBox.warning(self, "Nastavení remote služby", "Endpoint URL nesmí být prázdná.")
            return

        if not api_key:
            QMessageBox.warning(self, "Nastavení remote služby", "API klíč nesmí být prázdný.")
            return

        try:
            save_remote_restoration_config(endpoint_url, api_key)
        except RemoteRestorationConfigError as e:
            QMessageBox.warning(self, "Nastavení remote služby", str(e))
            return

        super().accept()