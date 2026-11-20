# RePaint – uživatelská dokumentace

**Language / Jazyk:** [English](user_documentation.en.md) | [Čeština](user_documentation.cs.md) | [Slovenčina](user_documentation.md)

## Obsah

* [Instalace a spuštění](#instalace-a-spuštění)
* [1. Vytvoření nového projektu](#1-vytvoření-nového-projektu)
* [2. Zarovnání masky poškození](#2-zarovnání-masky-poškození)
* [3. Otevření existujícího projektu](#3-otevření-existujícího-projektu)
* [4. Pracovní prostředí](#4-pracovní-prostředí)
* [5. Ovládání obrazu](#5-ovládání-obrazu)
* [6. Vrstvy](#6-vrstvy)
  * [Historická kopie](#historická-kopie)
* [7. Maska poškození a zvýraznění poškozených míst](#7-maska-poškození-a-zvýraznění-poškozených-míst)
* [8. Paleta barev](#8-paleta-barev)
* [9. Materiály a nastavení štětce](#9-materiály-a-nastavení-štětce)
* [10. Textury](#10-textury)
* [11. Nástroje](#11-nástroje)

  * [Štětec](#štětec)
  * [Guma](#guma)
  * [Rozmazání](#rozmazání)
  * [Výplň](#výplň)
  * [Vybrat](#vybrat)
  * [Laso](#laso)
  * [Hrana](#hrana)
  * [Zjemnit hranu](#zjemnit-hranu)
  * [Pipeta](#pipeta)
  * [Auto-výplň malých oblastí](#auto-výplň-malých-oblastí)
* [12. Externí algoritmy](#12-externí-algoritmy)

  * [Realistické doplnění](#realistické-doplnění)
  * [Texturové doplnění](#texturové-doplnění)
* [13. ColorChecker korekce](#13-colorchecker-korekce)
* [14. Undo a Redo](#14-undo-a-redo)
* [15. Ukládání projektu](#15-ukládání-projektu)
  * [Vytvoření nového návrhu z existujícího projektu](#vytvoření-nového-návrhu-z-existujícího-projektu)
* [16. Export výsledného obrazu](#16-export-výsledného-obrazu)
* [17. Export PDF reportu](#17-export-pdf-reportu)
* [18. Klávesové zkratky](#18-klávesové-zkratky)
* [19. Doporučený pracovní postup](#19-doporučený-pracovní-postup)
* [20. Časté problémy](#20-časté-problémy)

## Instalace a spuštění

Aplikaci lze používat dvěma způsoby.

### Instalace pomocí instalátoru

Pro běžné uživatele je určen soubor:

```text
RePaint-Setup-1.1.0.exe
```

Instalátor je určen pro 64bitový operační systém Windows. Po spuštění postupujte podle kroků průvodce. Aplikace se nainstaluje do uživatelského adresáře, přidá se do nabídky Start a volitelně lze vytvořit také zástupce na ploše.

Nainstalovaná verze již obsahuje Python, potřebné knihovny i lokální texturový algoritmus. Uživatel proto nemusí nic dalšího instalovat.

Při prvním použití realistického doplňování aplikace vyžádá endpoint URL a API klíč vzdálené služby. Údaje se uloží do systémového úložiště přihlašovacích údajů. Později je lze změnit přes **Nastavení → Remote realistické doplnění...**.

### Spuštění ze zdrojového kódu

Ke spuštění ze zdrojů je potřeba Python 3.13 a Git.

```powershell
git clone https://github.com/katarinapohankova/RePaint.git
cd RePaint\rp_restore_app

python3 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python app.py
```

Po aktivaci virtuálního prostředí se používá příkaz `python`, který odkazuje na interpret z daného prostředí. Instalace ze zdrojů může vyžadovat oprávnění k přístupu do repozitářů externích balíků uvedených v souboru `requirements.txt`.
Klient realistického doplňování se instaluje ze soukromého repozitáře GitHub, proto je k jeho získání potřeba příslušný přístup. Běžným uživatelům se doporučuje instalace pomocí připraveného instalátoru pro Windows.

## 1. Vytvoření nového projektu

Nový projekt lze vytvořit z úvodní obrazovky tlačítkem **Nový projekt** nebo přes nabídku **Soubor → Nový projekt z obrázku...**.

Při vytváření projektu se nejprve vybere původní obraz. Podporovány jsou běžné obrazové formáty, například PNG, JPG, JPEG, TIFF nebo TIF.

Po výběru obrazu lze vybrat také masku poškození. Maska určuje, které části obrazu jsou poškozené a kde je možné použít nástroje k doplňování. Pokud masku nechcete použít, můžete dialog pro výběr masky zavřít a pokračovat bez ní.

Pokud je maska vybrána, aplikace otevře dialog pro její zarovnání s původním obrazem.

## 2. Zarovnání masky poškození

Při zarovnávání masky se vybírají odpovídající body na původním obraze a na masce. Cílem je určit, jak se má maska transformovat, aby přesně odpovídala obrazu.

Postup:

1. Klikněte na bod na původním obraze.
2. Klikněte na odpovídající bod na masce.
3. V dalším okně se zobrazí zvětšený výřez obou míst.
4. Upřesněte polohu bodu na obraze i na masce co nejpřesněji.
5. Potvrďte dvojici bodů.
6. Stejným způsobem přidejte další body.

Pro zarovnání je potřeba vybrat alespoň čtyři dvojice bodů. Lze vybrat i více bodů, ale jejich počet je omezený. Čím přesněji jsou body zvoleny a čím rovnoměrněji jsou rozmístěny po obraze, tím spolehlivěji lze zarovnání vypočítat. Použití většího počtu správně zvolených bodů může přesnost zarovnání zlepšit.

V dialogu lze odstranit poslední bod nebo všechny body a začít znovu.

## 3. Otevření existujícího projektu

Existující projekt se otevírá přes **Soubor → Otevřít projekt...** nebo tlačítkem **Otevřít projekt** na úvodní obrazovce.

Projekt se ukládá jako soubor `.zip`. Tento soubor obsahuje vrstvy, masky, paletu, textury a další nastavení potřebná k pokračování v práci.

Na úvodní obrazovce se zobrazuje také seznam naposledy otevřených projektů. Projekt ze seznamu lze otevřít dvojklikem.

## 4. Pracovní prostředí

Po otevření projektu se zobrazí hlavní pracovní prostředí aplikace. Uprostřed je obraz, na kterém se bude pracovat. Kolem něj jsou panely a lišta nástrojů.

Hlavní části prostředí:

* levá lišta nástrojů,
* panel **Vrstvy**
* panel **Paleta**
* panel **Externí algoritmy**
* panel **Hrany**
* panel **Materiály**
* horní nabídka aplikace
* stavový řádek ve spodní části okna

Panely lze zobrazit nebo skrýt přes nabídku **Zobrazení**. Pokud panel zavřete, můžete jej později znovu otevřít prostřednictvím této nabídky.

## 5. Ovládání obrazu

Obraz lze přibližovat, oddalovat a posouvat.

Základní ovládání:

* kolečko myši přibližuje nebo oddaluje obraz
* pravé nebo prostřední tlačítko myši slouží k posunu obrazu
* kreslení a používání nástrojů se provádí levým tlačítkem myši

Při otevření projektu se obraz automaticky přizpůsobí velikosti okna. Přiblížení lze zvýšit až na stonásobek.

## 6. Vrstvy

Aplikace pracuje s několika typy vrstev:

* **Původní obraz** – původní načtený obraz, nelze jej měnit
* **Historická kopie** – volitelná referenční vrstva umožňující porovnávat současný obraz s jeho historickou podobou
* **Malba** – pracovní vrstvy, do kterých se doplňují poškozená místa
* **Hrany** – vrstva s hranami, které rozdělují poškození na samostatné oblasti

Nejčastěji se pracuje s vrstvami typu **Malba**. Do nich se kreslí štětcem, aplikuje výplň, textura, rozmazání nebo výsledky algoritmů.

V panelu **Vrstvy** lze:

* vybrat aktivní vrstvu
* zobrazit nebo skrýt vrstvu ikonou vlevo
* vytvořit novou vrstvu malby
* přejmenovat vrstvu
* odstranit vrstvu malby
* měnit průhlednost aktivní vrstvy
* zobrazit náhled aktivní vrstvy

Odstraňovat lze pouze vrstvy malby.
Vrstva historické kopie se v panelu zobrazí až po načtení referenčního obrázku. Není určena ke kreslení a lze nezávisle přepínat její viditelnost a nastavovat krytí.

### Náhled vrstvy

Panel **Vrstvy** obsahuje náhled aktivní vrstvy. Tento náhled pomáhá zkontrolovat, co se nachází přímo v dané vrstvě, aniž by bylo nutné skrývat ostatní vrstvy.

Kliknutím na náhled vrstvy se zobrazí zvětšený náhled přímo na hlavní ploše. Opětovným kliknutím na zmenšený náhled se náhled skryje a aplikace se vrátí k běžnému zobrazení obrazu.

### Historická kopie

Aplikace umožňuje používat historickou kopii obrazu jako referenci při plánování rekonstrukce. Kopie se načítá do již existujícího projektu a zarovnává se s původním obrazem.

#### Načtení a zarovnání

1. Otevřete projekt obsahující původní obraz.
2. V nabídce vyberte **Soubor → Načíst historickou kopii...**.
3. Vyberte obrázek historické kopie.
4. V dialogu označte odpovídající body na původním obraze a historické kopii.
5. Každou dvojici bodů můžete přesněji upravit ve zvětšených výřezech.
6. Po označení alespoň čtyř dvojic bodů potvrďte zarovnání.

Aplikace vypočítá homografii a zarovná historickou kopii do souřadnicového systému původního obrazu. Pro přesnější zarovnání lze použít až 20 dvojic bodů.

Po zarovnání se v panelu **Vrstvy** zobrazí vrstva **Historická kopie**. Pokud již projekt historickou kopii obsahuje, lze ji nahradit jiným snímkem.

#### Zobrazení historické kopie

Zobrazení závisí na viditelnosti vrstev **Původní obraz** a **Historická kopie**:

* **Pouze původní obraz:** původní obraz se zobrazuje na celém plátně.
* **Obě vrstvy:** mimo poškozená místa se zobrazuje původní obraz, v poškozených místech historická kopie.
* **Pouze historická kopie:** kopie se zobrazuje na celém plátně.
* **Obě vrstvy skryté:** nezobrazuje se žádný podklad.

Poškozené oblasti, ve kterých se používá historická kopie, se určují podle původní masky poškození, nikoli podle zbývajících nevyplněných míst.

Vrstva historické kopie podporuje průhlednost. Její krytí lze nastavovat posuvníkem stejně jako u ostatních vrstev. Při sníženém krytí se v poškozených oblastech pod kopií nezobrazuje původní obraz.

Zobrazení masky poškození a ostatních vrstev funguje nezávisle na viditelnosti historické kopie.

Historická kopie slouží pouze jako reference. Není součástí exportovaného výsledného obrazu.

## 7. Maska poškození a zvýraznění poškozených míst

Maska poškození určuje, které pixely obrazu se považují za poškozené. Většina nástrojů pracuje pouze v těchto místech.
Při přípravě masky se doporučuje používat černobílý obraz, ve kterém bílé pixely označují poškozená místa a černé pixely nepoškozené oblasti.

Maska se po načtení převede na binární reprezentaci,
se kterou aplikace dále pracuje.

Poškozená místa lze zvýraznit přes **Zobrazení → Zobrazit poškozené oblasti**. Ve stejné nabídce se nachází i posuvník pro nastavení průhlednosti zvýraznění.

Zvýraznění odpovídá aktuálně viditelným vrstvám. Pokud je některá vrstva malby skrytá, aplikace ji při zobrazení zbývajícího poškození nebere v úvahu.

## 8. Paleta barev

Panel **Paleta** slouží k výběru aktuální barvy a ukládání často používaných barev.

V panelu lze:

* změnit aktuální barvu
* přidat aktuální barvu do palety
* vybrat barvu z palety
* odstranit barvu z palety

Pokud se do palety přidává barva, která v ní již je, nevytvoří se duplicita.

Aktuální barva se používá při práci se štětcem, výplní a při nastavení barvy textury.

## 9. Materiály a nastavení štětce

Panel **Materiály** obsahuje nastavení štětce, gumy, rozmazání a textur.

Pro štětec, gumu a rozmazání lze nastavit:

* velikost štětce
* tvrdost
* krytí
* hustotu
* zda se má tah vrstvit
* sílu rozmazání
* zdroj rozmazání

Hodnota **Tvrdost** ovlivňuje okraj stopy štětce. Nižší tvrdost znamená měkčí okraj, vyšší tvrdost ostřejší okraj.

Hodnota **Krytí** určuje maximální neprůhlednost stopy.

Hodnota **Hustota** ovlivňuje, jak rychle se barva nebo mazání během tahu nanáší.

Možnost **Vrstvit v tahu** určuje, zda se jeden tah může během tažení myší postupně zesilovat, až do nastavené hodnoty krytí.

## 10. Textury

V panelu **Materiály** lze přepnout režim ze **Štětec** na **Textura**. V texturovém režimu se namísto jednolité barvy používá vybraná textura.

U textur lze nastavit:

* vybranou texturu
* hustotu textury
* sílu textury
* rotaci
* styl textury
* deformaci šířky a výšky

K dispozici jsou dva styly textury:

* **Transparentní** – jas textury určuje průhlednost vzoru obarveného aktuální barvou
* **Barevná** – jas textury vytváří světlejší a tmavší odstíny aktuální barvy

Textury vytvořené externím texturovým algoritmem si zachovávají vlastní vygenerované barvy. Styl **Transparentní/Barevná** se u nich nepoužívá a jejich barvy se upravují samostatně tlačítkem **Upravit barvy…**.

V části **Deformace textury** lze změnit šířku a výšku textury. Deformace se projeví v náhledu a při dalším použití textury.

Pokud chcete aktuálně deformovanou texturu používat opakovaně, stiskněte **Přidat mezi textury**. Aplikace vytvoří novou texturu odvozenou od původní a přidá ji mezi ostatní textury. Pokud již stejná deformovaná verze existuje, nepřidá se duplicitně.

Do projektu lze přidat také vlastní texturu ze souboru.

## 11. Nástroje

Nástroje se vybírají v levé liště. Aktivní nástroj je zvýrazněný.

### Štětec

Nástroj **Štětec** slouží k ručnímu doplňování poškozených míst barvou nebo texturou. Používá aktuální barvu z palety a nastavení z panelu **Materiály**.

Kreslí se tažením levým tlačítkem myši.

Štětec lze používat pouze ve vrstvě malby. Pokud je aktivní jiná vrstva, aplikace se pokusí automaticky přepnout na vhodnou vrstvu malby.

---

### Guma

Nástroj **Guma** slouží k mazání obsahu vrstvy malby. Maže pouze to, co bylo doplněno do pracovní vrstvy, nikoli původní obraz.

Guma používá velikost, tvrdost, krytí a hustotu z panelu **Materiály**.

---

### Rozmazání

Nástroj **Rozmazání** slouží k jemnému rozmazání již doplněných částí. Pracuje v poškozené oblasti a používá nastavení z panelu **Materiály**.

V panelu lze zvolit zdroj rozmazání:

* **Vrstva malby** – rozmazává se pouze obsah aktivní vrstvy malby
* **Původní obraz + vrstva malby** – při výpočtu se zohledňuje také původní obraz pod vrstvou

Tento nástroj je vhodný například ke zjemnění ručně doplněných míst nebo úpravě příliš ostrých přechodů.

---

### Výplň

Nástroj **Výplň** vyplní poškozený region aktuální barvou nebo texturou.

Pokud není vybrána žádná oblast, stačí kliknout do poškozeného regionu. Aplikace vyplní celý region určený maskou poškození a případnými hranami.

Pokud je aktivní výběr, výplň se použije na vybrané oblasti.

Výplň se aplikuje pouze na místa, která ještě nejsou v aktivní vrstvě malby vyplněná.

---

### Vybrat

Nástroj **Vybrat** slouží k výběru poškozených regionů.

Kliknutím se vybere jeden region. Podržením klávesy **Ctrl** a kliknutím lze přidávat další regiony do výběru nebo je z výběru odebírat.

Vybrané oblasti se zobrazují šedým zvýrazněním.

Výběr se používá například před spuštěním texturového algoritmu nebo hromadnou výplní více oblastí.

---

### Laso

Nástroj **Laso** slouží k výběru více poškozených regionů tažením myší. Během tahu se kreslí obrys lasa. Po uvolnění tlačítka aplikace vybere poškozené regiony, které se nacházejí uvnitř nakresleného tvaru.

Pokud při použití lasa podržíte **Ctrl**, nový výběr se přidá k existujícímu.

Laso je vhodné pro rychlý výběr několika blízkých poškozených míst.

---

### Hrana

Nástroj **Hrana** slouží ke kreslení hranic v poškozených místech. Hrany rozdělují poškození na menší samostatné regiony, které lze následně vyplnit odděleně.

Hrany by se měly kreslit pouze tam, kde je potřeba poškozenou oblast rozdělit. Nejsou určeny jako běžný kreslicí štětec.

Kreslení hrany:

* levé tlačítko myši kreslí hranu
* pravé tlačítko myši nebo **Shift + levé tlačítko** hranu maže

Barvu hrany a šířku zjemnění lze nastavit v panelu **Hrany**.

---

### Zjemnit hranu

Nástroj **Zjemnit hranu** slouží ke zjemnění přechodu mezi dvěma regiony oddělenými již nakreslenou hranou. Používá se tehdy, když hrana rozdělila poškození na dvě části, obě strany jsou již vyplněné a přechod mezi nimi je příliš ostrý.

Při použití nástroje přejeďte levým tlačítkem přes existující hranu. Aplikace odstraní zasaženou část hrany a vytvoří jemnější přechod mezi doplněnými oblastmi.

Nástroj funguje pouze tam, kde existuje nakreslená hrana. Pokud není co zjemnit, aplikace zobrazí upozornění.

Šířka zjemnění se nastavuje v panelu **Hrany** hodnotou **Zjemnění (px)**.

---

### Pipeta

Nástroj **Pipeta** slouží k odebrání barvy z obrazu. Kliknutím na obraz se vybraná barva nastaví jako aktuální barva v paletě.

Pipeta je užitečná při ručním doplňování, když chcete navázat na barvy v okolí poškození.

---

### Auto-výplň malých oblastí

Nástroj **Auto-výplň malých oblastí** automaticky vyplní malé poškozené regiony podle nastavené maximální velikosti v pixelech.

Vedle nástroje je posuvník a číselná hodnota, kterou se nastavuje prahová velikost oblasti. Po změně hodnoty aplikace zvýrazní vhodné oblasti tyrkysovou barvou.

Kliknutím na zvýrazněnou oblast ji můžete z automatické výplně vyřadit nebo ji znovu zařadit.

Po stisknutí tlačítka **Auto-výplň malých oblastí** aplikace vyplní vybrané malé oblasti barvou vypočtenou z jejich okolí.

Pokud je aktivní ruční výběr oblastí, automatická výplň se použije na tento výběr.

Toto tlačítko je potřeba stisknout až ve chvíli, kdy chcete vybrané oblasti vyplnit; nejde o trvale aktivní kreslicí nástroj.

---

## 12. Externí algoritmy

Panel **Externí algoritmy** obsahuje nástroje pro automatické doplňování poškozených částí pomocí externích algoritmů.

* **Realistické doplnění**
* **Texturové doplnění**

### Realistické doplnění

Realistické doplnění slouží k automatickému dogenerování poškozených míst ve zvoleném obdélníkovém okně. Algoritmus se spouští na vzdálené službě, proto vyžaduje připojení k internetu a platný API klíč.

Při prvním použití aplikace vyžádá přístupové údaje. Později je lze upravit přes **Nastavení → Remote realistické doplnění...**.

Po stisknutí tlačítka **Realistické doplnění** se otevře dialog, ve kterém lze zvolit okno dvěma způsoby:

* použít společný ohraničující obdélník aktuálního výběru
* vybrat okno ručně přímo v obraze

Maximální velikost okna je 1440 × 1440 pixelů. Okno musí obsahovat alespoň část zbývající masky poškození.

K dispozici jsou dva režimy:

* **Základní** – je určen pro běžné realistické doplňování poškozených míst. Umožňuje nastavit míru dogenerování.
* **Vedené podle náčrtu** – umožňuje usměrnit doplňování pomocí ručně nakreslených vodicích čar. Ty by měly být tmavé a tenké, ideálně přibližně jeden pixel široké. Tento režim je výrazně pomalejší.

V obou režimech lze nezávisle vybrat podklad, ze kterého má algoritmus vycházet:

* **Původní obraz** – použije se původní obraz.
* **Historická kopie** – použije se historická kopie v celé oblasti vstupního okna.
* **Původní obraz + kopie v poškozených místech** – mimo poškozená místa se použije původní obraz, v poškozených místech historická kopie.

Poslední dvě možnosti jsou dostupné pouze v projektu, který obsahuje načtenou historickou kopii.

Pokud historická kopie obsahuje průhledná místa, algoritmus místo nich automaticky použije odpovídající pixely původního obrazu. Při částečné průhlednosti se oba obrazy plynule smíchají.

Výběr podkladu nezávisí na aktuální viditelnosti vrstev na plátně ani na nastaveném krytí historické kopie.

Volba **Použít viditelné vrstvy malby a hran** umožňuje zahrnout do vstupního obrazu také existující viditelné pracovní vrstvy. V základním režimu je ve výchozím stavu vypnutá, ve vedeném režimu zapnutá. Uživatel ji může změnit.

V základním režimu lze nastavit hodnotu **Míra dogenerování**. Nižší hodnota více zachovává původní strukturu pod maskou, zatímco hodnota 1 znamená úplné dogenerování. Pokud pod maskou nejsou použitelné původní pixely, doporučuje se nastavit hodnotu 1.

Volitelná hodnota **seed** umožňuje opakovat výpočet se stejným náhodným nastavením.

Pokud je aktivní výběr regionů, výsledek se použije pouze v tomto výběru. Pokud výběr neexistuje, použije se zbývající maska poškození ve zvoleném okně. Výsledek se vloží do aktivní vrstvy malby pouze na místech, která na ní ještě nejsou vyplněná.

Model realistického doplňování je primárně určen k restaurování děl Albrechta Dürera.

### Texturové doplnění

Texturové doplnění používá lokální algoritmus k vytvoření texturovaného obsahu. Dialog nabízí dva režimy výstupu:

* **Doplnit vybranou oblast obrazu** – výsledek se vloží přímo do vybraných poškozených regionů,
* **Vygenerovat samostatnou texturu a přidat ji do materiálů** – vytvoří samostatný texturový obraz, který se přidá mezi textury aktuálního projektu.

Pro přímé doplnění obrazu je potřeba nejprve vybrat poškozenou oblast nástrojem **Vybrat** nebo **Laso**. Bez aktivního výběru lze stále vytvořit samostatnou texturu a přidat ji do panelu Materiály.

V dialogu lze nastavit:

* typ modelu textury
* jednu až tři barvy
* sílu každé barevné vrstvy
* měřítko v osách X a Y
* hustotu v osách X a Y u modelů, které ji podporují
* rotaci
* celkové měřítko
* neprůhledné nebo průhledné pozadí
* jas neprůhledného pozadí
* seed
* šířku a výšku samostatně generované textury

U každého modelu se zobrazuje jeho vstupní náhled. Tlačítkem **Vygenerovat náhled** lze vytvořit i zmenšený náhled výsledné textury podle aktuálních parametrů.

Při doplňování vybrané oblasti se výsledek vloží do aktivní vrstvy malby pouze v místech aktuálního výběru, která jsou stále poškozená a na dané vrstvě ještě nebyla vyplněna.

Samostatně vygenerovaná textura se přidá do panelu Materiály a zachová si vlastní vygenerované barvy. Lze ji používat texturovým štětcem nebo výplní. Při jejím výběru se zobrazí původní barvy a jejich síly; tlačítkem **Upravit barvy…** lze barvy změnit a texturu znovu vygenerovat.

## 13. ColorChecker korekce

Aplikace podporuje barevnou korekci pomocí tabulky ColorChecker. Dialog se otevírá přes **Úpravy → ColorChecker...**.

Postup:

1. Načtěte kalibrační fotografii s tabulkou ColorChecker.
2. Klikněte na čtyři rohy tabulky v pořadí uvedeném v dialogu.
3. Stiskněte **Spočítat korekci**.
4. Pokud je korekce vypočítána, použijte ji tlačítkem **Použít**.

Po výpočtu korekce lze její zobrazení zapnout nebo vypnout přes **Zobrazení → Použít ColorChecker korekci**.

Kalibrační fotografie by měla být vytvořena za stejných světelných podmínek jako pracovní fotografie díla. Ideálně by se měla pořídit přímo při dokumentaci díla.

Doporučuje se rozhodnout o použití ColorChecker korekce na začátku práce. Pokud se korekce zapne až po ručním doplňování, může se změnit vzhled již doplněných barev.

## 14. Undo a Redo

Aplikace podporuje vrácení a opětovné provedení úprav.

* **Úpravy → Zpět** nebo **Ctrl+Z** vrátí poslední úpravu
* **Úpravy → Znovu** nebo **Ctrl+Y** / **Ctrl+Shift+Z** obnoví vrácenou úpravu

Undo a Redo fungují globálně napříč vrstvami. Pokud se vrátí úprava provedená na jiné vrstvě, aplikace nastaví jako aktivní příslušnou vrstvu.

## 15. Ukládání projektu

Projekt se ukládá přes **Soubor → Uložit projekt** nebo klávesovou zkratkou **Ctrl+S**.

Pokud projekt ještě nemá zvolenou cestu, aplikace otevře dialog **Uložit projekt jako...**. Projekt se uloží jako `.zip`.

Možnosti v nabídce:

* **Uložit projekt** – uloží projekt na aktuální místo
* **Uložit projekt jako...** – uloží projekt jako nový soubor `.zip`
* **Zavřít projekt** – zavře aktuální projekt
* **Ukončit** – ukončí aplikaci

Pokud projekt obsahuje neuložené změny, aplikace se při zavírání zeptá, zda se mají změny uložit.

### Vytvoření nového návrhu z existujícího projektu

Z aktuálně otevřeného projektu lze vytvořit další nezávislý návrh rekonstrukce bez opakovaného načítání a zarovnávání vstupních obrazů.

V nabídce vyberte **Soubor → Vytvořit nový návrh z aktuálního projektu...**.

Aplikace nabídne dvě možnosti:

* **Ponechat malbu a hrany** – vytvoří úplnou kopii projektu včetně existujících pracovních vrstev.
* **Začít s čistou malbou** – zachová původní obraz, masku poškození, historickou kopii, paletu a textury, ale vytvoří prázdné vrstvy malby a hran. Všechny původně poškozené oblasti budou opět nevyplněné.

Následně zvolte název a umístění nového projektu.

Pokud původní projekt obsahuje neuložené změny, aplikace nabídne možnosti **Uložit**, **Neukládat** nebo **Zrušit**.

Při volbě **Neukládat** se původní soubor nezmění, ale nový návrh bude obsahovat i aktuální neuložené úpravy.

Po úspěšném vytvoření se nový návrh automaticky otevře a aplikace zobrazí jeho název.

Každý návrh je samostatný ZIP projekt. Úpravy provedené v novém návrhu neovlivní původní projekt.

## 16. Export výsledného obrazu

Výsledný obraz se exportuje přes **Soubor → Exportovat obraz…**.

Exportovaný obraz vždy obsahuje původní obraz jako podklad a na něm viditelné vrstvy malby a hran.

Viditelnost původního obrazu na plátně export neovlivňuje.
Historická kopie se do výsledného obrazu nikdy nezahrnuje, ani když je právě viditelná na plátně.

Skryté pracovní vrstvy malby a hran se do exportu nezahrnují.

Podporované formáty exportu:

* TIFF
* PNG
* JPEG

## 17. Export PDF reportu

PDF report se exportuje přes **Soubor → Exportovat report…**.

Před vytvořením reportu se otevře dialog, kde lze vyplnit volitelné údaje:

* jméno restaurátora
* název díla
* autor díla
* poznámky

Report obsahuje:

* základní údaje o projektu
* datum vytvoření reportu
* volitelné poznámky
* původní obraz
* masku poškození
* aktuální výsledný stav
* zbývající masku poškození
* statistiku pokrytí poškozených míst
* samostatné pracovní vrstvy
* historickou kopii jako samostatnou referenční vrstvu, pokud je v projektu načtena

Výsledný obraz v reportu se vytváří z původního obrazu a viditelných pracovních vrstev. Historická kopie je zdokumentována samostatně a není součástí výsledné rekonstrukce.

## 18. Klávesové zkratky

### Projekt

* **Ctrl+N** – nový projekt z obrázku
* **Ctrl+O** – otevřít projekt
* **Ctrl+S** – uložit projekt
* **Ctrl+Shift+S** – uložit projekt jako
* **Ctrl+W** – zavřít projekt
* **Ctrl+Q** – ukončit aplikaci

### Úpravy

* **Ctrl+Z** – zpět
* **Ctrl+Y** – znovu
* **Ctrl+Shift+Z** – znovu
* **+** nebo **=** – zvětšit štětec
* **-** – zmenšit štětec

### Nástroje

* **B** – Štětec
* **E** – Guma
* **D** – Rozmazání
* **F** – Výplň
* **S** – Vybrat
* **L** – Laso
* **G** – Hrana
* **M** – Zjemnit hranu
* **I** – Pipeta

## 19. Doporučený pracovní postup

Doporučený postup práce:

1. Vytvořit nový projekt z původního obrazu.
2. Načíst a zarovnat masku poškození.
3. Zkontrolovat, zda zvýraznění poškození odpovídá obrazu.  
    Případně použít ColorChecker korekci.
4. Pokud je dostupná historická kopie, načíst ji, zarovnat s původním obrazem a podle potřeby používat jako referenci.
5. Podle potřeby vytvořit nové vrstvy malby.
6. Větší nebo logicky oddělené poškozené oblasti rozdělit hranami.
7. Menší místa doplnit automatickou výplní nebo ručně.
8. Větší oblasti doplnit výplní, texturou nebo externím algoritmem.
9. Ostré přechody upravit nástroji Rozmazání nebo Zjemnit hranu.
10. Průběžně ukládat projekt.
11. Nakonec exportovat výsledný obraz nebo PDF report.

Pro různé varianty doplnění se doporučuje používat více vrstev malby. Vrstvy lze zobrazovat a skrývat a měnit jejich průhlednost, což usnadňuje porovnávání různých návrhů.

Při porovnávání více variant lze vytvářet samostatné návrhy z existujícího projektu. Každý návrh může obsahovat jinou rekonstrukci, přičemž všechny používají stejný původní obraz, masku a zarovnanou historickou kopii.

## 20. Časté problémy

### Nástroj nekreslí

Zkontrolujte, zda je aktivní vrstva typu **Malba**. Většina nástrojů nemůže kreslit do původního obrazu, historické kopie ani do vrstvy hran.

Také zkontrolujte, zda klikáte do oblasti určené maskou poškození. Nástroje jsou omezeny na poškozená místa.

### Výplň se neaplikuje

Oblast už může být na aktivní vrstvě vyplněná. Zkuste vybrat jinou vrstvu malby nebo vytvořit novou vrstvu.

### Nejsou vidět poškozená místa

Zkontrolujte, zda je zapnutá možnost **Zobrazení → Zobrazit poškozené oblasti**. Průhlednost zvýraznění lze upravit posuvníkem v nabídce **Zobrazení**.

Pokud je doplnění ve vrstvě malby skryté, může se poškození ve zvýraznění znovu zobrazovat, protože aplikace počítá pouze s aktuálně viditelnými vrstvami.

### Aplikace je při velkém obrazu pomalejší

Velké obrazy TIFF nebo velké masky mohou zpomalit výběr oblastí, výplň nebo externí algoritmy. Při rozsáhlejších úpravách je vhodné projekt průběžně ukládat.

### Historická kopie se nezobrazuje

Zkontrolujte, zda byla historická kopie načtena a zda je její vrstva v panelu **Vrstvy** viditelná.

Pokud je viditelný také původní obraz, historická kopie se zobrazuje pouze v místech označených původní maskou poškození.

Pro zobrazení historické kopie na celém plátně skryjte vrstvu **Původní obraz**.

### Historická kopie obsahuje prázdná místa

Prázdné oblasti vzniklé při zarovnání nebo úpravě kopie mohou zůstat průhledné. Při realistickém doplňování se tato místa automaticky nahradí původním obrazem.

Pokud potřebujete zachovat průhlednost také ve vstupním souboru historické kopie, použijte formát podporující alfa kanál, například PNG.
