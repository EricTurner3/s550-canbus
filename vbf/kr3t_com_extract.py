# Pull the analog KR3T cluster's CAN receive configuration out of its decompressed firmware image and write
# KR3T-14C026-AC_com.json: every RX ID with its handle, DLC, firmware init bytes, its message-missing monitor
# (and deadline), the frame bits that feed the per-signal monitors, plus the wrench (service required) inputs.
# make_can_notes.py turns that into the notes file. How each table was found is in KR3T_NOTES.md.
#
#   python -I kr3t_com_extract.py
#
# All addresses are runtime addresses (image loads at 0xC100). RH850, little-endian.
import json, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)   # -I drops the script dir; rh850dis.py lives next to this file
from rh850dis import dis, d, BASE

OUT = os.path.join(HERE, "KR3T-14C026-AC_com.json")
GP = 0xFEDD9334

# ---- tables (see KR3T_NOTES.md "Receive path") ----
HASH_KEYS, HASH_N = 0x145434, 223   # CanIf hash: slot = (id + 0x56) % 223, linear probe, FFFF = empty
LIST_IDS = 0x1455F4                 # IDs outside the hash: LE32, sorted descending
HASH_VALS = 0x1456B4                # handle per hash slot
LIST_VALS = 0x145872                # handle per list ID
DLC = 0x1458D4                      # DLC per handle (also the RX buffer length)
RXBUF = 0x145980                    # RX buffer (RAM) per Com handle, 162 entries
INIT = 0x146CBC                     # init value bytes per Com handle (pointer or 0)
RESET_MASK = 0x146F44               # per Com handle: bits put back to the init value by 0x0143E6 (pointer or 0)
NOTIFY = 0x146720                   # per Com handle: callback run on reception (sets monitor flags)
TX_IDS = 0x14520C                   # IDs the cluster transmits, LE32 sorted descending
MON_FLAGS = 0xFEDD9582              # monitor "seen" flag bytes, set by the callbacks
G1 = dict(idx=0x148794, mask=0x148834, n=159, state=0xFEDDB7C8)   # per-signal monitors, fixed 500 ticks
G2 = dict(idx=0x1488D4, mask=0x148960, n=138, state=0xFEDDBA08, timeout=0x1489EC)  # per-message monitors
TICK_MS = 10                        # 500 ticks = 5 s = the manual's wrench timeout
WRENCH_TAB, WRENCH_N = 0x1443C0, 6  # {state getter, value getter, value that requests the wrench}
WRENCH_EN = 0x144408                # [input*3 + config mode] -> 0x4842E = input evaluated, else ignored
WRENCH_EVAL = 0x4842E

u8 = lambda a: d[a - BASE]
u16 = lambda a: struct.unpack_from("<H", d, a - BASE)[0]
u32 = lambda a: struct.unpack_from("<I", d, a - BASE)[0]

# ---- ID <-> handle ----
id_of = {}
for i in range(HASH_N):
    k = u16(HASH_KEYS + 2 * i)
    if k != 0xFFFF:
        id_of[u16(HASH_VALS + 2 * i)] = k
n_list = (HASH_VALS - LIST_IDS) // 4
for i in range(n_list):
    id_of[u16(LIST_VALS + 2 * i)] = u32(LIST_IDS + 4 * i)
n_handles = max(id_of) + 1
assert sorted(id_of) == list(range(n_handles)), "handles are not 0..N-1"
n_com = 0
while (u32(RXBUF + 4 * n_com) >> 16) == 0xFEDD:
    n_com += 1
dlc = [u8(DLC + h) for h in range(n_handles)]
buf = {h: u32(RXBUF + 4 * h) for h in range(n_com)}

def frame_pos(addr):
    """RAM address inside an RX buffer -> (handle, byte)."""
    for h, b in buf.items():
        if b <= addr < b + max(dlc[h], 1):
            return h, addr - b
    return None

def blob(ptr, n):
    return " ".join("%02X" % u8(ptr + i) for i in range(n)) if ptr else None

