# RePaint – programátorská dokumentácia

**Language / Jazyk:** [English](developer_documentation.en.md) | [Čeština](developer_documentation.cs.md) | [Slovenčina](developer_documentation.md)

## Obsah

* [1. Základná štruktúra projektu](#1-základná-štruktúra-projektu)
* [2. Hlavné použité knižnice](#2-hlavné-použité-knižnice)
* [3. Dátový model projektu](#3-dátový-model-projektu)
* [4. Vrstvy](#4-vrstvy)
* [5. ProjectController](#5-projectcontroller)
* [6. Canvas](#6-canvas)
* [7. Nástroje](#7-nástroje)
* [8. Panely](#8-panely)
* [9. Ukladanie a načítanie projektu](#9-ukladanie-a-načítanie-projektu)
* [10. Načítanie a ukladanie obrázkov](#10-načítanie-a-ukladanie-obrázkov)
* [11. Maska poškodenia a regióny](#11-maska-poškodenia-a-regióny)
* [12. Undo/Redo](#12-undoredo)
* [13. Textúrový štetec](#13-textúrový-štetec)
* [14. Auto-výplň](#14-auto-výplň)
* [15. Hrany a zjemnenie hrán](#15-hrany-a-zjemnenie-hrán)
* [16. Rozmazanie](#16-rozmazanie)
* [17. Externé algoritmy](#17-externé-algoritmy)
* [18. ColorChecker korekcia](#18-colorchecker-korekcia)
* [19. Zarovnanie masky a historickej kópie](#19-zarovnanie-masky-a-historickej-kópie)
* [20. PDF report](#20-pdf-report)
* [21. Nastavenia aplikácie](#21-nastavenia-aplikácie)
* [22. Typický tok práce v kóde](#22-typický-tok-práce-v-kóde)
* [23. Zhrnutie](#23-zhrnutie)


Aplikácia je napísaná v jazyku Python a používa knižnicu PySide6 na grafické používateľské rozhranie. Na prácu s obrazovými dátami sa používa najmä NumPy, Pillow a OpenCV.

## 1. Základná štruktúra projektu

Hlavný balík aplikácie sa nachádza v priečinku `rp_restore`.

Zjednodušená štruktúra:

```text
rp_restore_app/rp_restore/
├── config/
│   └── settings.py
├── core/
│   ├── algorithm_runner.py
│   ├── auto_fill.py
│   ├── color_correction.py
│   ├── edge_blend.py
│   ├── history.py
│   ├── layers.py
│   ├── mask_alignment.py
│   ├── project_model.py
│   ├── regions.py
│   ├── remote_restoration_config.py
│   ├── selection.py
│   └── texture_brush.py
├── gui/
│   ├── main_window.py
│   ├── project_controller.py
│   ├── mask_alignment_dialog.py
│   ├── colorchecker_dialog.py
│   ├── realistic_fill_dialog.py
│   ├── remote_restoration_settings_dialog.py
│   ├── texture_fill_dialog.py
│   ├── start_screen_widget.py
│   ├── canvas/
│   ├── panels/
│   └── tools/
├── io/
│   ├── image_io.py
│   └── project_storage.py
├── report/
│   ├── pdf_report.py
│   └── report_dialog.py
└── resources/
```

Kód je rozdelený na niekoľko vrstiev:

* `core` obsahuje dátový model a výpočtovú logiku
* `gui` obsahuje grafické rozhranie a ovládanie aplikácie
* `gui/tools` obsahuje jednotlivé nástroje
* `gui/panels` obsahuje bočné panely aplikácie
* `io` rieši načítanie a ukladanie obrázkov a projektov
* `report` rieši generovanie PDF reportu
* `config` obsahuje nastavenia aplikácie
* `resources` obsahuje predvolené textúry, náhľady modelov a grafické zdroje aplikácie

## 2. Hlavné použité knižnice

Aplikácia používa najmä tieto externé knižnice a balíky:

* `PySide6` – grafické používateľské rozhranie
* `numpy` – reprezentácia a úprava obrazových dát
* `Pillow` – načítanie, prevod a ukladanie obrázkov
* `opencv-python` / `cv2` – vybrané obrazové operácie
* `reportlab` – generovanie PDF reportov
* `keyring` – ukladanie endpointu a API kľúča vzdialenej služby do systémového úložiska prihlasovacích údajov
* `painting_inpaint.remote` – klient vzdialeného realistického dopĺňania
* `texture_infill` – lokálne spúšťaný textúrový algoritmus

Textúrový algoritmus sa používa ako nainštalovaný Python balík. Nie je uložený v priečinku zdrojového kódu aplikácie. Jeho modelové súbory sú súčasťou balíka `texture_infill`.

## 3. Dátový model projektu

Hlavná trieda dátového modelu je `Project` v súbore:

```
rp_restore/core/project_model.py
```

Trieda `Project` reprezentuje jeden otvorený projekt. Obsahuje:

* názov projektu
* cestu k pôvodnému obrazu
* pôvodný pracovný obraz
* zoznam vrstiev
* pôvodnú masku poškodenia
* masky vyplnenia poškodenia
* historickú kópiu obrazu
* paletu farieb
* nastavenia štetca
* textúry
* nastavenia ColorChecker korekcie
* undo/redo manažér

Dôležité metódy triedy `Project`:

* `add_layer()` – pridanie vrstvy
* `remove_layer()` – odstránenie vrstvy typu Paint
* `get_background_layer()` – získanie pôvodného obrazu
* `get_paint_layers()` – získanie všetkých Paint vrstiev
* `get_edge_layer()` – získanie vrstvy hrán
* `composited_image()` – poskladanie výsledného obrazu
* `composited_region()` – poskladanie iba časti obrazu
* `set_damage_masks()` – nastavenie masky poškodenia
* `get_damage_remaining_mask()` – získanie zostávajúceho poškodenia
* `get_selection_from_click()` – výber regiónu kliknutím
* `get_selections_from_polygon()` – výber regiónov pomocou lasa
* `sync_layer_filled_mask_from_alpha()` – zosynchronizovanie masky vyplnenia podľa alfa kanála vrstvy
* `get_reference_layer()` – získanie historickej kópie
* `composited_view_image()` – zostavenie RGBA obrazu pre hlavné plátno
* `composited_view_region()` – zostavenie RGBA výrezu plátna
* `realistic_input_region()` – príprava RGB vstupu realistického algoritmu podľa zvoleného podkladu
* `get_export_image()` – zostavenie finálneho obrazu s vynúteným pôvodným pozadím

Skladanie obrazu je rozdelené podľa účelu. Metódy `composited_view_image()` a `composited_view_region()` pripravujú RGBA obraz pre vykresľovanie na plátne.

Pôvodné metódy `composited_image()` a `composited_region()` pracujú s RGB kompozíciou pôvodného pozadia a pracovných vrstiev. Historická kópia sa do nich nezahrňuje.

Metóda `get_export_image()` používa `composited_image()` s parametrom `force_original_background=True`, čím zabezpečuje export pôvodného obrazu nezávisle od jeho viditeľnosti na plátne.

## 4. Vrstvy

Vrstvy sú definované v súbore:

```
rp_restore/core/layers.py
```

Používajú sa štyri typy vrstiev:

```python
class LayerRole(str, Enum):
    BACKGROUND = "background"
    REFERENCE = "reference"
    EDGE = "edge"
    PAINT = "paint"
```

Každá vrstva je reprezentovaná triedou `Layer`, ktorá obsahuje:

* `meta` – metadata vrstvy
* `image` – obrazové dáta vo formáte RGBA
* `damage_filled_mask` – informáciu o tom, ktoré poškodené pixely sú vyplnené na tejto vrstve

Metadata vrstvy sú uložené v triede `LayerMeta`. Obsahujú napríklad:

* interné ID vrstvy
* názov vrstvy
* typ vrstvy
* viditeľnosť
* priehľadnosť
* poradie vrstvy

Vrstvy používajú obrazové dáta ako NumPy pole tvaru:

```
(height, width, 4)
```

Typ dát je `uint8` a kanály sú v poradí RGBA.

Vrstva typu `REFERENCE` reprezentuje historickú kópiu obrazu. Ide o špeciálnu referenčnú vrstvu, ktorá nie je určená na kreslenie a neovplyvňuje masku vyplnených poškodených miest.

Podporuje vlastnú viditeľnosť a krytie rovnako ako ostatné vrstvy. Jej obrazové dáta obsahujú aj alfa kanál, ktorý umožňuje reprezentovať skutočne chýbajúce časti kópie.

Vrstva sa vytvorí pri načítaní historickej kópie. `LayersPanel.refresh_from_project()` zároveň nezobrazuje prázdne referenčné vrstvy zo starších projektov.

## 5. ProjectController

Najdôležitejšia riadiaca trieda aplikácie je:

```
rp_restore/gui/project_controller.py
```

Trieda `ProjectController` prepája dátový model s grafickým rozhraním. Väčšina používateľských akcií nakoniec prechádza cez controller.

Controller zodpovedá napríklad za:

* aktuálne otvorený projekt
* aktívnu vrstvu
* aktívny nástroj
* výber poškodených oblastí
* nastavenia štetca a textúr
* aktualizáciu canvasu
* aktualizáciu panelov
* spúšťanie algoritmov
* ukladanie a otváranie projektu
* export obrazu
* ColorChecker korekciu
* Undo/Redo
* zobrazenie hlášok používateľovi

Controller ďalej zabezpečuje načítanie a zarovnanie historickej kópie a vytváranie nových nezávislých návrhov.

Dôležité metódy:

* `load_reference_image()` – načítanie obrázka, otvorenie zarovnávacieho dialógu a vloženie kópie do projektu.
* `create_proposal_from_current_project()` – vytvorenie samostatného projektu s existujúcimi alebo prázdnymi pracovnými vrstvami.
* `run_realistic_fill_window()` – príprava vstupného okna a spustenie realistického doplnenia podľa vybraného podkladu.

Pri vytváraní nového návrhu sa aktuálny stav projektu najprv serializuje do dočasného ZIP súboru a následne sa načíta ako nový nezávislý objekt `Project`.

Pri čistom návrhu sa odstránia existujúce vrstvy `PAINT` a `EDGE`, vytvoria sa nové prázdne vrstvy a pôvodná maska poškodenia sa nastaví ako nevyplnená. Pôvodný obraz, historická kópia, paleta a textúry sa zachovajú.

Nový projekt sa uloží pod samostatným názvom a otvorí sa až po úspešnom uložení. Kontrola neuložených zmien pôvodného projektu sa vykonáva v `MainWindow.on_create_proposal_requested()`.

Typický tok udalosti je:

```
používateľ klikne do canvasu
→ ImageCanvasWidget prepočíta súradnice obrazovky na súradnice obrazu
→ ProjectController zavolá metódu aktívneho nástroja
→ nástroj upraví dáta v Project
→ ProjectController obnoví príslušnú časť canvasu a panelov
```

Pri úpravách aplikácie je dobré najskôr skontrolovať, či daná funkcionalita patrí do:

* modelu `Project`
* controlleru `ProjectController`
* samostatného nástroja v `gui/tools`
* panelu v `gui/panels`

## 6. Canvas

Canvas je implementovaný v súbore:

```
rp_restore/gui/canvas/image_canvas_widget.py
```

Trieda `ImageCanvasWidget` zobrazuje výsledný obraz, rieši zoom, posun obrazu a prevod súradníc medzi obrazovkou a obrazom.

Canvas sám nevykonáva zložité úpravy projektu. Slúži hlavne ako zobrazovací prvok a zdroj udalostí myši. Logika nástrojov je oddelená v triedach v priečinku `gui/tools`.

Zvýraznenie výberu je implementované pomocou pomocnej funkcie v:

```
rp_restore/gui/canvas/overlay_highlight.py
```

Hlavné plátno používa RGBA obraz zostavený metódami `Project.composited_view_image()` a `Project.composited_view_region()`.

Podklad závisí od viditeľnosti vrstiev `BACKGROUND` a `REFERENCE`. Ak sú obe viditeľné, historická kópia nahrádza pôvodný obraz iba v oblastiach určených `damage_original_mask`. Pri skrytom `BACKGROUND` sa viditeľná kópia používa na celom plátne.

Krytie referenčnej vrstvy sa aplikuje na jej alfa kanál bez primiešavania pôvodného pozadia v nahradených oblastiach.

Pri čiastočnom prekreslení plátna používa `ImageCanvasWidget.patch_region()` režim `QPainter.CompositionMode_Source`, aby nový RGBA výrez úplne nahradil predchádzajúce pixely.

## 7. Nástroje

Interaktívne nástroje sú v priečinku:

```
rp_restore/gui/tools/
```

Každý nástroj dedí zo základnej triedy `BaseTool`:

```
rp_restore/gui/tools/base_tool.py
```

Základná trieda definuje metódy:

* `on_mouse_press()`
* `on_mouse_move()`
* `on_mouse_release()`
* `get_cursor()`

Aktuálne nástroje:

* `BrushTool` – štetec a textúrový štetec
* `EraserTool` – guma
* `BlendTool` – rozmazanie
* `FillTool` – výplň regiónu
* `SelectionTool` – výber kliknutím
* `LassoTool` – výber lasom
* `EdgeTool` – kreslenie a mazanie hrán
* `EdgeBlendTool` – zjemnenie prechodu cez hranu
* `PipetteTool` – pipeta

Ak treba pridať nový nástroj, tak by to bolo takto:

1. Vytvoriť novú triedu v `gui/tools`
2. Zdediť z `BaseTool`
3. Implementovať reakcie na udalosti myši
4. Zaregistrovať nástroj v `MainWindow`
5. Doplniť prepnutie nástroja v `ProjectController.set_current_tool()`
6. Podľa potreby doplniť kurzor a panelové nastavenia

## 8. Panely

Bočné panely sa nachádzajú v priečinku:

```
rp_restore/gui/panels/
```

Hlavné panely:

* `LayersPanel` – zobrazenie a správa vrstiev
* `PalettePanel` – paleta farieb
* `MaterialsPanel` – nastavenia štetca, gumy, rozmazania a textúr
* `EdgeSettingsPanel` – nastavenia hrán
* `AlgorithmPanel` – spúšťanie externých algoritmov

Panely nepracujú priamo s dátovým modelom projektu, ale typicky komunikujú cez `ProjectController`. To znižuje riziko, že sa stav GUI a stav projektu rozídu.

## 9. Ukladanie a načítanie projektu

Ukladanie a načítanie projektov je implementované v súbore:

```
rp_restore/io/project_storage.py
```

Používajú sa triedy:

* `ProjectSerializer`
* `ProjectLoader`

Projekt sa ukladá ako `.zip` súbor. Vnútri ZIP-u sa nachádza najmä:

```
project.json
layers/
masks/
textures/
```

Súbor `project.json` obsahuje metadata projektu, napríklad:

* názov projektu
* zoznam vrstiev
* cesty k uloženým obrázkom vrstiev
* cesty k maskám
* paletu
* aktuálnu farbu
* nastavenia štetca
* nastavenia ColorChecker korekcie
* zoznam textúr
* históriu pre report

Obrázky vrstiev a masky sa ukladajú ako PNG. Pri načítaní sa znovu vytvoria objekty `Project`, `Layer`, `LayerMeta` a `Texture`.
Historická kópia sa ukladá ako bežná RGBA vrstva s typom `REFERENCE`. Jej obrázok, viditeľnosť, krytie a poradie sú súčasťou projektu.

Staršie projekty bez referenčnej vrstvy zostávajú kompatibilné. Historickú kópiu do nich možno dodatočne načítať.

## 10. Načítanie a ukladanie obrázkov

Pomocné funkcie pre obrázky sú v:

```
rp_restore/io/image_io.py
```

Tento modul rieši:

* načítanie obrázkov
* zmenu obrázka na pracovnú veľkosť
* uloženie výsledného obrazu
* uloženie masky

Obrazové dáta sa v aplikácii reprezentujú ako NumPy polia. Jednotlivé vrstvy aj obraz určený na vykreslenie na plátne používajú RGBA. Vstupy realistického algoritmu a exportovaný výsledný obraz používajú RGB.

## 11. Maska poškodenia a regióny

Maska poškodenia je dvojrozmerné bool NumPy pole. Hodnota `True` označuje poškodený pixel.

Regióny poškodenia sa vytvárajú podľa masky poškodenia a vrstvy hrán. Logika je v súbore:

```
rp_restore/core/regions.py
```

Dôležité prvky:

* `RegionInfo`
* `RegionMap`
* `build_region_map()`

Výber oblastí je reprezentovaný triedami v:

```
rp_restore/core/selection.py
```

Používajú sa hlavne:

* `Selection`
* `SelectionSet`

Výbery sa používajú pri nástroji Vybrat, Laso, výplni, auto-výplni a externých algoritmoch.

## 12. Undo/Redo

Undo/Redo systém sa nachádza v:

```
rp_restore/core/history.py
```

Dôležité triedy:

* `UndoAction`
* `GlobalUndoManager`

Každá zmena pixelov sa ukladá ako `UndoAction`, ktorá obsahuje:

* popis akcie
* ID vrstvy
* typ vrstvy
* bounding box zmenenej oblasti
* pixely pred zmenou
* pixely po zmene

Undo/Redo funguje globálne naprieč vrstvami. Po aplikovaní Undo alebo Redo sa synchronizujú aj masky vyplnenia poškodenia podľa alfa kanála vrstvy.

Pri pridávaní novej úpravy, ktorá mení pixely, je potrebné vytvoriť a uložiť `UndoAction`, inak sa zmena nebude dať vrátiť.

## 13. Textúrový štetec

Logika textúr je v súbore:

```
rp_restore/core/texture_brush.py
```

Dôležité triedy:

* `Texture`
* `TextureSettings`

Dôležité funkcie:

* `generate_brush_stamp()` – vytvorenie stopy textúrového štetca
* `generate_fill_pattern()` – vytvorenie textúrového vzoru pre výplň
* `deform_texture_image()` – deformácia textúry
* `clear_texture_cache()` – vyčistenie cache pri zmene nastavení

Textúry sa ukladajú do projektu a môžu byť buď pôvodné, alebo odvodené deformované textúry.

## 14. Auto-výplň

Auto-výplň malých oblastí je implementovaná v:

```
rp_restore/core/auto_fill.py
```

Hlavná funkcia je:

```
auto_fill_regions()
```

Auto-výplň pracuje s regiónmi poškodenia. Pre každý vybraný región vypočíta farbu z okolia a vyplní ho na aktívnej Paint vrstve. Výsledok sa uloží aj do Undo/Redo histórie.

## 15. Hrany a zjemnenie hrán

Kreslenie hrán je v nástroji:

```
rp_restore/gui/tools/edge_tool.py
```

Výpočtová logika zjemnenia prechodu cez hranu je v:

```
rp_restore/core/edge_blend.py
```

Nástroj na zjemnenie hrán je:

```
rp_restore/gui/tools/edge_blend_tool.py
```

Zjemnenie hrany pracuje s vybranou časťou existujúcej hrany. Aplikácia vytvorí mäkší prechod medzi vyplnenými oblasťami po oboch stranách hrany a následne odstráni zasiahnutú časť hrany.

## 16. Rozmazanie

Nástroj rozmazania je implementovaný v:

```
rp_restore/gui/tools/blend_tool.py
```

Rozmazanie môže používať rôzny zdroj podľa nastavenia v paneli Materiály:

* iba aktívnu Paint vrstvu
* kombináciu pôvodného obrazu a aktívnej Paint vrstvy

Nástroj upravuje len poškodené oblasti a zmeny zapisuje do aktívnej Paint vrstvy.

## 17. Externé algoritmy

Spúšťanie externých algoritmov zabezpečuje súbor:

```text
rp_restore/core/algorithm_runner.py
```

Dôležité triedy a dátové štruktúry:

* `AlgorithmType` – rozlišuje realistické a textúrové dopĺňanie
* `RealisticFillMode` – rozlišuje základný a vedený režim realistického dopĺňania
* `AlgorithmRequest` – obsahuje vstupné obrazy, masky a parametre algoritmu
* `TextureAlgorithmParams` – obsahuje parametre textúrového algoritmu
* `AlgorithmResult` – obsahuje výsledný RGBA výrez, jeho pozíciu a logovacie správy
* `AlgorithmRunner` – pripravuje vstupy a spúšťa príslušný algoritmus

### Realistické dopĺňanie

Realistické dopĺňanie používa klienta:

```python
painting_inpaint.remote
```

Prístupové údaje spravuje modul:

```text
rp_restore/core/remote_restoration_config.py
```

Endpoint URL a API kľúč sa ukladajú pomocou knižnice `keyring` do systémového úložiska používateľa. API kľúč sa neukladá do projektu ani do bežného konfiguračného súboru. Pred spustením klienta sa údaje nastavia ako premenné prostredia iba pre aktuálne bežiaci proces.

Používateľ vyberá obdĺžnikové okno s maximálnym rozmerom 1440 × 1440 pixelov. Ak existuje aktívny výber regiónov, maska algoritmu je obmedzená na tento výber. V opačnom prípade sa použije zostávajúca maska poškodenia vo zvolenom okne.

Podporované sú dva režimy:

* **základný režim** umožňuje nastaviť mieru dogenerovania pomocou parametra `partial_noise`,
* **vedený režim** umožňuje využiť ručne nakreslené vodiace čiary a je výrazne pomalší než základný režim.

Výber vstupného podkladu je nezávislý od režimu algoritmu. Dialóg `RealisticFillDialog` ponúka tri možnosti:

* `original` – pôvodný obraz,
* `reference` – historická kópia,
* `hybrid` – pôvodný obraz s historickou kópiou v oblastiach určených pôvodnou maskou poškodenia.

Historická kópia je dostupná ako zdroj iba vtedy, ak projekt obsahuje neprázdnu referenčnú vrstvu.

Prípravu vstupného RGB výrezu zabezpečuje `Project.realistic_input_region()`. Pri použití historickej kópie sa priehľadné pixely nahradia zodpovedajúcimi pixelmi pôvodného obrazu. Pri čiastočnej priehľadnosti sa oba obrazy zmiešajú podľa alfa kanála kópie.

Do výpočtu sa nezahŕňa používateľom nastavené krytie referenčnej vrstvy ani jej viditeľnosť na plátne.

Parameter `use_composited_layers` určuje, či sa k vybranému podkladu pridajú aj viditeľné vrstvy `PAINT` a `EDGE`. Predvolene je vypnutý v základnom režime a zapnutý vo vedenom režime.

Výsledok sa vloží do aktívnej vrstvy typu `PAINT`, a to iba do vybraných poškodených pixelov, ktoré na danej vrstve ešte neboli vyplnené.

### Textúrové dopĺňanie

Textúrový algoritmus sa spúšťa prostredníctvom nainštalovaného balíka:

```python
texture_infill
```

Dostupné modely sa zisťujú z priečinka `models` nainštalovaného balíka pomocou `importlib.resources`. Samotné generovanie vykonáva verejná funkcia:

```python
texture_infill.texture_infill.generate_infill()
```

Textúrový algoritmus podporuje dva typy výstupu:

1. doplnenie aktuálne vybraných poškodených oblastí,
2. vygenerovanie samostatnej textúry, ktorá sa pridá medzi materiály projektu.

Pri dopĺňaní oblasti aplikácia vypočíta ohraničujúci obdĺžnik výberu a algoritmu odovzdá iba príslušný výrez aktuálne zloženého obrazu a masku vybraných, ešte nevyplnených poškodených pixelov. Výsledný RGBA výrez sa vloží späť do aktívnej vrstvy malby.

Nastavenia textúrového algoritmu zahŕňajú:

* typ modelu textúry
* jednu až tri farby a silu každej farebnej vrstvy
* mierku v osiach X a Y
* hustotu v osiach X a Y pri podporovaných modeloch
* rotáciu a celkovú mierku
* nepriehľadné alebo priehľadné pozadie
* jas nepriehľadného pozadia
* seed
* rozmery samostatne generovanej textúry

Dialóg umožňuje vygenerovať zmenšený náhľad výsledku ešte pred spustením finálneho výpočtu.

Samostatne vygenerované textúry sa ukladajú do projektu spolu s parametrami algoritmu, pôvodnými farbami a silami farebných vrstiev. V paneli Materiály je možné ich farby neskôr upraviť a textúru opätovne vygenerovať.

Knižnica `numba`, ktorú používa textúrový balík, zapisuje cache do zapisovateľného priečinka aplikácie v používateľskom profile, aby nebolo potrebné zapisovať do inštalačného priečinka.

## 18. ColorChecker korekcia

Výpočtová časť ColorChecker korekcie je v:

```
rp_restore/core/color_correction.py
```

Dialóg je v:

```
rp_restore/gui/colorchecker_dialog.py
```

Korekcia sa počíta ako farebná transformačná matica. Táto matica sa uloží do projektu a môže sa zapínať alebo vypínať pre náhľad.

Korekcia sa aplikuje pri skladaní obrazu pre zobrazenie na plátne aj pri vytváraní exportovaného výsledného obrazu a PDF reportu. Nemení však priamo pixely jednotlivých vrstiev, ktoré zostávajú uložené v pôvodnej podobe.

## 19. Zarovnanie masky a historickej kópie

Logika zarovnania masky je v:

```
rp_restore/core/mask_alignment.py
```

Dialóg na výber bodov je v:

```
rp_restore/gui/mask_alignment_dialog.py
```

Používateľ vyberie zodpovedajúce body medzi pôvodným obrazom a maskou. Z nich sa vypočíta homografia a maska sa transformuje na rozmery pôvodného obrazu.

Rovnaký dialóg `MaskAlignmentDialog` sa používa aj pri zarovnávaní historickej kópie. Parameter `reference_mode=True` upravuje jeho popisky a spôsob prezentácie vstupných obrázkov.

Kópia sa zarovnáva k už existujúcemu pôvodnému obrazu v pracovnom rozlíšení projektu.

Homografia sa vypočíta pomocou `compute_homography()` zo zodpovedajúcich bodov historickej kópie a pôvodného obrazu. Na transformáciu kópie sa používa `warp_rgba_to_image()`, ktorá zachováva alfa kanál a priehľadnosť oblastí mimo transformovaného obrázka.

Pri interpolácii sa používa prednásobený alfa kanál (premultiplied alpha), aby nevznikali tmavé okraje priehľadných oblastí.

Dôležité funkcie:

* `compute_homography()`
* `warp_mask_to_image()`
* `warp_rgba_to_image()` – transformácia historickej kópie so zachovaním priehľadnosti
* `rgb_to_damage_mask()`

## 20. PDF report

Generovanie PDF reportu je v:

```
rp_restore/report/pdf_report.py
```

Dialóg pre vyplnenie údajov je v:

```
rp_restore/report/report_dialog.py
```

Dôležité prvky:

* `ReportMetadata`
* `generate_report()`

Report obsahuje pôvodný obraz, masku poškodenia, výsledný obraz, zostávajúcu masku, štatistiky a náhľady vrstiev.

Výsledný obraz v PDF reporte sa získava pomocou `Project.get_export_image()`. Vždy teda obsahuje pôvodné pozadie a viditeľné pracovné vrstvy, bez historickej kópie.

Ak projekt obsahuje historickú kópiu, funkcia `_add_layers_section()` ju pridá do samostatnej časti **Referenční obraz**. Kópia sa tým dokumentuje, ale nezahrňuje sa do výslednej rekonštrukcie.

Pri úprave obsahu reportu sa väčšina zmien robí v súbore `pdf_report.py`.

## 21. Nastavenia aplikácie

Nastavenia sú v:

```
rp_restore/config/settings.py
```

Trieda `AppSettings` aktuálne ukladá najmä zoznam naposledy otvorených projektov.

Nastavenia prístupu k vzdialenému realistickému dopĺňaniu sa neukladajú prostredníctvom `AppSettings`. Endpoint URL a API kľúč spravuje modul `remote_restoration_config.py` a ukladá ich pomocou knižnice `keyring` do systémového úložiska prihlasovacích údajov.

Nastavenia sa ukladajú do:

```
~/.rp_restore/settings.json
```

Ak sa nastavenia nepodarí načítať alebo uložiť, aplikácia chybu ignoruje a použije predvolený stav.

## 22. Typický tok práce v kóde

Príklad: používateľ použije štetec.

```
1. Používateľ vyberie nástroj Štětec v MainWindow
2. MainWindow informuje ProjectController
3. ProjectController nastaví aktívny BrushTool
4. Používateľ klikne do ImageCanvasWidget
5. Canvas prevedie pozíciu kurzora na súradnice obrazu
6. ProjectController zavolá BrushTool.on_mouse_press()
7. BrushTool upraví pixely aktívnej Paint vrstvy
8. Vytvorí sa UndoAction
9. Synchronizuje sa maska vyplnenia poškodenia
10. ProjectController obnoví príslušnú časť canvasu
```

Podobný princíp používajú aj ostatné nástroje.

### Načítanie historickej kópie

1. Používateľ vyberie možnosť **Načíst historickou kopii...**.
2. `MainWindow` zavolá `ProjectController.load_reference_image()`.
3. Otvorí sa `MaskAlignmentDialog` v referenčnom režime.
4. Z vybraných dvojíc bodov sa vypočíta homografia.
5. `warp_rgba_to_image()` vytvorí zarovnaný RGBA obraz.
6. Obrázok sa uloží do vrstvy `REFERENCE` a obnoví sa plátno.

### Vytvorenie nového návrhu

1. Používateľ vyberie vytvorenie nového návrhu.
2. `MainWindow` spracuje voľbu pracovných vrstiev a prípadné uloženie pôvodného projektu.
3. `ProjectController.create_proposal_from_current_project()` vytvorí nezávislú kópiu projektu.
4. Pri čistom návrhu sa inicializujú prázdne vrstvy `PAINT` a `EDGE` a obnoví pôvodná maska poškodenia.
5. Nový projekt sa uloží do samostatného ZIP súboru a otvorí sa v aplikácii.

## 23. Zhrnutie

Aplikácia je postavená okolo triedy `Project`, ktorá drží všetky dáta projektu, a triedy `ProjectController`, ktorá prepája model s grafickým rozhraním. Jednotlivé nástroje sú samostatné triedy reagujúce na udalosti myši. Vrstvy, masky a textúry sú uložené ako NumPy polia a celý projekt sa serializuje do ZIP súboru.
