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


# ---------------------------------------------------------------- pojistka
# Repo je veřejné. Surové exporty obsahují e-maily a ID rozhodčích a
# zapisovatelů – do data/ smí jen soubory prohnané přes sanitize.py.
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_FORBIDDEN = ("UserEmail", "UserID", "DeviceSessionID", "LastJudgeDataChange", "LastChange")
for _f in sorted(glob.glob(os.path.join(DATA, "*.json"))):
    _t = open(_f, encoding="utf-8").read()
    _bad = [k for k in _FORBIDDEN if '"%s"' % k in _t]
    if _EMAIL.search(_t) or _bad:
        die(
            "%s obsahuje osobní údaje (%s).\n"
            "  Surový export nepatří do veřejného repa. Prožeň ho nejdřív:\n"
            "  python3 sanitize.py <surový.json> data/<název.json>"
            % (os.path.basename(_f), ", ".join(_bad) or "e-mail")
        )

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


def name_key(nm):
    """Jméno bez diakritiky, malými písmeny, slova seřazená – aby
    „Klára Zbranková“ a „Zbranková Klára“ byl jeden člověk."""
    return " ".join(sorted(re.sub(r"[^a-z ]", "", norm_ascii(nm)).split()))


aid_names = defaultdict(set)          # aid -> klíče jmen, pod kterými v datech je
for p in perfs:
    for m in p["members"]:
        aid_names[m["aid"]].add(name_key(m["name"]))
key2aids = defaultdict(set)           # klíč jména -> aid
for aid, ks in aid_names.items():
    for k in ks:
        key2aids[k].add(aid)

id_unified = {}     # (ID z exportu, jméno) -> sjednocené ID
id_conflict = {}    # (ID z exportu, jméno) -> komu to ID v datech patří


def aid_for(part, pinfo):
    """Identita závodníka – musí držet napříč soutěžemi, jinak se jednomu
    člověku rozpadne součet dvou nejlepších na dva lidi, nebo se mu připíše
    cizí výkon.

    Členská ID v exportech nejsou spolehlivá: stejný člověk má v různých
    soutěžích různá ID, někdy žádné (MemberID = 0), a výjimečně dostane ID,
    které v datech patří někomu jinému. Proto se ID věří, jen když souhlasí
    se jménem:
      1. ID je v datech známé a patří člověku s tímto jménem  → to ID
      2. jméno je v datech známé (jednoznačně)                → ID podle jména
      3. ID je v datech známé, ale patří JINÉMU jménu         → konflikt,
         nepřiřazuje se, vznikne nové ID podle jména (a vypíše se)
      4. ID v datech není                                     → to ID
      5. žádné ID                                             → nové z MemberCode / jména
    Sjednocení i konflikty build vypisuje, ať se dají zkontrolovat.
    """
    nm = (part["FirstName"] + " " + part["LastName"]).strip()
    k = name_key(nm)
    mid = ("m%d" % part["MemberID"]) if part.get("MemberID") else None
    if mid and k in aid_names.get(mid, ()):
        return mid
    cands = key2aids.get(k, set())
    if len(cands) == 1:
        canon = next(iter(cands))
        if mid and mid != canon:
            id_unified[(mid, nm)] = canon
        return canon
    if mid and mid in aid_names:
        id_conflict[(mid, nm)] = sorted(aid_names[mid])
        mid = None
    if mid:
        return mid
    if nm in new_aids:
        return new_aids[nm]
    code = (pinfo.get(part["ParticipantID"], {}) or {}).get("MemberCode") or ""
    digits = re.sub(r"\D", "", code)
    aid = "c" + digits if digits else "x" + re.sub(r"[^a-z0-9]", "", norm_ascii(nm))
    new_aids[nm] = aid
    return aid


# ---------------------------------------------------------------- nové exporty
NOT_RESULTS = {"legacy.json", "kategorie.json", "reprezentace.json"}   # služební soubory, ne výsledkovky
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

