from __future__ import annotations

import os
from dataclasses import dataclass


SERVICE_NAME = "RP-Restore"
ENDPOINT_USERNAME = "modal_endpoint_url"
API_KEY_USERNAME = "modal_restoration_api_key"

#endpoint nie je tajný údaj, preto môže byť predvyplnený v aplikácii
#ak sa endpoint zmení, používateľ ho vie upraviť v nastaveniach
DEFAULT_ENDPOINT_URL = "https://danideos-kaiser--painting-inpaint-backend-modal-restoration-api.modal.run/v1/restore/stream"


class RemoteRestorationConfigError(RuntimeError):
    """Chyba pri načítaní alebo ukladaní nastavení remote služby"""


@dataclass
class RemoteRestorationConfig:
    """Lokálne nastavenie prístupu k remote realistickému doplneniu"""

    endpoint_url: str
    api_key: str

    def is_complete(self) -> bool:
        """Vráti True, ak sú vyplnené všetky údaje potrebné pre remote službu"""
        return bool(self.endpoint_url.strip()) and bool(self.api_key.strip())


def _get_keyring():
    """
    Načíta keyring až pri použití

    Vďaka tomu sa zvyšok aplikácie dá spustiť aj v prípade,
    že balíček keyring chýba. Chyba sa zobrazí až pri nastavovaní
    alebo použití remote realistického doplnenia.
    """
    try:
        import keyring
    except ImportError as e:
        raise RemoteRestorationConfigError(
            "Balíček keyring není nainstalovaný. "
        ) from e

    return keyring


def load_remote_restoration_config() -> RemoteRestorationConfig:
    """
    Načíta endpoint a API key zo systémového úložiska používateľa

    API key sa neukladá do súboru projektu ani do settings.json.
    """
    keyring = _get_keyring()

    try:
        endpoint_url = (keyring.get_password(SERVICE_NAME, ENDPOINT_USERNAME) or DEFAULT_ENDPOINT_URL).strip()
        api_key = (keyring.get_password(SERVICE_NAME, API_KEY_USERNAME) or "").strip()
    except Exception as e:
        raise RemoteRestorationConfigError(f"Nepodařilo se načíst nastavení remote služby: {e}") from e

    if not endpoint_url:
        endpoint_url = DEFAULT_ENDPOINT_URL

    return RemoteRestorationConfig(endpoint_url=endpoint_url, api_key=api_key)


def save_remote_restoration_config(endpoint_url: str, api_key: str) -> None:
    """
    Uloží endpoint a API key do systémového úložiska používateľa

    API key sa neukladá do obyčajného textového súboru.
    """
    endpoint_url = endpoint_url.strip()
    api_key = api_key.strip()

    if not endpoint_url:
        raise RemoteRestorationConfigError("Endpoint URL nesmí být prázdná")

    if not api_key:
        raise RemoteRestorationConfigError("API key nesmí být prázdný")

    keyring = _get_keyring()

    try:
        keyring.set_password(SERVICE_NAME, ENDPOINT_USERNAME, endpoint_url)
        keyring.set_password(SERVICE_NAME, API_KEY_USERNAME, api_key)
    except Exception as e:
        raise RemoteRestorationConfigError(f"Nepodařilo se uložit nastavení remote služby: {e}") from e


def _delete_password_if_exists(username: str) -> None:
    """Bezpečne zmaže jednu položku z keyringu, ak existuje"""
    keyring = _get_keyring()

    try:
        keyring.delete_password(SERVICE_NAME, username)
    except Exception:
        pass


def clear_remote_restoration_config() -> None:
    """Odstráni uložené údaje pre remote realistické doplnenie"""
    _delete_password_if_exists(ENDPOINT_USERNAME)
    _delete_password_if_exists(API_KEY_USERNAME)

    #odstránime aj hodnoty nastavené pre aktuálne bežiaci proces aplikácie
    os.environ.pop("MODAL_ENDPOINT_URL", None)
    os.environ.pop("MODAL_RESTORATION_API_KEY", None)


def has_remote_restoration_config() -> bool:
    """Vráti True, ak sú uložené všetky údaje potrebné pre remote službu"""
    try:
        return load_remote_restoration_config().is_complete()
    except RemoteRestorationConfigError:
        return False


def apply_remote_restoration_environment() -> None:
    """
    Nastaví premenné prostredia iba pre aktuálne bežiaci proces aplikácie

    Remote klient zatiaľ používa RestorationClient.from_env(provider="modal"),
    preto mu údaje odovzdáme týmto spôsobom. Nenastavujeme ich však natrvalo
    vo Windows
    """
    config = load_remote_restoration_config()

    if not config.is_complete():
        raise RemoteRestorationConfigError("Chybí endpoint URL nebo API key pro remote službu")

    os.environ["MODAL_ENDPOINT_URL"] = config.endpoint_url
    os.environ["MODAL_RESTORATION_API_KEY"] = config.api_key