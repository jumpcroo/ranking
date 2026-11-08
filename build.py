#!/usr/bin/env python3
"""
Přegeneruje index.html pro https://jumpcroo.github.io/ranking/

Použití:
    python3 build.py                 # přegeneruje index.html
    python3 build.py --check         # jen vypíše, co by se stalo, nic nezapíše

Jak se přidá nová soutěž:
    1. JSON export z výsledkového systému vlož do data/
       Úroveň závodu dej do názvu souboru: "... A.json" nebo "... B.json".
       Např. "S-BEE 2026 A.json".
    2. Pusť build.py.
    3. Commitni index.html a data/<nový soubor>.

Když se na soutěži jede A i B zároveň (smíšená), z exportu se to vyčíst NEDÁ —
ve stejném eventu jsou vedle sebe záznamy obou úrovní a žádné pole je nerozlišuje.
Takovou soutěž pojmenuj bez přípony a pravidlo dopiš do config.json, viz tam.

Historické soutěže (do Czech Open 2026 včetně) jsou zamrzlé v data/legacy.json
a nepřepočítávají se. Jejich A/B příznaky jsou ověřené a není je z čeho odvodit.
"""

import json, os, re, sys, glob, unicodedata
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
LEGACY = os.path.join(DATA, "legacy.json")
CONFIG = os.path.join(ROOT, "config.json")
TEMPLATE = os.path.join(ROOT, "template.html")
OUT = os.path.join(ROOT, "index.html")

AGE_LEVEL = {
    "8 and under": 0,
    "9-11": 1,
    "11 and Younger": 1,
    "12-15": 2,
    "16+ (allow younger)": 3,
}

CHECK = "--check" in sys.argv


def die(msg):
    print("CHYBA: " + msg, file=sys.stderr)
    sys.exit(1)


def norm_ascii(s):
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- vstupy
legacy = load_json(LEGACY)
cfg = load_json(CONFIG)

perfs = list(legacy["perfs"])
disc_names = legacy["discNames"]
team_disc = set(legacy["teamDisc"])
limits = legacy["limits"]
comp_levels = dict(legacy["compLevels"])

known_comps = {p["comp"] for p in perfs}

# jméno -> aid z už ověřených dat (identita závodníka musí držet napříč soutěžemi,
# jinak se jednomu člověku rozpadne součet dvou nejlepších)
name2aid = {}
for p in perfs:
    for m in p["members"]:
        name2aid[m["name"].strip()] = m["aid"]

club_alias = cfg.get("clubAliases", {})
level_cfg = cfg.get("levels", {})
mixed_cfg = cfg.get("mixedRules", {})


def level_from_filename(path):
    base = os.path.basename(path)
    base = re.sub(r"\.json$", "", base, flags=re.I)
    m = re.search(r"[ _\-]([AB])$", base.strip())
    return m.group(1).upper() if m else None


def entry_level(comp, level, ev, en):
    """Úroveň jednoho záznamu. U smíšené soutěže podle pravidla z config.json."""
    if level in ("A", "B"):
        return level
    rule = mixed_cfg.get(comp)
    if not rule:
        die(
            "soutěž %r je smíšená (A i B zároveň) a chybí pravidlo.\n"
            "  Z exportu se úroveň vyčíst nedá. Dopiš do config.json do \"mixedRules\" "
            "buď {\"byDivision\": {\"<DivisionName>\": \"A\", ...}} nebo "
            "{\"byAgeGroup\": {\"<AgeGroupName>\": \"A\", ...}}, "
            "nebo soubor pojmenuj s příponou A/B, pokud je celá soutěž jedné úrovně." % comp
        )
    if "byDivision" in rule:
        dv = ev.get("DivisionName")
        if dv not in rule["byDivision"]:
            die("soutěž %r: DivisionName %r není v config.json → mixedRules → byDivision" % (comp, dv))
        return rule["byDivision"][dv]
    if "byAgeGroup" in rule:
        ag = ev.get("AgeGroupName")
        if ag not in rule["byAgeGroup"]:
            die("soutěž %r: AgeGroupName %r není v config.json → mixedRules → byAgeGroup" % (comp, ag))
        return rule["byAgeGroup"][ag]
    die("soutěž %r: pravidlo v mixedRules nerozumím (čekám byDivision nebo byAgeGroup)" % comp)


def comp_date(j):
    """Datum soutěže = nejstarší odeslaný protokol."""
    ds = set()
    for ev in j["Events"]:
        for en in ev.get("Entries", []):
            for sc in en.get("Scores") or []:
                t = sc.get("ScoresheetSubmittedTime")
                if t:
                    ds.add(t[:10])
    return min(ds) if ds else None


