# RePaint

**Language / Jazyk:** [English](README.md) | [Čeština](README.cs.md) | [Slovenčina](README.sk.md)

RePaint je aplikácia určená na digitálne dopĺňanie poškodených častí obrazov. Umožňuje pracovať s pôvodným obrazom, maskou poškodenia, viacerými vrstvami, ručnými nástrojmi a externými algoritmami na dopĺňanie chýbajúcich miest.

Aplikácia vznikla ako súčasť bakalárskej práce v spolupráci s Národnou galériou v Prahe a je určená najmä na prípravu a porovnávanie návrhov reštaurátorského zásahu.

## Funkcie aplikácie

Aplikácia podporuje najmä:

* vytvorenie projektu z obrazu a masky poškodenia
* zarovnanie masky poškodenia pomocou zodpovedajúcich bodov
* načítanie a zarovnanie historickej kópie obrazu
* využitie historickej kópie ako referenčného podkladu pri plánovaní rekonštrukcie
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
* využitie historickej kópie pri realistickom dopĺňaní poškodených miest
* Undo/Redo
* uloženie a otvorenie projektu vo formáte `.zip`
* vytváranie nezávislých návrhov rekonštrukcie z existujúceho projektu
* export výsledného obrazu
* export PDF reportu

## Štruktúra projektu

Základná štruktúra repozitára:

```
.
├── docs/
│   ├── user_documentation.md
│   ├── user_documentation.cs.md
│   ├── user_documentation.en.md
│   ├── developer_documentation.md
│   ├── developer_documentation.cs.md
│   └── developer_documentation.en.md
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
│       └── resources/
├── COPYRIGHT.md
├── README.cs.md
├── README.sk.md
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
RePaint-Setup-1.1.0.exe
```

Najnovšia verzia aplikácie je dostupná v sekcii
[GitHub Releases](https://github.com/katarinapohankova/RePaint/releases/latest)

Inštalátor je určený pre 64-bitový operačný systém Windows. Po jeho spustení sa aplikácia nainštaluje do používateľského priečinka, vytvorí sa odkaz v ponuke Štart a voliteľne aj odkaz na pracovnej ploche.

Táto verzia už obsahuje Python, potrebné knižnice aj lokálny textúrový algoritmus. Na cieľovom počítači preto nie je potrebné samostatne inštalovať Python, Git ani ďalšie závislosti.

Realistické dopĺňanie používa vzdialenú službu. Vyžaduje internetové pripojenie a platný API kľúč, ktorý sa zadáva pri prvom použití a následne sa ukladá do systémového úložiska prihlasovacích údajov.

### Spustenie zo zdrojového kódu

Na spustenie zo zdrojov je potrebný Python 3.13 a Git. Repozitár sa naklonuje a následne sa prejde do priečinka aplikácie:

```powershell
git clone https://github.com/katarinapohankova/RePaint.git
cd RePaint\rp_restore_app
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
Klient realistického dopĺňania sa inštaluje zo súkromného GitHub repozitára, preto je na jeho získanie potrebný príslušný prístup. Bežným používateľom sa odporúča inštalácia pomocou pripraveného Windows inštalátora.

## Použitie

Po spustení aplikácie je možné vytvoriť nový projekt alebo otvoriť už existujúci projekt.

Nový projekt sa vytvára z pôvodného obrazu. Voliteľne je možné pridať aj masku poškodenia, ktorá určuje oblasti určené na dopĺňanie. Ak je maska pridaná, aplikácia umožní jej zarovnanie s obrazom pomocou zodpovedajúcich bodov.

Do projektu je možné dodatočne načítať aj historickú kópiu obrazu. Tá sa zarovná s pôvodným obrazom a môže slúžiť ako referenčný podklad pri dopĺňaní poškodených oblastí vrátane použitia realistického algoritmu.

Z existujúceho projektu je možné vytvoriť nový nezávislý návrh rekonštrukcie. Používateľ si môže vybrať, či chce zachovať existujúce vrstvy malby a hrán, alebo začať s prázdnymi pracovnými vrstvami.

Podrobnejší opis práce s aplikáciou je uvedený v [užívateľskej dokumentácii](docs/user_documentation.md).

## Vývojárska dokumentácia

Stručný opis vnútornej štruktúry aplikácie, hlavných modulov, dátového modelu a nástrojov je uvedený v [programátorskej dokumentácii](docs/developer_documentation.md).

## Ukladanie projektov

Projekt sa ukladá ako `.zip` súbor. Tento súbor obsahuje najmä:

* metadata projektu
* pôvodný obraz
* vrstvy
* masky
* paletu
* textúry
* nastavenia potrebné na pokračovanie práce

Ak projekt obsahuje historickú kópiu, tá sa uloží spolu s ostatnými vrstvami vrátane priehľadnosti a nastavení. Pri vytváraní ďalšieho návrhu sa zachová aj jej zarovnanie. Každý návrh sa ukladá ako samostatný projekt.

Pri exporte výsledného obrazu sa vždy používa pôvodný obraz spolu s viditeľnými pracovnými vrstvami. Historická kópia je iba referenčná a do výslednej rekonštrukcie sa nezahrnie. V PDF reporte môže byť uvedená samostatne.

Uložený projekt je možné neskôr znovu otvoriť v aplikácii a pokračovať v úpravách.

## Externé algoritmy

Aplikácia podporuje dva externé algoritmy:

* **realistické dopĺňanie** – používa klienta `painting_inpaint.remote` a vzdialenú službu; umožňuje vybrať vstupný podklad z pôvodného obrazu, historickej kópie alebo ich kombinácie podľa masky poškodenia; vyžaduje internetové pripojenie, endpoint URL a API kľúč
* **textúrové dopĺňanie** – používa lokálne nainštalovaný balík `texture_infill`; umožňuje doplniť vybranú poškodenú oblasť alebo vytvoriť samostatnú textúru a pridať ju medzi materiály projektu

Pri použití nainštalovanej verzie aplikácie sú potrebné balíky a modely už zahrnuté v inštalácii.