# ---------------------------------------------------------------- rozbor
# Ke každému výkonu, ke kterému existuje JSON export, se připojí:
#   fv  index „pole“ – seznam všech, proti kterým se závodnice umisťovala
#   pl  umístění v tom poli
#   fs  rozpad freestylu (viz enrich.py)
#   sm  srážka za chybné starty/výměny u rychlosti, pokud nějaká byla
#
# Pole (fields) má dvě podoby:
#  • čistý event (všechny spárované výkony mají stejnou úroveň A/B):
#    pole = VŠECHNY záznamy oficiálního eventu včetně zahraničních oddílů
#    a umístění = OFICIÁLNÍ pořadí z výsledkovky
#  • smíšený event (A i B v jednom eventu – oficiální pořadí je společné,
#    ale vyhlašuje se zvlášť): pole = jen záznamy téže úrovně, které jsou
#    v datech nástroje (zahraniční u smíšených soutěží úroveň nemají),
#    umístění se dopočítá podle IJRU
# Data nástroje (perfs) zahraniční oddíly nemají záměrně – slouží českému
# rankingu a nominacím. Pole je jen na umístění a odstupy na konkrétním závodě.
# Historické soutěže bez exportu (ME, EOT, JME) rozbor nemají.
sys.path.insert(0, ROOT)
import enrich  # noqa: E402

def _mini(fs):
    if not fs:
        return 0
    return [fs.get("D"), fs.get("P"), fs.get("Q", 1), fs.get("M")]

perf_by_key = defaultdict(list)
for p in perfs:
    k = (p["comp"], p["disc"], frozenset(m["aid"] for m in p["members"]), p["score"], p.get("al"))
    perf_by_key[k].append(p)

clubs_tbl, club_idx = [], {}
def cidx(name):
    name = club_alias.get(name, name) or "?"
    if name not in club_idx:
        club_idx[name] = len(clubs_tbl)
        clubs_tbl.append(name)
    return club_idx[name]

rcheck, rbad = Counter(), []
coverage = defaultdict(lambda: [0, 0])
json_comps = set()
raw_events = []          # (comp, disc, gender, age, [entry dict])

for path in sorted(f for f in glob.glob(os.path.join(DATA, "*.json")) if os.path.basename(f) not in NOT_RESULTS):
    j = load_json(path)
    comp = j.get("CompetitionName")
    json_comps.add(comp)
    pinfo = {p_["ParticipantID"]: p_ for p_ in j.get("Participants", [])}
    teams = {t["TeamID"]: t["TeamName"] for t in j.get("Teams", [])}
    for ev in j["Events"]:
        abbr = ev["EventDefinitionAbbr"]
        disc = "DDCS" if abbr == "DDCS30" else abbr
        al = AGE_LEVEL.get(ev["AgeGroupName"])
        rows = []
        for en in ev.get("Entries", []):
            if en.get("IsDeleted") or not en.get("IsScored") or en.get("TotalScore") is None:
                continue
            parts = en.get("Participants") or []
            if not parts:
                continue
            score = float(en["TotalScore"])
            res = (en.get("EntryScoreData") or {}).get("result") or {}
            fs = enrich.freestyle(res, enrich.judges_by_type(en)) if "D" in res else None
            if fs:
                rr = enrich.recompute_R(fs)
                if rr is not None:
                    ok = abs(rr - score) <= 0.011
                    rcheck["shoda" if ok else "rozdíl"] += 1
                    if not ok:
                        rbad.append((comp, disc, score, rr))
            tn = next((x.get("TeamName") for x in parts if x.get("TeamName")), None) or teams.get(parts[0].get("TeamID"))
            perf = None
            if disc in disc_names and al is not None:
                aids = frozenset(aid_for(x, pinfo) for x in parts)
                cand = perf_by_key.get((comp, disc, aids, score, al))
                if cand:
                    perf = cand.pop(0)
                    if fs:
                        perf["fs"] = fs
                    elif res.get("m"):
                        perf["sm"] = res["m"]
            rows.append({"score": score, "ork": en.get("Rank"), "club": tn, "fs": fs, "perf": perf,
                         "aids": sorted(aid_for(x, pinfo) for x in parts) if os.environ.get("DEBUG_UNMATCHED") else None})
        if rows and disc in disc_names:
            raw_events.append((comp, disc, ev["GenderName"], ev["AgeGroupName"], rows))

for p in perfs:
    if p["comp"] in json_comps:
        coverage[p["comp"]][1] += 1

perf_pos = {id(p): i for i, p in enumerate(perfs)}   # pořadí v payloadu se už nemění
fields = []
rank_check, rank_bad = Counter(), []
merge_log = Counter()
mixed_dropped = 0

