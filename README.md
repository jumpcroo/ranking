# Jumpcroo – ranking a limity

Výsledkový přehled oddílu Jumpcroo: nominační ranking, splnění kvalifikačních
limitů a karta závodnice s posunem výkonů v čase.

## Kde to lidé vidí

```
data/*.json          JSON exporty z výsledkového systému (jeden soubor = jedna soutěž)
   ↓ python3 build.py
index.html           hotová stránka, všechno v jednom souboru
   ↓ git push
GitHub Pages    →    https://jumpcroo.github.io/ranking/
   ↓ <iframe>
Webnode         →    https://www.jumpcroo.cz/ranking/     ← co vidí lidé
```

Na Webnode je v HTML poli vložené jen tohle a nikdy se to nemění:

```html
<iframe src="https://jumpcroo.github.io/ranking/" style="width:100%;height:85vh;border:0;border-radius:12px" loading="lazy" title="Jumpcroo Výsledky"></iframe>
```

## Přidání nové soutěže

1. JSON export z výsledkového systému **prožeň přes `sanitize.py`** a teprve
   výsledek ulož do `data/`:
   `python3 sanitize.py "<surový export>.json" "data/S-BEE 2026 A.json"`
   **Úroveň závodu dej do názvu souboru** – `... A.json` nebo `... B.json`.
   Surový export obsahuje e-maily a ID rozhodčích a zapisovatelů; build
   ho do veřejného repa nepustí a zastaví se.
2. `python3 build.py` (nebo `python3 build.py --check`, když chceš jen vidět,
   co by se stalo, a nic nepřepsat).
3. Commitni `index.html` a nový soubor v `data/`.

Skript vypíše, co přidal, kolik výkonů, jaké datum soutěže určil a koho
nenapároval na existující členské ID. Ty výpisy se vyplatí přečíst – viz níž.

### Soutěž, kde se jede A i B zároveň

**Z exportu se úroveň jednotlivého výsledku vyčíst nedá.** Ve stejném eventu –
stejná disciplína, stejná věková kategorie – jsou vedle sebe záznamy úrovně A i B
a žádné pole v JSONu je nerozlišuje. Ověřeno i na hypotéze, že by A/B šlo odvodit
od splnění limitu: vychází to jen na 61 %, takže ne.

Takovou soutěž pojmenuj bez přípony a pravidlo dopiš do `config.json` do
`mixedRules`:

- `byDivision` – když export vyplňuje `DivisionName` a dělí se podle něj
  (novější formát exportu to pole má)
- `byAgeGroup` – když jsou úrovně rozdělené podle věkových kategorií

Pozor: když je **stejná kategorie v A i v B**, `byAgeGroup` nestačí a je potřeba
`byDivision`. U S-BEE je takto ve obou úrovních kategorie 12–15.

Když pravidlo chybí, build se zastaví s chybou a řekne, co doplnit. Nikdy nic
netipuje.

## Co si od skriptu přečíst

- **Noví závodníci bez členského ID.** Novější formát exportu nemá `MemberID`
  (má tam 0 a místo něj `MemberCode` v úplně jiné řadě čísel), takže se závodníci
  párují **podle jména**. Když se někdo nenapáruje, dostane nové ID a skript ho
  vypíše. Projdi ten seznam: pokud je tam někdo, kdo už v datech je, jen zapsaný
  jinak (přehozené jméno a příjmení, překlep), rozpadne se mu součet dvou
  nejlepších na dva různé lidi a ranking bude špatně.
- **Závodníci, kteří nastoupili v nižší kategorii, než mají zapsanou.**
  Kategorie se nezmění sama, jen se na to upozorní. Zkontroluj, jestli je to
  v pořádku.
- **Vynechané záznamy** – smazané a neohodnocené položky se do dat neberou.

## Záložky

- **Ranking** – nominační pořadí, součet dvou nejlepších
- **Limity** – splnění kvalifikačních limitů, přepínač MS/ME × MČR
- **Karta** – karta závodnice, celá historie a graf posunu po disciplínách
- **Závody** – podklad na povídání o výsledcích po závodě

### Závody

Vybere se závod a u každé závodnice se ukáže, co zajela a o kolik se posunula
proti svému poslednímu výkonu v téže disciplíně. Označí se osobní rekord, první
start v disciplíně a to, když výkon poprvé překročil limit MČR nebo MS. Nahoře
je souhrn: kolik padlo osobáků, kolik limitů a tři největší zlepšení.

