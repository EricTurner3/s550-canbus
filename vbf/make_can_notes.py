# Build the per-CAN-ID notes for the analog KR3T cluster: KR3T-14C026-AC_CAN_Notes.json (canonical) and .md (view).
# Firmware facts come from KR3T-14C026-AC_com.json (run kr3t_com_extract.py first), names from database.md and the
# Ford DBC, real payloads from this car's freeze frame. Hand-filled fields (required_bytes, notes) in the JSON are
# kept across re-runs.
#
#   python -I kr3t_com_extract.py && python -I make_can_notes.py
import csv, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
COM  = os.path.join(HERE, "KR3T-14C026-AC_com.json")
DB   = os.path.join(REPO, "database.md")
DBC  = os.path.join(REPO, "other_refs", "VehicleCAN.dbcx")              # Ford signal DB (2018+/FD1 arch)
FF   = os.path.join(REPO, "other_refs", "2015GTPremium_FreezeFrame.csv")  # one real sample per ID, this car
JOUT = os.path.join(HERE, "KR3T-14C026-AC_CAN_Notes.json")
MOUT = os.path.join(HERE, "KR3T-14C026-AC_CAN_Notes.md")
HAND = ("required_bytes", "notes")   # hand-filled, preserved on re-run


def parse_database(path):
    """{id: {name, db_status}} from the database.md Index table."""
    out = {}
    row = re.compile(r"^\|\s*\**`0x([0-9A-Fa-f]+)`\**\s*\|\s*\**(.*?)\**\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$")
    for line in open(path, encoding="utf-8"):
        m = row.match(line.strip())
        if m and m.group(2).strip().lower() != "name":
            out[int(m.group(1), 16)] = {"name": m.group(2).strip().strip("*").replace("**", "").strip(),
                                         "db_status": m.group(3).strip()}
    return out


