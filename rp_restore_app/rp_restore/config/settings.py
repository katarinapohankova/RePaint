from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar


@dataclass
class AppSettings:
    """
    Uchováva nastavenia aplikácie uložené mimo projektu
    """

    #súbor s nastaveniami je uložený v domovskom priečinku používateľa
    SETTINGS_DIR: ClassVar[Path] = Path.home() / ".rp_restore"
    SETTINGS_FILE: ClassVar[Path] = SETTINGS_DIR / "settings.json"

    recent_projects: list[str] = field(default_factory=list)

    @classmethod
    def load_default(cls) -> "AppSettings":
        """
        Načíta nastavenia zo súboru alebo vráti prázdne nastavenia
        """
        try:
            settings_file = cls.SETTINGS_FILE
            if settings_file.is_file():
                raw = settings_file.read_text(encoding="utf-8")
                data = json.loads(raw)
                return cls(recent_projects=data.get("recent_projects", []))
        except Exception:
            #ak sa niečo pokazí, použijeme default
            pass
        return cls()
    
    def save(self) -> None:
        """Uloží nastavenia do JSON súboru"""
        try:
            self.SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "recent_projects": self.recent_projects,
            }
            self.SETTINGS_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            #chyba uloženia nesmie zhodiť celú aplikáciu
            pass

    def add_recent_project(self, path: str) -> None:
        """Pridá projekt na začiatok zoznamu naposledy otvorených projektov"""
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        #limit na 10 položiek
        self.recent_projects = self.recent_projects[:10]

        self.save()

    def get_recent_projects(self) -> list[str]:
        """Vráti kópiu zoznamu naposledy otvorených projektov"""
        return list(self.recent_projects)
    