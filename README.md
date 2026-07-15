# RePaint

RePaint je aplikácia určená na digitálne dopĺňanie poškodených častí obrazov. Umožňuje pracovať s pôvodným obrazom, maskou poškodenia, viacerými vrstvami, ručnými nástrojmi a externými algoritmami na dopĺňanie chýbajúcich miest.

Aplikácia vznikla ako súčasť bakalárskej práce v spolupráci s Národnou galériou v Prahe a je určená najmä na prípravu a porovnávanie návrhov reštaurátorského zásahu.

## Funkcie aplikácie

Aplikácia podporuje najmä:

* vytvorenie projektu z obrazu a masky poškodenia
* zarovnanie masky poškodenia pomocou zodpovedajúcich bodov
* prácu s vrstvami
* ručné dopĺňanie farbou alebo textúrou
* výplň poškodených regiónov
* výber poškodených oblastí kliknutím alebo lasom
* kreslenie hrán na rozdelenie poškodenia na menšie regióny
* zjemnenie prechodu medzi vyplnenými regiónmi
* rozmazanie doplnených častí
* automatickú výplň malých poškodených oblastí
* ColorChecker korekciu
* externé realistické a textúrové dopĺňanie
* Undo/Redo
* uloženie a otvorenie projektu vo formáte `.zip`
* export výsledného obrazu
* export PDF reportu

## Štruktúra projektu

Základná štruktúra repozitára:

```
.
├── docs/
│   ├── user_documentation.md
│   └── developer_documentation.md
├── rp_restore_app/
│   ├── app.py
│   ├── RePaint.spec
│   ├── requirements.txt
│   ├── requirements-lock.txt
│   ├── packaging/
│   │   ├── RePaint.ico
│   │   ├── RePaint.iss
│   │   └── version_info.txt
│   └── rp_restore/
│       ├── config/
│       ├── core/
│       ├── gui/
│       ├── io/
│       ├── report/
│       ├── resources/
│       └── utils/
├── COPYRIGHT.md
└── README.md
```

Priečinok `rp_restore_app` obsahuje samotnú aplikáciu. Hlavný balík aplikácie je `rp_restore`.

Priečinok `docs` obsahuje dokumentáciu:

* `user_documentation.md` – užívateľská dokumentácia
* `developer_documentation.md` – programátorská dokumentácia

## Inštalácia a spustenie

Aplikáciu je možné používať dvoma spôsobmi: nainštalovať ju pomocou pripraveného inštalátora alebo ju spustiť priamo zo zdrojového kódu.

### Inštalácia pomocou inštalátora

Pre bežné používanie je určený súbor:

```text
RePaint-Setup-1.0.1.exe
```

Inštalátor je určený pre 64-bitový operačný systém Windows. Po jeho spustení sa aplikácia nainštaluje do používateľského priečinka, vytvorí sa odkaz v ponuke Štart a voliteľne aj odkaz na pracovnej ploche.

Táto verzia už obsahuje Python, potrebné knižnice aj lokálny textúrový algoritmus. Na cieľovom počítači preto nie je potrebné samostatne inštalovať Python, Git ani ďalšie závislosti.

Realistické dopĺňanie používa vzdialenú službu. Vyžaduje internetové pripojenie a platný API kľúč, ktorý sa zadáva pri prvom použití a následne sa ukladá do systémového úložiska prihlasovacích údajov.

### Spustenie zo zdrojového kódu

Na spustenie zo zdrojov je potrebný Python 3.13 a Git. Repozitár sa naklonuje a následne sa prejde do priečinka aplikácie:

```powershell
git clone https://gitlab.mff.cuni.cz/teaching/nprg045/ikudov/pohankova-katarina.git
cd pohankova-katarina\rp_restore_app
```

Vytvorí a aktivuje sa virtuálne prostredie:

```powershell
python3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Po aktivovaní prostredia sa závislosti inštalujú prostredníctvom interpretra `python` z daného virtuálneho prostredia:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Aplikácia sa spustí príkazom:

```powershell
python app.py
```

Inštalácia zo zdrojového kódu môže vyžadovať oprávnenie na prístup k repozitárom externých balíkov uvedených v súbore `requirements.txt`.

## Použitie

Po spustení aplikácie je možné vytvoriť nový projekt alebo otvoriť už existujúci projekt.

Nový projekt sa vytvára z pôvodného obrazu. Voliteľne je možné pridať aj masku poškodenia, ktorá určuje oblasti určené na dopĺňanie. Ak je maska pridaná, aplikácia umožní jej zarovnanie s obrazom pomocou zodpovedajúcich bodov.

Podrobnejší opis práce s aplikáciou je uvedený v užívateľskej dokumentácii:

```
docs/user_documentation.md
```

## Vývojárska dokumentácia

Stručný opis vnútornej štruktúry aplikácie, hlavných modulov, dátového modelu a nástrojov je uvedený v programátorskej dokumentácii:

```
docs/developer_documentation.md
```

## Ukladanie projektov

Projekt sa ukladá ako `.zip` súbor. Tento súbor obsahuje najmä:

* metadata projektu
* pôvodný obraz
* vrstvy
* masky
* paletu
* textúry
* nastavenia potrebné na pokračovanie práce

Uložený projekt je možné neskôr znovu otvoriť v aplikácii a pokračovať v úpravách.

## Externé algoritmy

Aplikácia podporuje dva externé algoritmy:

* **realistické dopĺňanie** – používa klienta `painting_inpaint.remote` a vzdialenú službu; vyžaduje internetové pripojenie, endpoint URL a API kľúč
* **textúrové dopĺňanie** – používa lokálne nainštalovaný balík `texture_infill`; umožňuje doplniť vybranú poškodenú oblasť alebo vytvoriť samostatnú textúru a pridať ju medzi materiály projektu

Pri použití nainštalovanej verzie aplikácie sú potrebné balíky a modely už zahrnuté v inštalácii.
