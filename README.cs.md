# RePaint

**Language / Jazyk:** [English](README.md) | [Čeština](README.cs.md) | [Slovenčina](README.sk.md)

RePaint je aplikace určená k digitálnímu doplňování poškozených částí obrazů. Umožňuje pracovat s původním obrazem, maskou poškození, více vrstvami, ručními nástroji a externími algoritmy pro doplňování chybějících míst.

Aplikace vznikla jako součást bakalářské práce ve spolupráci s Národní galerií v Praze a je určena především k přípravě a porovnávání návrhů restaurátorských zásahů.

## Funkce aplikace

Aplikace podporuje zejména:

* vytvoření projektu z obrazu a masky poškození
* zarovnání masky poškození pomocí odpovídajících bodů
* načtení a zarovnání historické kopie obrazu
* využití historické kopie jako referenčního podkladu při plánování rekonstrukce
* práci s vrstvami
* ruční doplňování barvou nebo texturou
* výplň poškozených regionů
* výběr poškozených oblastí kliknutím nebo lasem
* kreslení hran pro rozdělení poškození na menší regiony
* zjemnění přechodu mezi vyplněnými regiony
* rozmazání doplněných částí
* automatickou výplň malých poškozených oblastí
* ColorChecker korekci
* externí realistické a texturové doplňování
* využití historické kopie při realistickém doplňování poškozených míst
* Undo/Redo
* uložení a otevření projektu ve formátu `.zip`
* vytváření nezávislých návrhů rekonstrukce z existujícího projektu
* export výsledného obrazu
* export PDF reportu

## Struktura projektu

Základní struktura repozitáře:

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

Adresář `rp_restore_app` obsahuje samotnou aplikaci. Jejím hlavním balíkem je `rp_restore`.

Adresář `docs` obsahuje dokumentaci:

* `user_documentation.md` – uživatelská dokumentace
* `developer_documentation.md` – programátorská dokumentace

## Instalace a spuštění

Aplikaci lze používat dvěma způsoby: nainstalovat ji pomocí připraveného instalátoru nebo ji spustit přímo ze zdrojového kódu.

### Instalace pomocí instalátoru

Pro běžné použití je určen soubor:

```text
RePaint-Setup-1.1.0.exe
```

Nejnovější verze aplikace je dostupná v sekci
[GitHub Releases](https://github.com/katarinapohankova/RePaint/releases/latest).

Instalátor je určen pro 64bitový operační systém Windows. Po spuštění se aplikace nainstaluje do uživatelského adresáře, vytvoří se zástupce v nabídce Start a volitelně také zástupce na ploše.

Nainstalovaná verze již obsahuje Python, potřebné knihovny i lokální texturový algoritmus. Na cílovém počítači proto není nutné samostatně instalovat Python, Git ani další závislosti.

Realistické doplňování používá vzdálenou službu. Vyžaduje připojení k internetu a platný API klíč, který se zadává při prvním použití a poté se ukládá do systémového úložiště přihlašovacích údajů.

### Spuštění ze zdrojového kódu

Pro spuštění ze zdrojů je potřeba Python 3.13 a Git. Repozitář se naklonuje a poté se přejde do adresáře aplikace:

```powershell
git clone https://github.com/katarinapohankova/RePaint.git
cd RePaint\rp_restore_app
```

Vytvoří a aktivuje se virtuální prostředí:

```powershell
python3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Po aktivaci prostředí se závislosti instalují pomocí interpretru `python` z daného virtuálního prostředí:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Aplikace se spustí příkazem:

```powershell
python app.py
```

Instalace ze zdrojového kódu může vyžadovat oprávnění k přístupu do repozitářů externích balíků uvedených v souboru `requirements.txt`.
Klient realistického doplňování se instaluje ze soukromého repozitáře GitHub, proto je k jeho získání potřeba příslušný přístup. Běžným uživatelům se doporučuje instalace pomocí připraveného instalátoru pro Windows.

## Použití

Po spuštění aplikace je možné vytvořit nový projekt nebo otevřít již existující projekt.

Nový projekt se vytváří z původního obrazu. Volitelně je možné přidat také masku poškození, která určuje oblasti určené k doplňování. Pokud je maska přidána, aplikace umožní její zarovnání s obrazem pomocí odpovídajících bodů.

Do projektu lze dodatečně načíst také historickou kopii obrazu. Ta se zarovná s původním obrazem a může sloužit jako referenční podklad při doplňování poškozených oblastí, včetně využití realistického algoritmu.

Z existujícího projektu lze vytvořit nový nezávislý návrh rekonstrukce. Uživatel si může zvolit, zda chce zachovat existující vrstvy malby a hran, nebo začít s prázdnými pracovními vrstvami.

Podrobnější popis práce s aplikací je uveden v [uživatelské dokumentaci](docs/user_documentation.cs.md).

## Vývojářská dokumentace

Stručný popis vnitřní struktury aplikace, hlavních modulů, datového modelu a nástrojů je uveden v [programátorské dokumentaci](docs/developer_documentation.cs.md).

## Ukládání projektů

Projekt se ukládá jako soubor `.zip`. Tento soubor obsahuje zejména:

* metadata projektu
* původní obraz
* vrstvy
* masky
* paletu
* textury
* nastavení potřebná k pokračování v práci

Pokud projekt obsahuje historickou kopii, uloží se spolu s ostatními vrstvami, včetně průhlednosti a nastavení. Při vytváření dalšího návrhu se zachová také její zarovnání. Každý návrh se ukládá jako samostatný projekt.

Při exportu výsledného obrazu se vždy používá původní obraz spolu s viditelnými pracovními vrstvami. Historická kopie je pouze referenční a do výsledné rekonstrukce se nezahrnuje. V PDF reportu může být uvedena samostatně.

Uložený projekt je možné později znovu otevřít v aplikaci a pokračovat v úpravách.

## Externí algoritmy

Aplikace podporuje dva externí algoritmy:

* **realistické doplňování** – používá klienta `painting_inpaint.remote` a vzdálenou službu; umožňuje vybrat vstupní podklad z původního obrazu, historické kopie nebo jejich kombinace podle masky poškození; vyžaduje připojení k internetu, endpoint URL a API klíč
* **texturové doplňování** – používá lokálně nainstalovaný balík `texture_infill`; umožňuje doplnit vybranou poškozenou oblast nebo vytvořit samostatnou texturu a přidat ji mezi materiály projektu

Při použití nainstalované verze aplikace jsou potřebné balíky a modely již zahrnuty v instalaci.