new_aids = {}


def aid_for(part, pinfo):
    """Identita závodníka. MemberID je spolehlivé; nový formát exportu ho ale nemá
    (má 0 a místo něj MemberCode v jiné řadě čísel), tak se páruje podle jména."""
    if part.get("MemberID"):
        return "m%d" % part["MemberID"]
    nm = (part["FirstName"] + " " + part["LastName"]).strip()
    if nm in name2aid:
        return name2aid[nm]
    if nm in new_aids:
        return new_aids[nm]
    code = (pinfo.get(part["ParticipantID"], {}) or {}).get("MemberCode") or ""
    digits = re.sub(r"\D", "", code)
    aid = "c" + digits if digits else "x" + re.sub(r"[^a-z0-9]", "", norm_ascii(nm))
    new_aids[nm] = aid
    return aid


# ---------------------------------------------------------------- nové exporty
NOT_RESULTS = {"legacy.json", "kategorie.json"}   # služební soubory, ne výsledkovky
files = sorted(f for f in glob.glob(os.path.join(DATA, "*.json")) if os.path.basename(f) not in NOT_RESULTS)
added = {}
report = []

for path in files:
    j = load_json(path)
    comp = j.get("CompetitionName")
    if not comp:
        die("%s: chybí CompetitionName" % os.path.basename(path))
    if comp in known_comps:
        report.append("  přeskočeno (už je v legacy.json): %s" % comp)
        continue

    level = level_from_filename(path) or level_cfg.get(comp)
    if level is None and comp not in mixed_cfg:
        die(
            "%s: nevím úroveň soutěže %r.\n"
            "  Pojmenuj soubor s příponou (\"... A.json\" / \"... B.json\"), "
            "nebo doplň config.json → levels, nebo → mixedRules u smíšené soutěže."
            % (os.path.basename(path), comp)
        )

    date = comp_date(j)
    if not date:
        die("%s: v exportu není žádný čas odeslání protokolu, neumím určit datum soutěže" % os.path.basename(path))

    teams = {t["TeamID"]: t["TeamName"] for t in j.get("Teams", [])}
    pinfo = {p["ParticipantID"]: p for p in j.get("Participants", [])}
    gender_of = {1: "Female", 2: "Male"}

    count = 0
    skipped = Counter()
    for ev in j["Events"]:
        abbr = ev["EventDefinitionAbbr"]
        disc = "DDCS" if abbr == "DDCS30" else abbr
        if disc not in disc_names:
            skipped["neznámá disciplína " + abbr] += 1
            continue
        al = AGE_LEVEL.get(ev["AgeGroupName"])
        if al is None:
            skipped["neznámá kategorie " + str(ev["AgeGroupName"])] += 1
            continue
        lc = entry_level(comp, level, ev, None)

        for en in ev.get("Entries", []):
            if en.get("IsDeleted"):
                skipped["smazané"] += 1
                continue
            if not en.get("IsScored"):
                skipped["bez výsledku"] += 1
                continue
            score = en.get("TotalScore")
            if score is None:
                skipped["bez skóre"] += 1
                continue
            parts = en.get("Participants") or []
            if not parts:
                skipped["bez závodníků"] += 1
                continue

            members = []
            for x in parts:
                nm = (x["FirstName"] + " " + x["LastName"]).strip()
                members.append({"name": nm, "aid": aid_for(x, pinfo)})

            tn = next((x.get("TeamName") for x in parts if x.get("TeamName")), None) or teams.get(parts[0].get("TeamID"))
            club = club_alias.get(tn, tn)

            # Pohlaví: u Female/Male eventu platí event. U Mixed se bere podle
            # složení týmu, pokud je pohlaví účastníků v exportu známé.
            if ev["GenderName"] in ("Female", "Male"):
                gender = ev["GenderName"]
            else:
                gs = {gender_of.get((pinfo.get(x["ParticipantID"]) or {}).get("GenderID")) for x in parts}
                if None in gs:
                    gender = ev["GenderName"]
                elif gs == {"Female"}:
                    gender = "Female"
                elif gs == {"Male"}:
                    gender = "Male"
                else:
                    gender = "Mixed"

            perfs.append({
                "kind": "team" if disc in team_disc else "ind",
                "disc": disc,
                "discName": disc_names[disc],
                "al": al,
                "gender": gender,
                "comp": comp,
                "lc": lc,
                "date": date,
                "score": float(score),
                "cR": lc == "A",
                "cL": True,
                "club": club,
                "members": members,
            })
            count += 1

    comp_levels[comp] = level or "mixed"
    added[comp] = (count, date, level or "mixed", os.path.basename(path), dict(skipped))

