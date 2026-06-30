# RePaint

RePaint je aplikácia určená na digitálne dopĺňanie poškodených častí obrazov. Umožňuje pracovať s pôvodným obrazom, maskou poškodenia, viacerými vrstvami, ručnými nástrojmi a externými algoritmami na dopĺňanie chýbajúcich miest.

Aplikácia vzniká ako súčasť bakalárskej práce a je zameraná najmä na použitie pri príprave návrhov reštaurátorského zásahu.

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
│   ├── rp_restore/
│       ├── config/
│       ├── core/
│       ├── gui/
│       ├── io/
│       └── report/
│   └── requirements.txt
└── README.md
```

Priečinok `rp_restore_app` obsahuje samotnú aplikáciu. Hlavný balík aplikácie je `rp_restore`.

Priečinok `docs` obsahuje dokumentáciu:

* `user_documentation.md` – užívateľská dokumentácia
* `developer_documentation.md` – programátorská dokumentácia

## Inštalácia a spustenie

Aplikácia zatiaľ nie je zabalená ako samostatný inštalačný súbor. Spúšťa sa preto priamo zo zdrojového kódu.

Najprv je potrebné naklonovať repozitár:

```
git clone https://gitlab.mff.cuni.cz/teaching/nprg045/ikudov/pohankova-katarina.git
cd pohankova-katarina
```

Potom sa vytvorí a aktivuje virtuálne prostredie:

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Následne sa nainštalujú závislosti:

```
python -m pip install -r requirements.txt
```

Aplikácia sa spustí z priečinka `rp_restore_app`:

```
cd rp_restore_app
python app.py
```

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

Aplikácia obsahuje podporu pre externé algoritmy:

* realistické dopĺňanie
* textúrové dopĺňanie

## Poznámky

Aplikácia je stále vo vývoji. Niektoré časti, najmä externé algoritmy a spôsob distribúcie aplikácie, sa budú ešte meniť