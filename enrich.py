"""
Rozbor výsledků z JSON exportů: pořadí v eventu, rozpad freestylu a podklady
pro záložku s rozborem. Volá se z build.py.

Všechny hodnoty v rozpadu jsou převzaté z oficiálních výsledků (EntryScoreData)
a z výsledků jednotlivých rozhodčích (JudgeResults, TallySheet), které počítá
samotný výsledkový systém. Nic se tu neodhaduje – odhady (např. „kolik by měla
bez chyb“) se počítají až v prohlížeči a jsou tam tak i označené.

Typy rozhodčích (JudgeResults.meta.judgeTypeId):
  P        prezentace – kategorie ent/form/music/crea/vari na škále 0–24
  T        technický – missy, breaky, porušení, povinné prvky
  Dp Dm Dr obtížnost SR: power/gymnastika, multiples, rope manipulation
  Da Db    obtížnost Wheel
  Dj Dt    obtížnost Double Dutch: jumper, turner
  Shj S    rychlost: hlavní rozhodčí (chybné starty) a počítající
"""

from collections import defaultdict

SR_LEVELS = ["0.5", "1", "2", "3", "4", "5", "6", "7", "8"]
DD_LEVELS = ["1", "2", "3", "4", "5"]
PRES_CATS = ["ent", "form", "music", "crea", "vari"]


def r2(x):
    return None if x is None else round(float(x) + 0.0, 2)


def r3(x):
    return None if x is None else round(float(x) + 0.0, 3)


def ijru_avg(vals):
    """Průměrování podle IJRU: 2 → průměr; 3 → dva nejbližší (při shodě ve
    prospěch závodníka, tj. dva vyšší); 4+ → bez nejvyššího a nejnižšího."""
    v = sorted(x for x in vals if x is not None)
    n = len(v)
    if n == 0:
        return None
    if n == 1:
        return v[0]
    if n == 2:
        return (v[0] + v[1]) / 2
    if n == 3:
        d1, d2 = v[1] - v[0], v[2] - v[1]
        return (v[0] + v[1]) / 2 if d1 < d2 else (v[1] + v[2]) / 2
    return sum(v[1:-1]) / (n - 2)


def judges_by_type(entry):
    """typ rozhodčího -> seznam (tally, result) za všechny protokoly záznamu"""
    out = defaultdict(list)
    for sc in entry.get("Scores") or []:
        js = sc.get("JudgeScoreData") or {}
        jr = js.get("JudgeResults") or {}
        t = (jr.get("meta") or {}).get("judgeTypeId")
        if not t:
            continue
        out[t].append(((js.get("TallySheet") or {}).get("tally") or {}, jr.get("result") or {}))
    return out


def level_profile(sheets, levels, dd=False):
    """Průměrný počet prvků v každé úrovni přes rozhodčí jednoho typu.
    U Double Dutch se plus/minus varianta úrovně počítá do základní úrovně."""
    if not sheets:
        return None
    acc = [0.0] * len(levels)
    for tally, _ in sheets:
        for i, lv in enumerate(levels):
            n = tally.get("diffL" + lv, 0) or 0
            if dd:
                n += (tally.get("diffL%sPlus" % lv, 0) or 0) + (tally.get("diffL%sMinus" % lv, 0) or 0)
            acc[i] += n
    k = len(sheets)
    prof = [round(a / k, 2) for a in acc]
    return prof if any(prof) else None