# ---------------------------------------------------------------- dopočty
# athCat = nejnižší věková kategorie, ve které závodník nastoupil.
# Hodnoty z legacy.json se berou jako dané a nepřepisují se – jsou ověřené.
# Dopočítávají se jen noví závodníci, a u stávajících se kategorie sníží,
# když nastoupili v nižší, než měli dosud zapsanou.
ath_cat = dict(legacy.get("athCat") or {})
mins = defaultdict(list)
for p in perfs:
    if p.get("al") is None:
        continue
    for m in p["members"]:
        mins[m["aid"]].append(p["al"])
cat_warnings = []
for aid, vals in mins.items():
    lo = min(vals)
    if aid not in ath_cat or ath_cat[aid] is None:
        ath_cat[aid] = lo
    elif lo < ath_cat[aid]:
        # Nepřepisujeme: hodnota z legacy.json je ověřená a tiché snížení
        # kategorie by zamíchalo limity. Jen na to upozorníme.
        cat_warnings.append((aid, ath_cat[aid], lo))

# Kategorie pro příští sezónu. V repu leží JEN dvojice aid → kategorie,
# žádná jména a žádné ročníky narození – ty jsou osobní údaj a zůstávají mimo
# repo (Jumpcroo/Spolek a administrativa/rocniky.csv). Kategorie sama z repa
# nic nového neprozradí, je u každého startu ve výsledkovce.
next_cat = {}
next_season = None
KATEGORIE = os.path.join(DATA, "kategorie.json")
if os.path.exists(KATEGORIE):
    k = load_json(KATEGORIE)
    next_cat = k.get("cat") or {}
    next_season = k.get("season")

comp_groups = {"A": [], "mixed": [], "B": [], "intl": []}
# pořadí soutěží podle data
order = {}
for p in perfs:
    d = p.get("date") or "9999"
    if p["comp"] not in order or d < order[p["comp"]]:
        order[p["comp"]] = d
for comp in sorted(order, key=lambda c: order[c]):
    lvl = comp_levels.get(comp, "mixed")
    comp_groups["A" if lvl == "A" else ("B" if lvl == "B" else "mixed")].append(comp)

generated = max((p.get("date") or "") for p in perfs)

payload = {
    "generated": generated,
    "discNames": disc_names,
    "teamDisc": sorted(team_disc),
    "limits": limits,
    "compGroups": comp_groups,
    "athCat": ath_cat,
    "athCatNext": next_cat,
    "nextSeason": next_season,
    "perfs": perfs,
}

# ---------------------------------------------------------------- výstup
tpl = open(TEMPLATE, encoding="utf-8").read()
if "__DATA__" not in tpl:
    die("template.html neobsahuje značku __DATA__")
blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
if "</script" in blob.lower():
    die("data obsahují </script, to by rozbilo stránku")
html = tpl.replace("__DATA__", blob)

print("=== BUILD RANKINGU ===")
for line in report:
    print(line)
if added:
    for comp, (n, date, lvl, fn, skipped) in added.items():
        print("  přidáno: %s — %d výkonů, datum %s, úroveň %s (%s)" % (comp, n, date, lvl, fn))
        if skipped:
            print("      vynecháno: %s" % ", ".join("%s × %d" % (k, v) for k, v in skipped.items()))
else:
    print("  žádná nová soutěž")
if cat_warnings:
    print("  POZOR – závodníci, kteří nastoupili v nižší kategorii, než mají zapsanou.")
    print("  Kategorie se nezměnila; zkontroluj, jestli je zápis správný:")
    for aid, had, low in cat_warnings:
        nm = next((m["name"] for p in perfs for m in p["members"] if m["aid"] == aid), aid)
        print("      %s (%s): zapsáno %s, nastoupil v %s" % (nm, aid, had, low))
if new_aids:
    print("  noví závodníci bez členského ID (%d):" % len(new_aids))
    for nm, aid in sorted(new_aids.items()):
        print("      %s → %s" % (nm, aid))
print("  celkem: %d výkonů, %d soutěží, %d závodníků" % (len(perfs), len(order), len(ath_cat)))
if next_cat:
    print("  kategorie pro sezónu %s: %d závodníků" % (next_season, len(next_cat)))
else:
    print("  kategorie pro příští sezónu: data/kategorie.json není, blok o přechodu se nezobrazí")
print("  rozhodné období se počítá v prohlížeči z aktuálního data, data generována %s" % generated)

if CHECK:
    print("\n--check: index.html nezapsán")
else:
    open(OUT, "w", encoding="utf-8").write(html)
    print("\n  zapsáno %s (%.0f kB)" % (os.path.basename(OUT), os.path.getsize(OUT) / 1024))
