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
- **Karta** – rozbor závodnice: kde velí a kde zabrat, na co se zaměřit,
  vývoj v čase a rozbor posledního závodu v každé disciplíně
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

## Rozbor závodnice (Karta)

**Kde velíš a kde zabrat** – postavení v ČR v každé disciplíně podle nejlepšího
výkonu za rozhodné období, proti všem českým závodníkům (u týmových disciplín
týmům) ve stejné kategorii a pohlaví. Stupně: Špička ČR (top 3), Silná stránka
(horní čtvrtina), Střed, Rezerva. Zahraniční oddíly se sem nepočítají.

**Na co se zaměřit** – doporučení z posledního závodu v každé disciplíně, jen
věci doložitelné čísly, seřazené podle toho, co přinesou:

1. chyby „zadarmo“ – porušení času/prostoru, chybný start
2. nesplněné povinné prvky
3. bedna na dosah – u rychlosti malý odstup, u freestylu „bez chyb na bedně“
4. čistota – missy a breaky podle podílu ztracené sestavy
5. limit na dosah
6. obtížnost výrazně pod bednou (s nejslabší částí obtížnosti)
7. o místo výš, když nejde o bednu

**Rozbor posledního závodu** u každé disciplíny:

- umístění a **odstup na místo výš, na bednu a na 1. místo** i s oddílem
- u freestylu tabulka D, P, Q, srážky a výsledek proti bedně a vítězi
  (když vyhrála, proti druhému místu)
- **kolik stály chyby**: missy, jejich vliv na prezentaci, breaky, porušení,
  nesplněné povinné prvky; a **odhad bez chyb** i s umístěním
- podrobně: obtížnost podle částí (power/gymnastika, multiples, rope
  manipulation; u DD jumper/turner) proti českým závodníkům na bedně,
  prezentace po pěti kategoriích, rozložení úrovní prvků

### Odkud se to bere a co je přesné

Všechno je z oficiálních výsledků (`EntryScoreData`) a z výsledků jednotlivých
rozhodčích, které počítá samotný výsledkový systém (`JudgeResults`,
`TallySheet`). Typ rozhodčího: `P` prezentace, `T` technický, `Dp`/`Dm`/`Dr`
obtížnost SR, `Da`/`Db` Wheel, `Dj`/`Dt` Double Dutch.

**Přesné:** umístění, odstupy, D/P/Q/M, ztráty srážkami a povinnými prvky
(z oficiálních složek: R = D × (1 + P) × Q × M, u DD bez Q).
**Odhad** (v appce označený): vliv missů na prezentaci a „bez chyb“ – počítá se
s tím, že rozhodčí prezentace za každý miss strhli bod v každé kategorii;
ořez škály 0–24 se zanedbává.

**Umístění** je vždy proti **celému oficiálnímu poli včetně zahraničních**
oddílů – tak, jak to bylo ve výsledkovce. Dvě zvláštnosti:

- **sloučené kategorie** – pořadatel malou kategorii někdy vyhodnotí společně
  s jinou (třeba jediného kluka mezi holkami). V exportu to napsané není.
  Build sloučení najde tak, že vyzkouší, se kterým eventem sloučené pořadí
  reprodukuje oficiální umístění přesně, a jen tehdy ho přijme.
- **smíšené soutěže A + B** – oficiální pořadí v exportu je společné, ale
  vyhlašuje se zvlášť. Umístění se tu dopočítá v rámci úrovně podle IJRU
  (rychlost: shoda = stejné místo; freestyle: tie-break M → Q → P → D).

### Kontroly, které build vypisuje

V sekci `=== ROZBOR ===` musí být:

- spárováno **N / N** u každé soutěže s exportem
- `kontrola R = složky podle IJRU` – jen `shoda`
- `kontrola umístění vs. oficiální` – jen `shoda`

Stav k 8. 11. 2026: 3 681 / 3 681 výkonů, 656 / 656 freestylů, 3 808 / 3 808
umístění, 88 sloučených kategorií. Nezávislá kontrola v Pythonu přímo ze
surových výsledků (mimo build) na 398 náhodných výkonech: 0 nesrovnalostí
v umístění, odstupech i ztrátách.

### Identita závodníků

Členská ID v exportech nejsou spolehlivá: stejný člověk má v různých soutěžích
různá ID, někdy žádné, a výjimečně ID, které v datech patří někomu jinému
(Nina Tůmová má v exportu Mini Cupu ID Valérie Vojtěškové). ID se proto
věří, jen když souhlasí se jménem; jinak rozhoduje jméno. Build vypisuje
každé **sjednocení** a každý **konflikt** – projdi je, než výsledek pushneš.

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