def _ranks(rows, is_fs):
    tmp = [({"score": r["score"]}, r["fs"]) for r in rows]
    mr = enrich.rank_group(tmp, is_fs)
    return [mr[id(o)] for o, _ in tmp]

def _rank_within(target, pool, is_fs):
    """Umístění záznamů z target, kdyby se řadily mezi všechny záznamy pool."""
    allr = _ranks(pool, is_fs)
    pos = {id(r): allr[i] for i, r in enumerate(pool)}
    return [pos[id(r)] for r in target]

# Sloučené kategorie: pořadatel někdy malou kategorii vyhodnotí společně
# s jinou (např. jediného kluka mezi holkami). V exportu to není napsané –
# pozná se to tak, že oficiální pořadí nesedí s vlastním eventem. Pak se
# hledá event téže soutěže, disciplíny a věku, se kterým sloučené pořadí
# reprodukuje oficiální umístění PŘESNĚ. Jen tehdy se sloučení přijme.
by_cda = defaultdict(list)
for i, (comp, disc, gen, age, rows) in enumerate(raw_events):
    by_cda[(comp, disc, age)].append(i)

def _official(rows):
    return [r["ork"] for r in rows]

field_rows = {}   # index raw eventu -> (řádky pole, způsob)
for i, (comp, disc, gen, age, rows) in enumerate(raw_events):
    is_fs = any(r["fs"] for r in rows)
    lcs = {r["perf"]["lc"] for r in rows if r["perf"]}
    if len(lcs) > 1 or any(r["ork"] is None for r in rows):
        continue
    if _ranks(rows, is_fs) == _official(rows):
        field_rows[i] = (rows, "official")
        merge_log["samostatný event, sedí"] += 1
        continue
    found = None
    others = [k for k in by_cda[(comp, disc, age)] if k != i]
    tries = [[k] for k in others] + ([others] if len(others) > 1 else [])
    for combo in tries:
        pool = list(rows)
        for k in combo:
            pool += raw_events[k][4]
        if _rank_within(rows, pool, is_fs) == _official(rows):
            found = (pool, combo)
            break
    if found:
        field_rows[i] = (found[0], "merged")
        merge_log["sloučená kategorie, potvrzeno"] += 1
    else:
        field_rows[i] = (rows, "official-unverified")
        merge_log["oficiální pořadí nejde zreprodukovat"] += 1

for i, (comp, disc, gen, age, rows) in enumerate(raw_events):
    is_fs = any(r["fs"] for r in rows)
    lcs = {r["perf"]["lc"] for r in rows if r["perf"]}
    if i in field_rows:
        pool, how = field_rows[i]
        # kontrola: umístění každého záznamu = oficiální
        for r in rows:
            if how == "official-unverified":
                rank_check["nejde zreprodukovat"] += 1
                rank_bad.append((comp, disc, gen, age, r["score"], r["ork"]))
            else:
                rank_check["shoda"] += 1
        lc = next(iter(lcs)) if lcs else None
        groups = [(lc, rows, pool, how)]
    else:
        groups = []
        for lc in sorted(lcs):
            sub = [r for r in rows if r["perf"] and r["perf"]["lc"] == lc]
            groups.append((lc, sub, sub, "computed"))
        mixed_dropped += sum(1 for r in rows if not r["perf"])

    for lc, own, pool, how in groups:
        # umístění vlastních záznamů: oficiální, nebo dopočtené v rámci úrovně
        if how == "computed":
            own_pl = _ranks(own, is_fs)
            pool_pl = own_pl
        else:
            own_pl = [r["ork"] for r in own]
            pool_pl = [r["ork"] for r in pool] if how == "official" or how == "official-unverified" \
                else _ranks(pool, is_fs)
        # v sloučeném poli zobrazujeme pořadí sloučeného pole, ale vlastní
        # záznamy mají oficiální umístění (ověřené výš)
        if how == "merged":
            pos = {id(r): pl for r, pl in zip(pool, pool_pl)}
            for r, pl in zip(own, own_pl):
                pos[id(r)] = pl
            pool_pl = [pos[id(r)] for r in pool]
        order_ = sorted(range(len(pool)), key=lambda k: (pool_pl[k] if pool_pl[k] is not None else 10**6, -pool[k]["score"]))
        fi = len(fields)
        entries = []
        own_ids = {id(r) for r in own}
        for k in order_:
            r = pool[k]
            entries.append([r["score"], pool_pl[k], cidx(r["club"]), _mini(r["fs"]),
                            perf_pos.get(id(r["perf"]), -1) if r["perf"] else -1])
        for r, pl in zip(own, own_pl):
            if r["perf"]:
                r["perf"]["fv"] = fi
                r["perf"]["pl"] = pl
        fields.append([comp, disc, gen, age, lc, {"official": 1, "merged": 2, "computed": 0, "official-unverified": 3}[how], entries])