def freestyle(res, judges):
    """Kompaktní rozpad freestylu. Klíče:
      R D P Q M      oficiální výsledek a jeho složky
      d              obtížnost po typech rozhodčích
      q              počet nesplněných povinných prvků po kategoriích
      am ab av       missy, breaky, porušení (průměr technických rozhodčích)
      xm xb xv       srážky za ně jako podíl (M = 1 − (xm + xb + xv))
      pc             prezentace po kategoriích (0–24, průměr dle IJRU)
      pm             kolik missů viděli rozhodčí prezentace (strhávají je
                     v každé kategorii prezentace)
      lv             rozložení úrovní prvků po typech rozhodčích obtížnosti
      fm             model: sr | wh | dd
    """
    fs = {}
    for k in ("R", "D", "P", "Q", "M"):
        if k in res:
            fs[k] = r2(res[k])
    if "dP" in res or "dM" in res or "dR" in res:
        fs["fm"] = "sr"
        fs["d"] = {k: r2(res[src]) for k, src in (("p", "dP"), ("m", "dM"), ("r", "dR")) if src in res}
    elif "dA" in res or "dB" in res:
        fs["fm"] = "wh"
        fs["d"] = {k: r2(res[src]) for k, src in (("a", "dA"), ("b", "dB")) if src in res}
    elif "Dj" in res or "Dt" in res:
        fs["fm"] = "dd"
        fs["d"] = {k: r2(res[src]) for k, src in (("j", "Dj"), ("t", "Dt")) if src in res}
    q = {k: res[src] for k, src in (("p", "qP"), ("m", "qM"), ("r", "qR"), ("i", "qI")) if src in res}
    if q:
        fs["q"] = q
    for k in ("am", "ab", "av"):
        if k in res:
            fs[k] = r2(res[k])
    # srážky jako podíly (M = 1 − (m + b + v)) – oficiální hodnoty, ať se
    # „kolik stály chyby“ počítá z výsledků, ne z vlastního přepočtu
    for k in ("m", "b", "v"):
        if k in res:
            fs["x" + k] = r3(res[k])

    pj = judges.get("P") or []
    if pj:
        fs["pc"] = {c: r2(ijru_avg([t.get(c) for t, _ in pj])) for c in PRES_CATS}
        fs["pm"] = r2(ijru_avg([t.get("miss") for t, _ in pj]))

    lv = {}
    if fs.get("fm") == "sr":
        for key, jt in (("p", "Dp"), ("m", "Dm"), ("r", "Dr")):
            prof = level_profile(judges.get(jt), SR_LEVELS)
            if prof:
                lv[key] = prof
    elif fs.get("fm") == "wh":
        for key, jt in (("a", "Da"), ("b", "Db")):
            prof = level_profile(judges.get(jt), SR_LEVELS)
            if prof:
                lv[key] = prof
    elif fs.get("fm") == "dd":
        for key, jt in (("j", "Dj"), ("t", "Dt")):
            prof = level_profile(judges.get(jt), DD_LEVELS, dd=True)
            if prof:
                lv[key] = prof
    if lv:
        fs["lv"] = lv
    return fs


def recompute_R(fs):
    """Kontrolní přepočet výsledku ze složek podle IJRU TM.
    SR, Wheel: R = D × (1 + P) × Q × M ;  DD: R = D × (1 + P) × M"""
    D, P, M = fs.get("D"), fs.get("P"), fs.get("M")
    if D is None or P is None or M is None:
        return None
    if fs.get("fm") == "dd":
        return round(D * (1 + P) * M, 2)
    Q = fs.get("Q", 1.0)
    return round(D * (1 + P) * Q * M, 2)


def rank_group(items, is_fs):
    """Pořadí v jednom eventu. items = [(perf, fs nebo None)].
    Rychlost: podle R, shoda = stejné místo, další n+m.
    Freestyle tie-break podle IJRU: M → Q → P → D, pak stejné místo."""
    def key(it):
        p, fs = it
        if is_fs and fs:
            return (p["score"], fs.get("M", 0), fs.get("Q", 1), fs.get("P", 0), fs.get("D", 0))
        return (p["score"],)
    srt = sorted(items, key=key, reverse=True)
    ranks = {}
    prev, place = None, 0
    for i, it in enumerate(srt):
        k = key(it)
        if k != prev:
            place = i + 1
            prev = k
        ranks[id(it[0])] = place
    return ranks