# ---- reception callbacks: which monitor flag bits each frame sets, and on which frame bit ----
BR_NEED = {"bnl": 1, "bl": 0, "be": 1, "bne": 0}   # branch that SKIPS the flag -> bit value needed to set it

def walk_callback(fn):
    items = []; base = None; pend = None; gate = None
    a = fn
    while a < fn + 0x600:
        L, s = dis(a)
        m = re.match(r"ld\.bu (-?\d+)\[gp\], (\w+)", s)
        if m:
            gate = dict(addr=GP + int(m.group(1)), reg=m.group(2), bit=None, need=None)
        elif gate and re.match(r"(shr|shl) \d+, %s$" % gate["reg"], s):
            op, k = s.split()[0], int(s.split()[1].rstrip(","))
            gate["bit"] = k - 1 if op == "shr" else (0 if k == 31 else None)
        elif gate and re.match(r"andi 0x([0-9A-F]+), %s, r0" % gate["reg"], s):
            m2 = int(s.split()[1].rstrip(","), 16)
            gate["bit"] = m2.bit_length() - 1 if m2 & (m2 - 1) == 0 else None
            gate["andi"] = True
        elif gate and s.split()[0] in BR_NEED and gate["bit"] is not None and gate["need"] is None:
            need = BR_NEED[s.split()[0]]
            if gate.get("andi"):   # andi sets Z when the bit is clear: be skips -> need 1
                need = 1 if s.startswith("be") else 0
            gate["need"] = need
        elif s.startswith("mov 0xFEDD95"):
            base = int(s.split()[1].rstrip(","), 16)
        elif re.match(r"ori 0x[0-9A-F]+, (\w+), \1$", s):
            pend = int(s.split()[1].rstrip(","), 16); preg = s.split()[-1]
        elif pend is not None and (s.startswith("sst.b %s," % preg) or re.match(r"st\.b %s, -?\d+\[gp\]" % preg, s)):
            if s.startswith("sst.b"):
                flag = base + int(re.search(r", (\d+)\[ep\]", s).group(1))
            else:
                flag = GP + int(re.search(r", (-?\d+)\[gp\]", s).group(1))
            g = None
            if gate and gate["need"] is not None:
                p = frame_pos(gate["addr"])
                g = dict(byte=p[1], bit=gate["bit"], need=gate["need"]) if p else dict(ram="0x%X" % gate["addr"], bit=gate["bit"], need=gate["need"])
                gate = None
            items.append(dict(flag_byte=flag - MON_FLAGS, mask=pend, gate=g)); pend = None
        if s == "dispose" or s.startswith("jmp [lp]"):
            break
        a += L
    return items

owner = {}   # (flag byte, bit mask) -> (handle, gate)
cb = {}
for h in range(n_com):
    fn = u32(NOTIFY + 4 * h)
    cb[h] = walk_callback(fn) if fn else []
    for it in cb[h]:
        for k in range(8):
            if it["mask"] & (1 << k):
                owner.setdefault((it["flag_byte"], 1 << k), []).append((h, it["gate"]))

# ---- the two monitor groups ----
monitors = []
for name, g in (("G1", G1), ("G2", G2)):
    for i in range(g["n"]):
        fb, m = u8(g["idx"] + i), u8(g["mask"] + i)
        ticks = u16(g["timeout"] + 2 * i) if "timeout" in g else 500
        src = []
        for k in range(8):
            if m & (1 << k):
                src += [dict(id="0x%03X" % id_of[h], handle=h, gate=gt) for h, gt in owner.get((fb, 1 << k), [])]
        monitors.append(dict(group=name, item=i, flag="b%d&%02X" % (fb, m), timeout_ms=ticks * TICK_MS,
                             state_addr="0x%08X" % (g["state"] + i), sources=src))