for p in perfs:
    if p["comp"] in json_comps and "fv" in p:
        coverage[p["comp"]][0] += 1

if os.environ.get("DEBUG_UNMATCHED"):
    left = [p for p in perfs if p["comp"] in json_comps and "fv" not in p]
    # co zbylo nespárované na straně exportu se stejným (soutěž, disciplína, skóre, věk)
    for p in left[:25]:
        cands = []
        for comp_, disc_, gen_, age_, rows_ in raw_events:
            if comp_ == p["comp"] and disc_ == p["disc"] and AGE_LEVEL.get(age_) == p.get("al"):
                for r in rows_:
                    if r["score"] == p["score"] and not r["perf"]:
                        cands.append(r)
        print("NESPÁROVÁNO", p["comp"][:16], p["disc"], p["score"], p.get("al"),
              [m["name"] + ":" + m["aid"] for m in p["members"]], "| v exportu:", [c["aids"] for c in cands][:2])

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
    "repre": (load_json(os.path.join(DATA, "reprezentace.json")).get("aids") or []) if os.path.exists(os.path.join(DATA, "reprezentace.json")) else [],
    "nextSeason": next_season,
    "fields": fields,
    "clubs": clubs_tbl,
    "perfs": perfs,
}

# ---------------------------------------------------------------- výstup
tpl = open(TEMPLATE, encoding="utf-8").read()
if "__DATA__" not in tpl:
    die("template.html neobsahuje značku __DATA__")
blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
if "</script" in blob.lower():
    die("data obsahují </script, to by rozbilo stránku")
# modul rozboru (analyza.js) se vkládá do stránky při buildu – jediný zdroj
ANALYZA = os.path.join(ROOT, "analyza.js")
if "/*__ANALYZA__*/" not in tpl:
    die("template.html neobsahuje značku /*__ANALYZA__*/")
tpl = tpl.replace("/*__ANALYZA__*/", open(ANALYZA, encoding="utf-8").read())
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
if id_conflict:
    print("  POZOR – ID z exportu patří v datech jinému člověku, NEPŘIŘAZENO (%d):" % len(id_conflict))
    for (mid, nm), who in sorted(id_conflict.items(), key=lambda x: x[0][1]):
        print("      %s má v exportu %s, to ale v datech patří: %s" % (nm, mid, ", ".join(who)))
if id_unified:
    print("  sjednocená ID – v exportu jiné členské ID než v datech, spárováno podle jména (%d):" % len(id_unified))
    for (mid, nm), canon in sorted(id_unified.items(), key=lambda x: x[0][1]):
        print("      %s: %s → %s" % (nm, mid, canon))
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
print("\n=== ROZBOR ===")
for comp in sorted(coverage, key=lambda c: order.get(c, "")):
    a, b = coverage[comp]
    print("  %-34s spárováno %4d / %4d výkonů%s" % (comp, a, b, "" if a == b else "  ← NEÚPLNÉ"))
print("  polí (eventů po úrovních): %d · freestyle s rozpadem: %d" % (len(fields), sum(1 for p in perfs if "fs" in p)))
print("  ve smíšených eventech vynecháno záznamů bez úrovně: %d" % mixed_dropped)
print("  kontrola R = složky podle IJRU:          %s" % dict(rcheck))
for x in rbad[:10]:
    print("      ROZDÍL %s %s oficiálně %s, přepočet %s" % x)
print("  eventy:                                 %s" % dict(merge_log))
print("  kontrola umístění vs. oficiální:         %s" % dict(rank_check))
for x in rank_bad[:15]:
    print("      NEJDE %s %s %s %s skóre %s: oficiálně %s." % x)

if CHECK:
    print("\n--check: index.html nezapsán")
else:
    open(OUT, "w", encoding="utf-8").write(html)
    print("\n  zapsáno %s (%.0f kB)" % (os.path.basename(OUT), os.path.getsize(OUT) / 1024))
