# RePaint – užívateľská dokumentácia

## Obsah

* [Inštalácia a spustenie](#inštalácia-a-spustenie)
* [1. Vytvorenie nového projektu](#1-vytvorenie-nového-projektu)
* [2. Zarovnanie masky poškodenia](#2-zarovnanie-masky-poškodenia)
* [3. Otvorenie existujúceho projektu](#3-otvorenie-existujúceho-projektu)
* [4. Pracovné prostredie](#4-pracovné-prostredie)
* [5. Ovládanie obrazu](#5-ovládanie-obrazu)
* [6. Vrstvy](#6-vrstvy)
* [7. Maska poškodenia a zvýraznenie poškodených miest](#7-maska-poškodenia-a-zvýraznenie-poškodených-miest)
* [8. Paleta farieb](#8-paleta-farieb)
* [9. Materiály a nastavenia štetca](#9-materiály-a-nastavenia-štetca)
* [10. Textúry](#10-textúry)
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
* [12. Externé algoritmy](#12-externé-algoritmy)

  * [Realistické doplnění](#realistické-doplnění)
  * [Texturové doplnění](#texturové-doplnění)
* [13. ColorChecker korekcia](#13-colorchecker-korekcia)
* [14. Undo a Redo](#14-undo-a-redo)
* [15. Ukladanie projektu](#15-ukladanie-projektu)
* [16. Export výsledného obrazu](#16-export-výsledného-obrazu)
* [17. Export PDF reportu](#17-export-pdf-reportu)
* [18. Klávesové skratky](#18-klávesové-skratky)
* [19. Odporúčaný pracovný postup](#19-odporúčaný-pracovný-postup)
* [20. Časté problémy](#20-časté-problémy)

## Inštalácia a spustenie

Aplikáciu je možné používať dvoma spôsobmi.

### Inštalácia pomocou inštalátora

Pre bežných používateľov je určený súbor:

```text
RePaint-Setup-1.0.1.exe
```

Inštalátor je určený pre 64-bitový operačný systém Windows. Po jeho spustení postupujte podľa krokov sprievodcu. Aplikácia sa nainštaluje do používateľského priečinka, pridá sa do ponuky Štart a voliteľne je možné vytvoriť aj odkaz na pracovnej ploche.

Nainštalovaná verzia už obsahuje Python, potrebné knižnice aj lokálny textúrový algoritmus. Používateľ preto nemusí nič ďalšie inštalovať.

Pri prvom použití realistického dopĺňania aplikácia vyžiada endpoint URL a API kľúč vzdialenej služby. Údaje sa uložia do systémového úložiska prihlasovacích údajov. Neskôr ich je možné zmeniť cez **Nastavení → Remote realistické doplnění...**.

### Spustenie zo zdrojového kódu

Na spustenie zo zdrojov je potrebný Python 3.13 a Git.

```powershell
git clone https://gitlab.mff.cuni.cz/teaching/nprg045/ikudov/pohankova-katarina.git
cd pohankova-katarina\rp_restore_app

python3 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python app.py
```

Po aktivovaní virtuálneho prostredia sa používa príkaz `python`, ktorý odkazuje na interpreter z daného prostredia. Inštalácia zo zdrojov môže vyžadovať oprávnenie na prístup k repozitárom externých balíkov uvedených v súbore `requirements.txt`.

## 1. Vytvorenie nového projektu

Nový projekt je možné vytvoriť z úvodnej obrazovky tlačidlom **Nový projekt** alebo cez menu **Soubor → Nový projekt z obrázku...**.

Pri vytváraní projektu sa najprv vyberie pôvodný obraz. Podporované sú bežné obrazové formáty, napríklad PNG, JPG, JPEG, TIFF alebo TIF.

Po výbere obrazu je možné vybrať aj masku poškodenia. Maska určuje, ktoré časti obrazu sú poškodené a kde je možné aplikovať nástroje na dopĺňanie. Ak masku nechcete použiť, dialóg na výber masky je možné zavrieť a pokračovať bez nej.

Ak je maska vybraná, aplikácia otvorí dialóg na jej zarovnanie s pôvodným obrazom.

## 2. Zarovnanie masky poškodenia

Pri zarovnávaní masky sa vyberajú zodpovedajúce body na pôvodnom obraze a na maske. Cieľom je určiť, ako sa má maska transformovať, aby presne sedela na obraz.

Postup:

1. Kliknite na bod na pôvodnom obraze.
2. Kliknite na zodpovedajúci bod na maske.
3. V ďalšom okne sa zobrazí zväčšený výrez oboch miest.
4. Upresnite bod na obraze aj na maske čo najpresnejšie.
5. Potvrďte výber bodu.
6. Rovnakým spôsobom pridajte ďalšie body.

Na zarovnanie treba vybrať aspoň štyri páry bodov. Je možné vybrať aj viac bodov, ale počet je obmedzený. Čím presnejšie sú body zvolené a čím viacej párove je zvolených, tým lepšie bude maska sedieť na pôvodný obraz.

V dialógu je možné vymazať posledný bod alebo všetky body a začať znovu.

## 3. Otvorenie existujúceho projektu

Existujúci projekt sa otvára cez **Soubor → Otevřít projekt...** alebo tlačidlom **Otevřít projekt** na úvodnej obrazovke.

Projekt sa ukladá ako súbor `.zip`. Tento súbor obsahuje vrstvy, masky, paletu, textúry a ďalšie zvolené nastavenia potrebné na pokračovanie práce.

Na úvodnej obrazovke sa zobrazuje aj zoznam naposledy otvorených projektov. Projekt zo zoznamu je možné otvoriť dvojklikom.

## 4. Pracovné prostredie

Po otvorení projektu sa zobrazí hlavné pracovné prostredie aplikácie. V strede je obraz, na ktorom sa bude pracovať. Okolo neho sú panely a lišta nástrojov.

Hlavné časti prostredia sú:

* ľavá lišta nástrojov,
* panel **Vrstvy**
* panel **Paleta**
* panel **Externé algoritmy**
* panel **Hrany**
* panel **Materiály**
* horné menu aplikácie
* stavový riadok v dolnej časti okna

Panely je možné zobraziť alebo skryť cez menu **Zobrazení**. Ak panel zavriete, dá sa neskôr znovu otvoriť cez toto menu.

## 5. Ovládanie obrazu

Obraz je možné približovať, odďaľovať a posúvať.

Základné ovládanie:

* koliesko myši približuje alebo odďaľuje obraz
* pravé alebo stredné tlačidlo myši slúži na posun obrazu
* kreslenie a používanie nástrojov sa robí ľavým tlačidlom myši

Pri otvorení projektu sa obraz automaticky prispôsobí veľkosti okna. Priblíženie je možné zvyšovať až na 100-krát.

## 6. Vrstvy

Aplikácia pracuje s viacerými typmi vrstiev:

* **Původní obraz** – pôvodný načítaný obraz, nedá sa meniť
* **Malba** – pracovné vrstvy, do ktorých sa dopĺňajú poškodené miesta
* **Hrany** – vrstva s hranami, ktoré rozdeľujú poškodenie na samostatné oblasti

Najčastejšie sa pracuje s vrstvami typu **Malba**. Do nich sa kreslí štetcom, aplikuje výplň, textúra, rozmazanie alebo výsledky algoritmov.

V paneli **Vrstvy** je možné:

* vybrať aktívnu vrstvu
* zobraziť alebo skryť vrstvu ikonou vľavo
* vytvoriť novú vrstvu malby
* premenovať vrstvu
* odstrániť vrstvu malby
* meniť priehľadnosť aktívnej vrstvy
* zobraziť náhľad aktívnej vrstvy

Odstraňovať je možné iba vrstvy malby.

### Náhľad vrstvy

Panel **Vrstvy** obsahuje náhľad aktívnej vrstvy. Tento náhľad pomáha skontrolovať, čo sa nachádza priamo na danej vrstve bez toho, aby bolo potrebné skrývať ostatné vrstvy.

Kliknutím na náhľad vrstvy sa zobrazí zväčšený náhľad priamo v hlavnej ploche. Opätovným kliknutím na zmenšený náhľad sa náhľad skryje a aplikácia sa vráti k bežnému zobrazeniu obrazu.

## 7. Maska poškodenia a zvýraznenie poškodených miest

Maska poškodenia určuje, ktoré pixely obrazu sa považujú za poškodené. Väčšina nástrojov je obmedzená tak, aby pracovala iba v týchto miestach.

Poškodené miesta je možné zvýrazniť cez **Zobrazení → Zobrazit poškoděné oblasti**. V tom istom menu sa nachádza aj posuvník na nastavenie priehľadnosti zvýraznenia.

Zvýraznenie zodpovedá aktuálne viditeľným vrstvám. Ak je nejaká vrstva malby skrytá, aplikácia ju pri zobrazení zostávajúceho poškodenia neberie do úvahy.

## 8. Paleta farieb

Panel **Paleta** slúži na výber aktuálnej farby a na ukladanie často používaných farieb.

V paneli je možné:

* zmeniť aktuálnu farbu
* pridať aktuálnu farbu do palety
* vybrať farbu z palety
* odstrániť farbu z palety

Ak sa do palety pridáva farba, ktorá už v palete je, nepridá sa duplicitne.

Aktuálna farba sa používa pri štetci, výplni a pri farebnom nastavení textúry.

## 9. Materiály a nastavenia štetca

Panel **Materiály** obsahuje nastavenia pre štetec, gumu, rozmazanie a textúry.

Pre štetec, gumu a rozmazanie je možné nastaviť:

* veľkosť štetca
* tvrdosť
* krytie
* hustotu
* či sa má ťah vrstviť
* silu rozmazania
* zdroj rozmazania

Hodnota **Tvrdost** ovplyvňuje okraj stopy štetca. Nižšia tvrdosť znamená mäkší okraj, vyššia tvrdosť ostrejší okraj.

Hodnota **Krytí** určuje maximálnu nepriehľadnosť stopy.

Hodnota **Hustota** ovplyvňuje, ako rýchlo sa farba alebo mazanie v ťahu nanáša.

Možnosť **Vrstvit v tahu** určuje, či sa jeden ťah môže počas ťahania myšou postupne zosilňovať (až do hodnoty krytí).

## 10. Textúry

V paneli **Materiály** je možné prepnúť režim zo **Štětec** na **Textura**. V textúrovom režime sa namiesto jednoliatej farby používa vybraná textúra.

Pri textúrach je možné nastaviť:

* vybranú textúru
* hustotu textúry
* silu textúry
* rotáciu
* štýl textúry
* deformáciu šírky a výšky

Dostupné sú dva štýly textúry:

* **Transparentní** – jas textúry určuje priehľadnosť vzoru, ktorý je zafarbený aktuálnou farbou
* **Barevná** – jas textúry vytvára svetlejšie a tmavšie odtiene aktuálnej farby

Textúry vytvorené externým textúrovým algoritmom si zachovávajú vlastnú vygenerovanú farebnosť. Pri nich sa štýl **Transparentní/Barevná** nepoužíva a ich farby sa upravujú samostatne tlačidlom **Upravit barvy…**.

V časti **Deformace textury** je možné zmeniť šírku a výšku textúry. Deformácia sa prejaví v náhľade a pri ďalšom použití textúry.

Ak chcete aktuálne deformovanú textúru používať opakovane, stlačte **Přidat mezi textury**. Aplikácia vytvorí novú textúru odvodenú od pôvodnej a pridá ju medzi ostatné textúry. Ak už rovnaká deformovaná verzia existuje, nepridá sa duplicitne.

Do projektu je možné pridať aj vlastnú textúru zo súboru.

## 11. Nástroje

Nástroje sa vyberajú v ľavej lište. Aktívny nástroj je zvýraznený.

### Štětec

Nástroj **Štětec** slúži na ručné dopĺňanie poškodených miest farbou alebo textúrou. Používa aktuálnu farbu z palety a nastavenia z panelu **Materiály**.

Kreslí sa ťahaním ľavým tlačidlom myši.

Štetec je možné použiť iba na vrstve malby. Ak je aktívna iná vrstva, aplikácia sa snaží automaticky prepnúť na vhodnú vrstvu malby.

---

### Guma

Nástroj **Guma** slúži na mazanie obsahu z vrstvy malby. Maže iba to, čo bolo doplnené do pracovnej vrstvy, nie pôvodný obraz.

Guma používa veľkosť, tvrdosť, krytie a hustotu z panelu **Materiály**.

---

### Rozmazání

Nástroj **Rozmazání** slúži na jemné rozmazanie už doplnených častí. Pracuje v poškodenej oblasti a používa nastavenia z panelu **Materiály**.

V paneli je možné zvoliť zdroj rozmazania:

* **Vrstva malby** – rozmazáva sa iba obsah aktívnej vrstvy malby
* **Původní obraz + vrstva malby** – pri výpočte sa berie do úvahy aj pôvodný obraz pod vrstvou

Tento nástroj je vhodný napríklad na zjemnenie ručne doplnených miest alebo na úpravu príliš ostrých prechodov.

--- 

### Výplň

Nástroj **Výplň** vyplní poškodený región aktuálnou farbou alebo textúrou.

Ak nie je vybraná žiadna oblasť, stačí kliknúť do poškodeného regiónu. Aplikácia vyplní celý región, ktorý je určený maskou poškodenia a prípadnými hranami.

Ak je aktívny výber, výplň sa aplikuje na vybrané oblasti.

Výplň sa aplikuje iba do tých miest, ktoré sú na aktívnej vrstve malby ešte nevyplnené.

---

### Vybrat

Nástroj **Vybrat** slúži na výber poškodených regiónov.

Kliknutím sa vyberie jeden región. Podržaním klávesu **Ctrl** a kliknutím je možné pridávať ďalšie regióny do výberu alebo ich z výberu odoberať.

Vybrané oblasti sú zobrazené šedým zvýraznením.

Výber sa používa napríklad pred spustením textúrového algoritmu alebo pred hromadnou výplňou viacerých oblastí.

---

### Laso

Nástroj **Laso** slúži na výber viacerých poškodených regiónov ťahom myši. Počas ťahu sa kreslí obrys lasa. Po pustení tlačidla aplikácia vyberie poškodené regióny, ktoré sa nachádzajú vo vnútri nakresleného tvaru.

Ak pri použití lasa podržíte **Ctrl**, nový výber sa pridá k existujúcemu výberu.

Laso je vhodné vtedy, keď chcete rýchlo vybrať viac blízkych poškodených miest naraz.

---

### Hrana

Nástroj **Hrana** slúži na kreslenie hraníc v poškodených miestach. Hrany rozdeľujú poškodenie na menšie samostatné regióny, ktoré sa potom dajú vyplniť oddelene.

Hrany by sa mali kresliť iba tam, kde je potrebné rozdeliť poškodenú oblasť. Nie sú určené ako bežný kresliaci štetec.

Kreslenie hrany:

* ľavé tlačidlo myši kreslí hranu
* pravé tlačidlo myši alebo **Shift + ľavé tlačidlo** hranu maže

Farbu hrany a šírku zjemnenia je možné nastaviť v paneli **Hrany**.

---

### Zjemnit hranu

Nástroj **Zjemnit hranu** slúži na zjemnenie prechodu medzi dvoma regiónmi oddelenými už nakreslenou hranou. Používa sa vtedy, keď hrana rozdelila poškodenie na dve časti, obe strany sú už vyplnené a medzi nimi zostal príliš ostrý prechod.

Pri použití nástroja prejdite ľavým tlačidlom cez existujúcu hranu. Aplikácia odstráni zasiahnutú časť hrany a vytvorí mäkší prechod medzi doplnenými oblasťami.

Nástroj funguje len tam, kde existuje nakreslená hrana. Ak nie je čo zjemniť, aplikácia zobrazí upozornenie.

Šírka zjemnenia sa nastavuje v paneli **Hrany** hodnotou **Zjemnění (px)**.

---

### Pipeta

Nástroj **Pipeta** slúži na odobratie farby z obrazu. Kliknutím na obraz sa vybraná farba nastaví ako aktuálna farba v palete.

Pipeta je užitočná pri ručnom dopĺňaní, keď chcete nadviazať na farby v okolí poškodenia.

---

### Auto-výplň malých oblastí

Nástroj **Auto-výplň malých oblastí** automaticky vyplní malé poškodené regióny podľa nastavenej maximálnej veľkosti v pixeloch.

Vedľa nástroja je posuvník a číselná hodnota, ktorou sa nastavuje prah veľkosti oblasti. Po zmene hodnoty aplikácia zvýrazní kandidátne oblasti tyrkysovou farbou.

Kliknutím na zvýraznenú oblasť ju môžete z automatickej výplne vyradiť alebo ju znovu zaradiť.

Po stlačení tlačidla **Auto-výplň malých oblastí** aplikácia vyplní vybrané malé oblasti farbou vypočítanou z ich okolia.

Ak je aktívny ručný výber oblastí, auto-výplň sa aplikuje na tento výber.

Toto tlačidlo treba stlačiť až na konci, pri vyplnení už vybraných oblastí (nebude to ako aktívny nástroj).

---

## 12. Externé algoritmy

Panel **Externé algoritmy** obsahuje nástroje na automatické dopĺňanie poškodených častí pomocou externých algoritmov.

* **Realistické doplnění**
* **Texturové doplnění**

### Realistické doplnění

Realistické doplnenie slúži na automatické dogenerovanie poškodených miest v zvolenom obdĺžnikovom okne. Algoritmus sa vykonáva na vzdialenej službe, preto vyžaduje internetové pripojenie a platný API kľúč.

Pri prvom použití aplikácia vyžiada prístupové údaje. Neskôr ich je možné upraviť cez **Nastavení → Remote realistické doplnění...**.

Po stlačení tlačidla **Realistické doplnění** sa otvorí dialóg, v ktorom je možné zvoliť okno dvoma spôsobmi:

* použiť spoločné ohraničenie aktuálneho výberu
* vybrať okno ručne priamo v obraze

Maximálna veľkosť okna je 1440 × 1440 pixelov. Okno musí obsahovať aspoň časť zostávajúcej masky poškodenia.

K dispozícii sú dva režimy:

* **Základní** – používa výrez pôvodného obrazu a je určený na bežné dopĺňanie poškodení,
* **Vedené podle náčrtu** – používa aktuálny zložený obraz vrátane prípadného ručného náčrtu. Vodiace čiary by mali byť tmavé a tenké, ideálne približne jeden pixel. Tento režim je výrazne pomalší.

V základnom režime je možné nastaviť hodnotu **Míra dogenerování**. Nižšia hodnota viac zachováva pôvodnú štruktúru pod maskou, zatiaľ čo hodnota 1 znamená úplné dogenerovanie. Ak pod maskou nie sú použiteľné pôvodné pixely, odporúča sa nastaviť hodnotu 1.

Voliteľná hodnota **seed** umožňuje zopakovať výpočet s rovnakým náhodným nastavením.

Ak je aktívny výber regiónov, výsledok sa aplikuje iba v tomto výbere. Ak výber neexistuje, použije sa zostávajúca maska poškodenia vo zvolenom okne. Výsledok sa vloží do aktívnej vrstvy malby iba na miestach, ktoré na nej ešte nie sú vyplnené.

Model realistického dopĺňania je primárne určený na reštaurovanie diel Albrechta Dürera.

### Texturové doplnění

Textúrové doplnenie používa lokálny algoritmus na vytvorenie textúrovaného obsahu. Dialóg ponúka dva režimy výstupu:

* **Doplnit vybranou oblast obrazu** – výsledok sa vloží priamo do vybraných poškodených regiónov,
* **Vygenerovat samostatnou texturu a přidat ji do materiálů** – vytvorí samostatný textúrový obraz, ktorý sa pridá medzi textúry aktuálneho projektu.

Na priame doplnenie obrazu treba najskôr vybrať poškodenú oblasť nástrojom **Vybrat** alebo **Laso**. Bez aktívneho výberu je možné stále vytvoriť samostatnú textúru a pridať ju do panelu Materiály.

V dialógu je možné nastaviť:

* typ modelu textúry
* jednu až tri farby
* silu každej farebnej vrstvy
* mierku v osiach X a Y
* hustotu v osiach X a Y pri modeloch, ktoré ju podporujú
* rotáciu
* celkovú mierku
* nepriehľadné alebo priehľadné pozadie
* jas nepriehľadného pozadia
* seed
* šírku a výšku samostatne generovanej textúry

Pri každom modeli sa zobrazuje jeho vstupný náhľad. Tlačidlom **Vygenerovat náhled** je možné vytvoriť aj zmenšený náhľad výslednej textúry podľa aktuálnych parametrov.

Pri dopĺňaní vybranej oblasti sa výsledok vloží do aktívnej vrstvy malby iba v miestach aktuálneho výberu, ktoré sú stále poškodené a na danej vrstve ešte neboli vyplnené.

Samostatne vygenerovaná textúra sa pridá do panelu Materiály a zachová si vlastné vygenerované farby. Je možné ju používať pomocou textúrového štetca alebo výplne. Pri jej výbere sa zobrazia pôvodné farby a ich sily; tlačidlom **Upravit barvy…** je možné farby zmeniť a textúru znovu vygenerovať.

## 13. ColorChecker korekcia

Aplikácia podporuje farebnú korekciu pomocou ColorChecker tabuľky. Dialóg sa otvára cez **Úpravy → ColorChecker...**.

Postup:

1. Načítajte kalibračnú fotografiu s ColorChecker tabuľkou
2. Kliknite na štyri rohy tabuľky v poradí uvedenom v dialógu
3. Stlačte **Spočítat korekci**
4. Ak je korekcia vypočítaná, použite ju tlačidlom **Použít**

Po výpočte korekcie je možné jej zobrazenie zapnúť alebo vypnúť cez **Zobrazení → Použít ColorChecker korekci**.

Kalibračná fotografia by mala byť vytvorená v rovnakých svetelných podmienkach ako pracovná fotografia diela. Ideálne je nafotiť ju hneď pri dokumentácii diela.

Odporúča sa rozhodnúť o použití ColorChecker korekcie na začiatku práce. Ak sa korekcia zapne až po ručnom dopĺňaní, môže sa zmeniť vzhľad už doplnených farieb.

## 14. Undo a Redo

Aplikácia podporuje spätné vrátenie a opätovné vykonanie úprav.

* **Úpravy → Zpět** alebo **Ctrl+Z** vráti poslednú úpravu
* **Úpravy → Znovu** alebo **Ctrl+Y** / **Ctrl+Shift+Z** obnoví vrátenú úpravu

Undo a Redo fungujú globálne naprieč vrstvami. Ak sa vráti úprava, ktorá bola vykonaná na inej vrstve, aplikácia nastaví ako aktívnu príslušnú vrstvu.

## 15. Ukladanie projektu

Projekt sa ukladá cez **Soubor → Uložit projekt** alebo klávesovou skratkou **Ctrl+S**.

Ak projekt ešte nemá zvolenú cestu, aplikácia otvorí dialóg **Uložit projekt jako...**. Projekt sa uloží ako `.zip`.

Možnosti v menu:

* **Uložit projekt** – uloží projekt na aktuálne miesto
* **Uložit projekt jako...** – uloží projekt ako nový `.zip` súbor
* **Zavřít projekt** – zavrie aktuálny projekt
* **Ukončit** – ukončí aplikáciu

Ak projekt obsahuje neuložené zmeny, aplikácia sa pri zatváraní opýta, či sa majú zmeny uložiť.

## 16. Export výsledného obrazu

Výsledný obraz sa exportuje cez **Soubor → Exportovat obraz…**.

Exportuje sa aktuálny výsledok podľa viditeľných vrstiev. Ak je niektorá vrstva skrytá, do exportovaného obrazu sa nezahrnie.

Podporované formáty exportu sú:

* TIFF
* PNG
* JPEG

## 17. Export PDF reportu

PDF report sa exportuje cez **Soubor → Exportovat report…**.

Pred vytvorením reportu sa otvorí dialóg, kde je možné vyplniť voliteľné údaje:

* meno reštaurátora
* názov diela
* autor diela
* poznámky

Report obsahuje:

* základné údaje o projekte
* dátum vytvorenia reportu
* voliteľné poznámky
* pôvodný obraz
* masku poškodenia
* aktuálny výsledný stav
* zostávajúcu masku poškodenia
* štatistiku pokrytia poškodených miest
* samostatné pracovné vrstvy

## 18. Klávesové skratky

### Projekt

* **Ctrl+N** – nový projekt z obrázku
* **Ctrl+O** – otvoriť projekt
* **Ctrl+S** – uložiť projekt
* **Ctrl+Shift+S** – uložiť projekt ako
* **Ctrl+W** – zavrieť projekt
* **Ctrl+Q** – ukončiť aplikáciu

### Úpravy

* **Ctrl+Z** – späť
* **Ctrl+Y** – znovu
* **Ctrl+Shift+Z** – znovu
* **+** alebo **=** – zväčšiť štetec
* **-** – zmenšiť štetec

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

## 19. Odporúčaný pracovný postup

Odporúčaný postup práce je:

1. Vytvoriť nový projekt z pôvodného obrazu.
2. Načítať a zarovnať masku poškodenia.
3. Skontrolovať, či zvýraznenie poškodenia sedí s obrazom.  
    Prípadne použiť Colorchecker korekciu.
4. Podľa potreby vytvoriť nové vrstvy malby.
5. Väčšie alebo logicky oddelené poškodenia rozdeliť hranami.
6. Menšie miesta doplniť auto-výplňou alebo ručne.
7. Väčšie oblasti doplniť výplňou, textúrou alebo externým algoritmom.
8. Ostré prechody upraviť nástrojmi Rozmazání alebo Zjemnit hranu.
9. Priebežne ukladať projekt.
10. Na konci exportovať výsledný obraz alebo PDF report.

Odporúča sa používať viac vrstiev malby pre rôzne varianty doplnenia. Vrstvy je možné zobrazovať a skrývať a meniť ich priehľadnosť, čo uľahčuje porovnávanie rôznych návrhov.

## 20. Časté problémy

### Nástroj nekreslí

Skontrolujte, či je aktívna vrstva typu **Malba**. Väčšina nástrojov nemôže kresliť do pôvodného obrazu ani do vrstvy hrán.

Tiež skontrolujte, či klikáte do oblasti určenej maskou poškodenia. Nástroje sú obmedzené na poškodené miesta.

### Výplň sa neaplikuje

Oblasť už môže byť na aktívnej vrstve vyplnená. Skúste vybrať inú vrstvu malby alebo vytvoriť novú vrstvu.

### Nie je vidieť poškodené miesta

Skontrolujte, či je zapnuté **Zobrazení → Zobrazit poškoděné oblasti**. Priehľadnosť zvýraznenia je možné upraviť posuvníkom v menu **Zobrazení**.

Ak je doplnenie na vrstve malby skryté, poškodenie sa môže v zvýraznení znovu zobrazovať, pretože aplikácia počíta iba s aktuálne viditeľnými vrstvami.

### Aplikácia je pri veľkom obraze pomalšia

Veľké TIFF obrazy alebo veľké masky môžu spomaliť výber oblastí, výplň alebo externé algoritmy. Pri rozsiahlejších úpravách je vhodné projekt priebežne ukladať.
