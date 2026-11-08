#!/usr/bin/env python3
"""
Očistí JSON export z výsledkového systému od osobních a technických údajů,
než se smí dostat do tohoto (veřejného) repa.

Použití:
    python3 sanitize.py <zdroj.json> data/<cíl.json>

Repo je veřejné a GitHub Pages servírují každý soubor v něm – i data/.
Surový export obsahuje u každého zásahu do výsledku e-mail a ID člověka,
který ho provedl (rozhodčí, zapisovatelé), a ID zařízení. To sem nepatří.

Odstraňuje se:
  - LastChange, LastJudgeDataChange   (kdo a kdy co měnil, včetně e-mailů)
  - UserEmail, UserID, DeviceID, DeviceSessionID, BatteryLevel  (kdekoli)
  - časová razítka jednotlivých značek rozhodčích (nejsou potřeba, jen nafukují)

Zůstává vše, co je potřeba k výsledkům a rozboru: závodníci (jsou veřejně
ve výsledkovce), skóre, rozpad skóre, značky rozhodčích bez identity.

Po očištění se soubor ještě jednou prohledá na cokoli, co vypadá jako e-mail.
Když něco najde, nic nezapíše a skončí chybou.
"""

import json, re, sys

DROP_KEYS = {
    "LastChange", "LastJudgeDataChange",
    "UserEmail", "UserID", "DeviceID", "DeviceSessionID", "BatteryLevel",
}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def clean(o, in_mark=False):
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if k in DROP_KEYS:
                continue
            if in_mark and k == "timestamp":
                continue
            out[k] = clean(v, in_mark=in_mark or k == "marks")
        return out
    if isinstance(o, list):
        return [clean(x, in_mark) for x in o]
    return o


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    out = clean(data)
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    found = EMAIL.findall(text)
    if found:
        print("CHYBA: po očištění zůstalo %d výskytů něčeho jako e-mail, nic nezapsáno." % len(found), file=sys.stderr)
        sys.exit(1)
    for k in DROP_KEYS:
        if '"%s"' % k in text:
            print("CHYBA: po očištění zůstal klíč %s, nic nezapsáno." % k, file=sys.stderr)
            sys.exit(1)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(text)
    print("očištěno: %s → %s (%.0f kB → %.0f kB)" % (
        src, dst, len(open(src, encoding="utf-8").read()) / 1024, len(text) / 1024))


if __name__ == "__main__":
    main()