Výchozí oddíl je Jumpcroo; jinak se řídí filtrem týmů. Hledání podle jména
funguje, takže si každý najde sám sebe.

U závodnic, které k 1. lednu přecházejí do vyšší věkové kategorie, přibude blok
s limity na MS, které na ně v nové kategorii budou platit, a s jejich nejlepšími
výkony. To je podklad na řeč o tom, co je čeká – hlavně u přechodu 9–11 → 12–15.

Rozhodné období se tu **neuplatňuje** – porovnává se s celou historií.
U týmových disciplín se porovnává s vlastním předchozím výkonem v disciplíně,
i když mohla být sestava jiná.

## Jak se počítá ranking a limity

- **Ranking** = součet dvou nejlepších výsledků ze závodů úrovně A a z mezinárodních
  závodů. Při stejném součtu rozhoduje novější výsledek.
- **Splnění limitu** = nejlepší jednotlivý výkon proti limitu. Limit lze splnit
  na A i na B.
- **Limit MČR je zároveň maximální limit úrovně B**: kdo ho v disciplíně dosáhne,
  nesmí v ní dál startovat na soutěžích úrovně B. Platí pro všechny věkové
  kategorie. Limity na MS mají jen kategorie 12–15 a 16+.
- **Rozhodné období**: ranking i limity se počítají jen z 10 celých kalendářních
  měsíců zpět plus běžícího měsíce. Počítá se v prohlížeči z aktuálního data,
  takže se posouvá samo a není co přenastavovat. Například v prosinci 2026 vypadne
  Master Cup (17. 1. 2026).
- **Karta závodnice rozhodné období neomezuje** – drží celou historii, aby byl
  vidět posun v čase. V grafu je svislá čárkovaná linka na začátku rozhodného
  období, starší body jsou ztlumené, oranžová vodorovná linka je limit MČR
  (strop pro B) a zelená limit na MS.

Zdroj pravidel: soutěžní systém Czech Jump Rope,
https://www.czechjumprope.cz/soutezni-system/

## Soubory

| | |
|---|---|
| `build.py` | přepočet; všechna logika je tady |
| `sanitize.py` | očištění exportu od osobních údajů před vložením do `data/` |
| `template.html` | stránka bez dat, se značkou `__DATA__` |
| `config.json` | úrovně smíšených soutěží, sjednocení názvů oddílů |
| `data/legacy.json` | zamrzlá ověřená data soutěží do Czech Open 2026 včetně |
| `data/kategorie.json` | kategorie pro příští sezónu, jen dvojice ID → kategorie |
| `data/*.json` | JSON exporty jednotlivých soutěží |
| `index.html` | vygenerovaná stránka – tu publikuje GitHub Pages |

`data/legacy.json` se nepřepočítává. Drží i kvalifikační limity, názvy disciplín
a seznam týmových disciplín – **když svaz změní limity, mění se tam.**
U historických soutěží jsou v něm A/B příznaky jednotlivých výsledků, které
není z čeho odvodit (viz výš o smíšených soutěžích).

## Osobní údaje

**Exporty z výsledkového systému.** U každého zásahu do výsledku je v nich
e-mail a ID člověka, který ho provedl (rozhodčí, zapisovatelé), a ID zařízení.
`sanitize.py` to odstraní a pak soubor ještě prohledá na cokoli, co vypadá
jako e-mail. `build.py` navíc odmítne běžet, když v `data/` takový údaj najde.

**Repo je veřejné** – jinak by GitHub Pages zadarmo nefungovaly. Cokoli se sem
commitne, si může kdokoli stáhnout. Proto sem **nepatří seznam členů**: jsou
v něm data narození dětí, čísla pojišťoven a e-maily rodičů.

`data/kategorie.json` proto obsahuje jen dvojice **členské ID → věková kategorie**.
Žádná jména, žádné ročníky. Kategorie sama z repa nic nového neprozradí – je
u každého startu ve výsledkovce.

Ročníky narození, ze kterých se kategorie počítají, žijí mimo repo:
`Jumpcroo/Spolek a administrativa/rocniky.csv` (jméno a rok, nic víc).
Když se složení oddílu změní, přepočítá se z nich `data/kategorie.json` a do repa
jde zase jen ten odvozený soubor.

## Kontrola

Že skript nic nerozbil, se dá ověřit tak, že přegeneruje už hotová data
a výsledek se porovná s předchozím `index.html` – data i HTML musí vyjít
identicky. Takhle byl skript postaven: reprodukuje ručně ověřenou verzi
z 8. 11. 2026 přesně, 3 843 výkonů ve 13 soutěžích.