def parse_dbc(path):
    """{id: {dbc_name, node, signals: [{name, bit, len, cover}]}}. bit = DBC start bit; cover = (byte, bit) pairs,
    following Motorola order for @0 signals."""
    out = {}; cur = None
    bo = re.compile(r"^BO_ (\d+) (\w+): (\d+) (\w+)")
    sg = re.compile(r"^ SG_ (\w+) : (\d+)\|(\d+)@([01])")
    for ln in open(path, encoding="latin1"):
        m = bo.match(ln)
        if m:
            idv = int(m.group(1)); cur = idv if idv <= 0x7FF else None
            if cur is not None:
                out[cur] = {"dbc_name": m.group(2), "node": m.group(4), "signals": []}
            continue
        s = sg.match(ln)
        if s and cur is not None:
            st, n, order = int(s.group(2)), int(s.group(3)), s.group(4)
            cover = []; p = st
            for _ in range(n):
                cover.append((p // 8, p % 8))
                p = (p - 1 if p % 8 else p + 15) if order == "0" else p + 1
            out[cur]["signals"].append({"name": s.group(1), "bit": st, "len": n, "cover": cover})
    return out


def parse_freezeframe(path):
    out = {}
    with open(path, newline="", encoding="latin1") as f:
        for row in csv.DictReader(f):
            try:
                out[int(row["ID (HEX)"], 16)] = {"sample_bytes": " ".join(row["Sample Data"].split()),
                                                 "freeze_desc": row.get("Description", "").strip()}
            except ValueError:
                pass
    return out


def dbc_signal(dbc, idv, byte, bit):
    for s in dbc.get(idv, {}).get("signals", []):
        if (byte, bit) in s["cover"]:
            return s["name"]
    return None


def main():
    com = json.load(open(COM))
    db, dbc, ff = parse_database(DB), parse_dbc(DBC), parse_freezeframe(FF)
    prev = {}
    if os.path.exists(JOUT):
        try:
            prev = {m["id"]: m for m in json.load(open(JOUT)).get("messages", [])}
        except (ValueError, KeyError):
            pass

    rx = {int(r["id"], 16): r for r in com["rx"]}
    tx = {int(t, 16) for t in com["tx"]}
    # wrench role per ID
    wrench = {}
    for w in com["wrench"]:
        active = all(w["active_in_modes"])
        for s in w["monitor_sources"]:
            g = s["gate"]
            need = ("received at least every %d ms" % w["monitor_timeout_ms"] +
                    (" with byte%d bit%d = %d" % (g["byte"], g["bit"], g["need"]) if g else ""))
            wrench.setdefault(int(s["id"], 16), []).append(dict(input=w["input"], active=active, role="watchdog", need=need))
        sb = w["service_bit"]
        wrench.setdefault(int(sb["id"], 16), []).append(dict(
            input=w["input"], active=active, role="service bit",
            need="byte%d bit%d != %d" % (sb["byte"], sb["bits"][0], w["requests_when_value"]),
            dbc=dbc_signal(dbc, int(sb["id"], 16), sb["byte"], sb["bits"][0])))

    messages = []
    for idv in sorted(set(rx) | tx):
        r = rx.get(idv, {}); dinfo = dbc.get(idv, {}); finfo = ff.get(idv, {})
        pm = r.get("present_monitor")
        rec = {
            "id": "0x%03X" % idv,
            "direction": ("rx+tx" if idv in rx and idv in tx else "rx" if idv in rx else "tx"),
            "handle": r.get("handle"),
            "dlc": r.get("dlc"),
            "name": db.get(idv, {}).get("name") or dinfo.get("dbc_name") or finfo.get("freeze_desc") or None,
            "db_status": db.get(idv, {}).get("db_status"),
            "dbc_name": dinfo.get("dbc_name"),
            "node": dinfo.get("node"),
            "sample_bytes": finfo.get("sample_bytes"),          # real payload from this car (freeze frame)
            "init_bytes": r.get("init_bytes"),                  # firmware default before the first frame
            "reset_mask": r.get("reset_mask"),                  # bits the firmware puts back to init_bytes
            # message-missing deadline: ms, 0 = configured but not monitored, None = no watchdog for this ID
            "deadline_ms": pm[0]["timeout_ms"] if pm else None,
            "watchdog": ("%s#%d" % (pm[0]["group"], pm[0]["item"])) if pm else None,
            "bit_monitors": [dict(byte=g["byte"], bit=g["bit"], need=g["need"], monitor="%s#%d" % (g["group"], g["item"]),
                                  timeout_ms=g["timeout_ms"], dbc=dbc_signal(dbc, idv, g["byte"], g["bit"]))
                             for g in r.get("gated_monitors") or []] or None,
            "wrench": wrench.get(idv),
            "signals": [{k: s[k] for k in ("name", "bit", "len")} for s in dinfo.get("signals", [])] or None,
            "required_bytes": None,
            "notes": "",
        }
        p = prev.get(rec["id"])
        if p:
            for k in HAND:
                if p.get(k) not in (None, "", []):
                    rec[k] = p[k]
        messages.append(rec)

    meta = dict(com["meta"])
    meta.update(
        title="Analog IPC (2019 GT 401A, KR3T-14C026-AC) CAN message notes",
        description="Every CAN ID the analog cluster receives or transmits, from its firmware (kr3t_com_extract.py), "
                    "with names from database.md / the Ford DBC and real payloads from this car's freeze frame. "
                    "Edit required_bytes / notes here; everything else is regenerated.",
        sources=dict(firmware="KR3T-14C026-AC_com.json (authoritative for this cluster)",
                     database_md="names / bench status", dbc="other_refs/VehicleCAN.dbcx (2018+ arch, names only)",
                     freeze_frame="other_refs/2015GTPremium_FreezeFrame.csv"),
        wrench=com["wrench"],
        generated_by="vbf/make_can_notes.py")
    json.dump(dict(meta=meta, messages=messages), open(JOUT, "w", encoding="utf-8"), indent=1)

    # ---- Markdown view ----
    L = ["# %s" % meta["title"], "",
         "> Generated by `vbf/make_can_notes.py` from `KR3T-14C026-AC_com.json` (firmware), `database.md`, the Ford DBC "
         "and this car's freeze frame. **`%s` is the canonical copy**; this file is overwritten." % os.path.basename(JOUT), "",
         "%d RX IDs (%d through Com), %d TX IDs. Image loads at %s, %s. Deadlines are message-missing timeouts "
         "(10 ms ticks); `0` = configured but not monitored, blank = no watchdog." % (
             meta["counts"]["rx"], meta["counts"]["rx_com"], meta["counts"]["tx"], meta["load_address"], meta["cpu"]), "",
         "## Wrench (powertrain malfunction / service required)", "",
         "Requested when any **active** input's watchdog times out (missing 5 s) or its service bit is set. "
         "Evaluated by `0x0483EC`, inputs at `0x1443C0`, enable per config mode at `0x144408`.", "",
         "| # | Active | Watchdog (must keep arriving) | Service bit (must stay clear) |", "|---|---|---|---|"]
    for w in com["wrench"]:
        src = ", ".join("`%s`%s" % (s["id"], " byte%d bit%d = %d" % (s["gate"]["byte"], s["gate"]["bit"], s["gate"]["need"]) if s["gate"] else "")
                        for s in w["monitor_sources"])
        sb = w["service_bit"]
        L.append("| %d | %s | %s %s, %d ms | `%s` byte%d bit%d (%s) |" % (
            w["input"], "**yes**" if all(w["active_in_modes"]) else "no", w["monitor"], src, w["monitor_timeout_ms"],
            sb["id"], sb["byte"], sb["bits"][0], dbc_signal(dbc, int(sb["id"], 16), sb["byte"], sb["bits"][0]) or "?"))
    L += ["", "## Messages", "",
          "| ID | Dir | DLC | Name | Deadline | Bit monitors | Firmware init | Sample (this car) | Notes |",
          "|---|---|---|---|---|---|---|---|---|"]
    for m in messages:
        bits = "; ".join("b%d.%d=%d %s" % (b["byte"], b["bit"], b["need"], b["dbc"] or "") for b in m["bit_monitors"] or [])
        L.append("| `%s` | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            m["id"], m["direction"], m["dlc"] if m["dlc"] is not None else "", (m["name"] or "").replace("|", "\\|"),
            "" if m["deadline_ms"] is None else m["deadline_ms"], bits.strip(),
            "`%s`" % m["init_bytes"] if m["init_bytes"] else "", "`%s`" % m["sample_bytes"] if m["sample_bytes"] else "",
            ((("**wrench input %s** " % "/".join(sorted({str(w["input"]) for w in m["wrench"] if w["active"]}))) if m["wrench"] and any(w["active"] for w in m["wrench"]) else "")
             + (m["notes"] or "")).replace("|", "\\|")))
    L.append("")
    open(MOUT, "w", encoding="utf-8").write("\n".join(L))
    print("wrote %s and %s: %d messages" % (os.path.basename(JOUT), os.path.basename(MOUT), len(messages)))


if __name__ == "__main__":
    main()