# ---- wrench inputs ----
def getter(fn):
    txt = []; a = fn
    for _ in range(6):
        L, s = dis(a); txt.append(s); a += L
        if s.startswith("jmp [lp]"): break
    t = " ; ".join(txt)
    m = re.search(r"ld\.bu (-?\d+)\[gp\]", t)
    addr = GP + int(m.group(1))
    for name, g in (("G1", G1), ("G2", G2)):
        if g["state"] <= addr < g["state"] + g["n"]:
            return dict(monitor="%s#%d" % (name, addr - g["state"]))
    h, byte = frame_pos(addr)
    sh = re.findall(r"(shl|shr) (\d+)", t); an = re.search(r"andi 0x([0-9A-F]+)", t)
    if len(sh) == 2:
        hi = 31 - int(sh[0][1]); lo = hi - (32 - int(sh[1][1])) + 1
    else:
        lo, hi = 0, int(an.group(1), 16).bit_length() - 1
    return dict(id="0x%03X" % id_of[h], byte=byte, bits=[hi, lo])

wrench = []
for i in range(WRENCH_N):
    r = WRENCH_TAB + 12 * i
    st, va = getter(u32(r)), getter(u32(r + 4))
    mon = next(x for x in monitors if "%s#%d" % (x["group"], x["item"]) == st["monitor"])
    modes = [u32(WRENCH_EN + 4 * (3 * i + m)) == WRENCH_EVAL for m in range(3)]
    wrench.append(dict(input=i, monitor=st["monitor"], monitor_sources=mon["sources"], monitor_timeout_ms=mon["timeout_ms"],
                       service_bit=va, requests_when_value=u32(r + 8), active_in_modes=modes))

# ---- per-ID records ----
rx = []
for h in range(n_handles):
    cid = id_of[h]
    present = [dict(group=x["group"], item=x["item"], timeout_ms=x["timeout_ms"]) for x in monitors
               if any(s["handle"] == h and s["gate"] is None for s in x["sources"])]
    gated = [dict(byte=s["gate"]["byte"], bit=s["gate"]["bit"], need=s["gate"]["need"], group=x["group"], item=x["item"],
                  timeout_ms=x["timeout_ms"]) for x in monitors for s in x["sources"]
             if s["handle"] == h and s["gate"] and "byte" in s["gate"]]
    rec = dict(id="0x%03X" % cid, handle=h, dlc=dlc[h], com=h < n_com)
    if h < n_com:
        rec.update(rx_buffer="0x%08X" % buf[h], init_bytes=blob(u32(INIT + 4 * h), dlc[h]),
                   reset_mask=blob(u32(RESET_MASK + 4 * h), dlc[h]), present_monitor=present or None, gated_monitors=gated or None)
    rx.append(rec)
rx.sort(key=lambda r: int(r["id"], 16))
tx = []
a = TX_IDS
while 0 < u32(a) <= 0x7FF:
    tx.append("0x%03X" % u32(a)); a += 4

doc = dict(
    meta=dict(image="vbf/KR3T-14C026-AC_unpacked/KR3T-14C026-AC_decompressed_C000.bin", load_address="0xC100",
              cpu="Renesas RH850 (little-endian)", gp="0x%08X" % GP, tick_ms=TICK_MS,
              counts=dict(rx=n_handles, rx_com=n_com, tx=len(tx), monitors_g1=G1["n"], monitors_g2=G2["n"]),
              unmatched_monitors=[x["group"] + "#%d" % x["item"] for x in monitors if not x["sources"]]),
    rx=rx, tx=sorted(tx, key=lambda s: int(s, 16)), monitors=monitors, wrench=wrench)
json.dump(doc, open(OUT, "w"), indent=1)
print("wrote %s: %d RX (%d Com), %d TX, %d+%d monitors (%d unmatched), %d wrench inputs" % (
    os.path.basename(OUT), n_handles, n_com, len(tx), G1["n"], G2["n"], len(doc["meta"]["unmatched_monitors"]), len(wrench)))
for w in wrench:
    print("  wrench input %d: %-7s %s  value %s b%d bits %s  active %s" % (
        w["input"], w["monitor"], ",".join(s["id"] + ("" if not s["gate"] else " b%d.%d=%d" % (s["gate"]["byte"], s["gate"]["bit"], s["gate"]["need"]))
                                        for s in w["monitor_sources"]),
        w["service_bit"]["id"], w["service_bit"]["byte"], w["service_bit"]["bits"], w["active_in_modes"]))
