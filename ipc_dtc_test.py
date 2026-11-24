# Read / clear the IPC's own DTCs over UDS (0x720 -> IPC, 0x728 <- IPC) while the normal
# s550_cluster.py heartbeat runs, and A/B-test candidate "module present" frames.
#
#   python ipc_dtc_test.py read            read DTCs once
#   python ipc_dtc_test.py clear           clear, then read after the codes have had time to re-set
#   python ipc_dtc_test.py probe           control run, then the same with 0x3A6 + 0x3A7 added
#   python ipc_dtc_test.py probe 223 2E3=0001000000000000@50 085roll 07Eroll ...
#                                          same, with these frames instead (hex id, optional
#                                          payload = 16 hex digits default zeros, optional @ms default 100,
#                                          or a named rolling-counter frame from ROLLERS)
#                                          <id>=roll = every nibble counts 0-F together (default @20)
#                                          file=<freeze frame csv> = every ID in it the heartbeat doesn't send
#                                          000-6FF[=<16 hex>][@1000] = every ID in the range the heartbeat and the
#                                          cluster don't send
#                                          hb = zeros on every heartbeat ID too (all but MUTE_KEEP), in place of
#                                          the heartbeat's own frame
#   python ipc_dtc_test.py scan [000-6FF ...] [file=<freeze frame csv>] [batch=24] [payload=<16 hex>|roll|nm] [ms=100]
#                                          hold batches of IDs, keep the ones that make a code stay away,
#                                          and bisect each down to the single ID. Log: dtc_scan_<time>.txt
#   python ipc_dtc_test.py mute [keep=3B3,42C] [076 200-230 ...]
#                                          the other way round: stop heartbeat frames and find the ones a code needs
#                                          to set (e.g. a frame we send with a frozen counter). keep= are never muted.
#                                          Log: dtc_mute_<time>.txt
#   python ipc_dtc_test.py sweep 42C off 8C0000009C600000 [bits=<16 hex>] [ms=50]
#                                          one heartbeat ID, one payload after another (`off` = not sent,
#                                          bits= every single-bit flip of a payload). Log: dtc_sweep_<time>.txt
#   python ipc_dtc_test.py watch [off|zeros|ff] [secs=6] [230 400-4FF ...]
#                                          for a warning with no DTC behind it: change one heartbeat ID at a time
#                                          (not sent / all 00 / all FF) and watch the cluster. Log: dtc_watch_<time>.txt
#   python ipc_dtc_test.py watch bits 3B3 42C [secs=6] [key]
#                                          one bit of each named heartbeat ID flipped at a time. 0x3B3 byte 0 (the key
#                                          state) is left alone unless `key`
#   python ipc_dtc_test.py supported       every code the cluster can set (19 0A), with status. Log: dtc_supported_<time>.txt
#   python ipc_dtc_test.py dids [DE00-DEFF ...] [mute=46A]
#                                          read every data ID (22 xxxx, default 0000-FFFF) and log the ones that
#                                          answer. mute= stops heartbeat IDs for the run. Log: dtc_dids_<time>.txt
#   python ipc_dtc_test.py ident [session=03] [F10C ...]
#                                          read the F1xx identity DIDs (strategy F188=FR33-14C026, calibration,
#                                          hw/sw versions, serial). No security. Log: fw_ident_<time>.txt
#   python ipc_dtc_test.py memread <addr_hex> <len_hex> [step=100] [session=03]
#                                          ReadMemoryByAddress walk -> fw_mem_<time>.bin. Stops on the first NRC
#                                          (app region usually NRC 33 = needs security).
#   python ipc_dtc_test.py seeds [n=10] [level=31] [session=03] [delay=0.5]
#                                          request the seed (27 31 - this IPC's level, not 01) n times, log each, and
#                                          say if it's static / rotating / session-seeded. Safe (seed requests don't
#                                          lock). Compare against Forscan's seeds on the same module. Log: fw_seeds_<time>.txt
#   python ipc_dtc_test.py seedsniff [secs=600]
#                                          passive: log every seed (67 31) and key (27 32) while Forscan unlocks the
#                                          IPC. Run it, then unlock in Forscan a few times to collect seed/key pairs to
#                                          derive the 3-byte algorithm from. Ctrl+C to stop. Log: fw_seedsniff_<time>.txt
#   python ipc_dtc_test.py upload [start=8000] [end=200000] [chunk=10000] [vbf=vbf/FR33-14C025-AB.vbf]
#                                          the strategy dump: 10 02, 27 01, SBL to RAM + 31 01 0301, then RequestUpload in
#                                          chunks until out of range -> fw_upload_<start>_<time>.bin. Never touches flash.
#   python ipc_dtc_test.py upprobe         read-only: bootloader DIDs + RequestUpload variants. Log: fw_upprobe_<time>.txt
#   python ipc_dtc_test.py sblprobe [vbf=vbf/FR33-14C025-AB.vbf]
#                                          OPT-IN: SBL (flash driver) to RAM + activate (31 01 0301), then retry 0x35.
#                                          Never erases or downloads to flash. Key off after. Log: fw_sblprobe_<time>.txt
#   python ipc_dtc_test.py odo [set=<km>] [session=03]
#                                          FR33 main counter: read (22 404C + 23 RAM) or set RAM via 3D, up or down.
#                                          Permanent once the next km of 0x179 counts commits it. Log: fw_odo_<time>.txt
#   python ipc_dtc_test.py selftest [stop=<s>] [secs=15]
#                                          FR33 routine 0202 (chime, needle sweep, more steps), polls its results.
#                                          stop= ends it early (31 02 02 02). Log: fw_selftest_<time>.txt
#   python ipc_dtc_test.py needle <gauge 0-3> <percent> [<percent> ...] [secs=3]
#                                          FR33: hold one needle at each position in turn (0x3D to its sweep state,
#                                          mode 1), then give it back. Log: fw_needle_<time>.txt
#   python ipc_dtc_test.py trykeys [level=01] [session=02] [start=0] [wait=620]
#                                          test uds_security.L01_CANDIDATES (Ford LFSR secrets) one fresh seed each;
#                                          waits out NRC 36/37 lockouts. Seed/key only. Log: fw_trykeys_<time>.txt
#
#   add `dummy` to any of these to also send s550_cluster.DUMMY_SCHEDULE (interactive_brute_force.py --dummydata)
#
# A candidate with the same ID as a heartbeat frame replaces it while it is on.
# Run with the venv from this folder; it imports s550_cluster (opens COM3), so close s550_cluster.py first.
import sys, time, threading, builtins, re
try:
    from uds_security import KEY_FNS   # per-level key functions; only needed to unlock for programming / diag
except ImportError:
    KEY_FNS = {}                       # file kept out of the repo: tooling still runs, just can't send a key

# hh:mm:ss before every console line (s550_cluster's too, so before it is imported), to match against the cluster by eye
_print = builtins.print
def _stamped_print(*a, **k):
    s = k.get('sep', ' ').join(str(x) for x in a)
    body = s.lstrip('\n')
    _print('\n' * (len(s) - len(body)) + time.strftime('%H:%M:%S ') + body, **{x: v for x, v in k.items() if x != 'sep'})
builtins.print = _stamped_print

import s550_cluster as c
import s550_data

REQ, RSP = 0x720, 0x728
BOOT_WAIT = 6        # s of heartbeat before the first request / clear
ADD_WAIT = 6         # s between probe's candidates starting and its clear: past the wrench's 5 s timeout
SETTLE = 12          # s after a clear: lost-comm codes re-set ~5 s, counter codes up to ~10 s

# candidate frames for `probe`: id -> (payload or function returning one, period s)
CANDIDATES = {
    0x3A6: ([0x00, 0x40, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00], 0.1),   # Side_Detect_L (blind spot)
    0x3A7: ([0x00, 0x40, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00], 0.1),   # Side_Detect_R
}
extra_on = False

# PSCM SteeringPinion_Data, wheel straight (drive.csv). Counter = b5 high nibble,
# b4 = 0xFF - (b0 + b1 + counter + b6 + b7): matches all 10696 frames in 2016_gt350_car/drive.csv. 100 Hz in the car
def pscm_roller():
    cnt = 0
    def roll():
        nonlocal cnt
        cnt = (cnt + 1) & 0x0F
        d = [0x7C, 0xF0, 0x80, 0x00, 0x00, cnt << 4, 0xFF, 0xFE]
        d[4] = (0xFF - (d[0] + d[1] + cnt + d[6] + d[7])) & 0xFF
        return d
    return roll

# 0x07E = the DBC's other SteeringPinion_Data ID, same layout; not in any 2015-17 capture (HS2 / 2018+ only?)
# 0x3CC Lane_Assist_Data3_FD1, sent by the PSCM (lane keeping = 2018+ only). DBC: LatCtlCpbltyDStat_No_Cnt
# 37|4 = b4 bits 5-2, _No_Cs 47|8 = b5, 30 ms. Checksum formula unknown: Ford's usual 0xFF - (data + cnt),
# which with every other byte zero is 0xFF - cnt. 3CCnocs leaves b5 = 0 (should turn -82 into -83 if 0x3CC is it)
def lka_roller(with_cs=True):
    cnt = 0
    def roll():
        nonlocal cnt
        cnt = (cnt + 1) & 0x0F
        d = [0] * 8
        d[4] = cnt << 2
        if with_cs:
            d[5] = (0xFF - cnt) & 0xFF
        return d
    return roll

ROLLERS = {'085roll': (0x085, pscm_roller(), 0.01),
           '07Eroll': (0x07E, pscm_roller(), 0.01),
           '3CCroll': (0x3CC, lka_roller(), 0.03),
           '3CCnocs': (0x3CC, lka_roller(False), 0.03),
           '202roll': (0x202, None, 0.02)}             # filled in below (needs the heartbeat's speed)

# 0x202 speed with the real car's counter: b2 bits 6-3, b1 = 0xFF - (counter + Qf 3 + b6 + b7)
# (checked against 2016_gt350_car/drive.csv). The heartbeat's 0x202 has neither; this replaces it while on.
# The counter goes up by 2 every frame at 50 Hz (14137 of 14559 GT350 steps; ivan's log drops frames, steps 2/4/6)
# and is always odd (b2 bit 3 = 1) in both the GT350 and ivan's GT log. The first version counted 2, 4 .. 0 (bit 3 = 0)
# and didn't clear U0401-82. b0 is 04 in the GT (00 in the GT350, not in the checksum)
def speed_roller():
    cnt = 1
    def roll():
        nonlocal cnt
        cnt = (cnt + 2) & 0x0F
        v = int(c.clusterdata.value_speed) * 175 if c.clusterdata else 0     # same scale as send_speed
        d = [0x04, 0x00, cnt << 3, 0x00, 0x60, 0x00, (v >> 8) & 0xFF, v & 0xFF]
        d[1] = (0xFF - (cnt + 3 + d[6] + d[7])) & 0xFF
        return d
    return roll

ROLLERS['202roll'] = (0x202, speed_roller(), 0.02)

# 0x084 GlobalClock_Data_FD1 from the GWM (DBC), 1 Hz in ivan's GT log: 17 00 01 11 2D 1B 11 00 = 2023, day 273, 17:45:27.
# b0 year - 2000, b2-3 day of the year, b4 minute, b5 second, b6 hour. No counter. Sent here from the PC's clock
def clock_roller():
    def roll():
        t = time.localtime()
        return [t.tm_year - 2000, 0x00, t.tm_yday >> 8, t.tm_yday & 0xFF, t.tm_min, t.tm_sec, t.tm_hour, 0x00]
    return roll

ROLLERS['084clock'] = (0x084, clock_roller(), 1.0)

# Counter hunt without knowing the layout: every nibble of the frame counts 0-F together
# (00 11 22 .. FF), so a 4-bit alive counter is valid wherever it sits. The checksum (if any)
# will be wrong, so look for the code CHANGING (e.g. -82 counter -> -83 checksum), not only clearing.
def nibble_roller():
    cnt = 0
    def roll():
        nonlocal cnt
        cnt = (cnt + 1) & 0x0F
        return [cnt * 0x11] * 8
    return roll

# never held by `scan`: diagnostics, and IDs with known side effects that outlast the test
SCAN_SKIP = set(range(0x700, 0x800)) | {
    0x191,   # display units, stored until the cluster loses power
    0x3AA,   # park aid, continuous chime
}

# ---- sending: heartbeat frames go through c.send_msg, which we wrap so a candidate can replace one
_send_raw = c.send_msg
heartbeat_ids = set()

muted = set()

last_hb = {}         # id -> the heartbeat's latest payload, sent or not

def _send_heartbeat(id, ts, data):
    heartbeat_ids.add(id)
    last_hb[id] = list(data)
    if id in muted or (extra_on and id in CANDIDATES):
        return
    return _send_raw(id, ts, data)

c.send_msg = _send_heartbeat

# TesterPresent keep-alive. 3E 80 = suppress-positive-response (no reply, won't collide with our 0x728 reads).
# Functional 0x7DF so the whole bus's S3 timer stays alive. On only during the diagnostic flows that need the
# session held (unlock / upload / memread); sent well under the ~5 s S3 timeout. Prevents a re-lock mid-dump.
tp_on = False
def _tp_loop():
    while True:
        if tp_on:
            _send_raw(0x7DF, c.start, [0x02, 0x3E, 0x80, 0, 0, 0, 0, 0])
        time.sleep(2.0)

def _extra_loop():
    nxt = {}
    while True:
        now = time.time()
        if extra_on:
            for i, (d, p) in list(CANDIDATES.items()):
                if i not in nxt:
                    nxt[i] = now + (i % 64) / 64 * p     # spread the first sends so a big set doesn't go out as one burst
                if now >= nxt[i]:
                    nxt[i] = now + p
                    _send_raw(i, c.start, d() if callable(d) else d)
        time.sleep(0.002)

# ---- ISO-TP / UDS (single request, reassembled reply) ----
rx_lock = threading.Lock()

def _recv(timeout):
    end = time.time() + timeout
    while time.time() < end:
        m = c.bus.recv(0.05)
        if m and m.arbitration_id == RSP:
            return bytes(m.data)
    return None

FC_STMIN = 0         # ms between the ECU's consecutive frames we ask for; upload raises it if frames get dropped

def _stmin_s(b):
    return b / 1000 if b <= 0x7F else (b - 0xF0) / 1e4 if 0xF1 <= b <= 0xF9 else 0.127

def _send_multi(req):
    # requests over 7 bytes (e.g. 0x35 with 4-byte address + size): first frame, wait for flow control, consecutive
    # frames honouring the block size and STmin it asks for. False if the ECU never sends flow control.
    n = len(req)
    _send_raw(REQ, c.start, [0x10 | (n >> 8), n & 0xFF] + list(req[:6]))
    pos, sn = 6, 1
    while pos < n:
        while True:
            f = _recv(1.0)
            if f is None:
                return False
            if f[0] >> 4 == 3:
                if f[0] & 0x0F == 1:                        # wait
                    continue
                if f[0] & 0x0F == 2:                        # overflow
                    return False
                break
        bs, gap = f[1], _stmin_s(f[2])
        sent = 0
        while pos < n and (bs == 0 or sent < bs):
            chunk = list(req[pos:pos + 7])
            _send_raw(REQ, c.start, [0x20 | sn] + chunk + [0] * (7 - len(chunk)))
            pos += 7; sn = (sn + 1) & 0x0F; sent += 1
            time.sleep(gap)
    return True

def uds(req, timeout=1.0):
    with rx_lock:
        while c.bus.recv(0):          # drop anything queued
            pass
        if len(req) <= 7:
            _send_raw(REQ, c.start, [len(req)] + list(req) + [0] * (7 - len(req)))
        elif not _send_multi(req):
            return None
        t = timeout
        while True:
            f = _recv(t)
            if f is None:
                return None
            pci = f[0] >> 4
            if pci == 0:                                    # single frame
                resp = f[1:1 + (f[0] & 0x0F)]
            elif pci == 1:                                  # first frame -> flow control, collect
                total = ((f[0] & 0x0F) << 8) | f[1]
                resp = bytearray(f[2:8])
                _send_raw(REQ, c.start, [0x30, 0, FC_STMIN, 0, 0, 0, 0, 0])
                sn = 1
                while len(resp) < total:
                    cf = _recv(1.0)
                    if cf is None:
                        return None                         # incomplete: don't decode a partial reply
                    if cf[0] >> 4 == 2:
                        if cf[0] & 0x0F != sn:              # a dropped frame shifts every code after it
                            print('  [isotp] frame lost (got seq {}, wanted {}), discarding reply'.format(cf[0] & 0x0F, sn))
                            return None
                        sn = (sn + 1) & 0x0F
                        resp += cf[1:8]
                resp = bytes(resp[:total])
            else:
                continue
            if resp[0] == 0x7F and len(resp) >= 3 and resp[2] == 0x78:   # response pending
                t = 5.0
                continue
            return resp

def dtc_name(b0, b1, b2):
    return '{}{}{:X}{:02X}-{:02X}'.format('PCBU'[b0 >> 6], (b0 >> 4) & 3, b0 & 0x0F, b1, b2)

def read_dtcs():
    for _ in range(3):                                      # retry a reply that lost a frame
        r = uds([0x19, 0x02, 0xFF])
        if r is not None:
            break
    if r is None:
        print('  no reply from 0x728 (cluster awake? bus wiring?)')
        return None
    if r[0] != 0x59:
        print('  negative reply:', r.hex(' '))
        return None
    codes = {}
    for i in range(3, len(r) - 3, 4):
        codes[dtc_name(r[i], r[i + 1], r[i + 2])] = r[i + 3]
    return codes

def faults(codes):
    # status 0x40 alone = "test not completed this cycle": listed, but not a fault
    return {k: st for k, st in codes.items() if st & 0x0F}

def show(label, codes):
    if codes is None:
        return
    failed = faults(codes)
    print('{} ({} faults, {} not-run listed)'.format(label, len(failed), len(codes) - len(failed)))
    for k, st in sorted(failed.items()):
        print('  {}  status {:02X}{}'.format(k, st, '  lamp' if st & 0x80 else ''))
    for k, st in sorted(codes.items()):
        if k not in failed:
            print('  ({}  status {:02X}{}, not run)'.format(k, st, '  lamp' if st & 0x80 else ''))

def clear():
    r = uds([0x14, 0xFF, 0xFF, 0xFF], timeout=2.0)
    print('  clear:', 'ok' if r and r[0] == 0x54 else ('FAILED ' + (r.hex(' ') if r else 'no reply')))

def clear_and_read(label):
    clear()
    time.sleep(SETTLE)
    codes = read_dtcs()
    show(label, codes)
    return codes or {}

FILE_IDS = set()                                     # candidates that came from file= or a range

def parse_candidates(args):
    # <id>[=<16 hex>][@<ms>] or a ROLLERS name; no payload = zeros, no period = 100 ms
    out = {}
    for a in args:
        if a.startswith('file='):                    # every ID in a freeze-frame style csv, as scan's file=
            import csv
            for r in csv.DictReader(open(a[5:])):
                i = int(r['ID (HEX)'], 16)
                FILE_IDS.add(i)
                out[i] = (list(bytes.fromhex(r['Sample Data'].replace(' ', '').ljust(16, '0')))[:8], 0.1)
            continue
        if a in ROLLERS:
            i, f, p = ROLLERS[a]
            out[i] = (f, p)
            continue
        a, _, ms = a.partition('@')
        i, _, h = a.partition('=')
        h = h.replace(' ', '') or '00' * 8
        if h == 'roll':
            out[int(i, 16)] = (nibble_roller(), int(ms or 20) / 1000)
            continue
        d = (list(bytes.fromhex(h.ljust(16, '0')))[:8], int(ms or 100) / 1000)
        if '-' in i:                                 # a range: every ID in it the heartbeat doesn't send
            lo, hi = (int(x, 16) for x in i.split('-'))
            for j in range(lo, hi + 1):
                FILE_IDS.add(j)
                out[j] = d
            continue
        FILE_IDS.discard(int(i, 16))                 # named on its own: replaces the heartbeat's frame
        out[int(i, 16)] = d
    return out

def open_log(name):
    log_f = open(time.strftime(name + '_%Y%m%d_%H%M%S.txt'), 'w')
    def log(*x):
        line = ' '.join(str(v) for v in x)
        print(line, flush=True)                      # print adds the time itself
        log_f.write(time.strftime('%H:%M:%S ') + line + '\n')
        log_f.flush()
    return log

# ---- scan ----
def scan(args):
    global CANDIDATES, extra_on
    ranges, batch, payload, period, per_id = [], 24, [0] * 8, 0.1, {}
    for a in args:
        if a.startswith('file='):                    # IDs + payloads from a freeze-frame style csv
            import csv
            for r in csv.DictReader(open(a[5:])):
                per_id[int(r['ID (HEX)'], 16)] = list(bytes.fromhex(r['Sample Data'].replace(' ', '').ljust(16, '0')))[:8]
        elif a.startswith('batch='):
            batch = int(a[6:])
        elif a == 'payload=roll':
            payload, period = 'roll', 0.02
        elif a == 'payload=nm':                      # network management: b0 = ID low byte, rest FF
            payload = 'nm'
        elif a.startswith('payload='):
            payload = list(bytes.fromhex(a[8:].ljust(16, '0')))[:8]
        elif a.startswith('ms='):
            period = int(a[3:]) / 1000
        elif '-' in a:
            ranges.append(tuple(int(x, 16) for x in a.split('-')))
        else:
            ranges.append((int(a, 16), int(a, 16)))     # single ID
    ranges = ranges or [(0x000, 0x7FF if per_id else 0x6FF)]

    # what the cluster itself transmits: listen a moment (the adapter does not receive our own frames)
    cluster_tx = set()
    end = time.time() + 2
    with rx_lock:
        while time.time() < end:
            m = c.bus.recv(0.05)
            if m:
                cluster_tx.add(m.arbitration_id)
    skip = SCAN_SKIP | heartbeat_ids | cluster_tx
    ids = sorted({i for lo, hi in ranges for i in range(lo, hi + 1)} - skip)
    if per_id:
        ids = [i for i in ids if i in per_id]

    log = open_log('dtc_scan')

    log('skipping heartbeat', ' '.join('%03X' % i for i in sorted(heartbeat_ids)))
    log('skipping cluster TX', ' '.join('%03X' % i for i in sorted(cluster_tx)))
    log('scanning {} IDs {}, batches of {}, payload {} every {:.0f} ms'.format(
        len(ids), ' '.join('%03X-%03X' % r for r in ranges), batch,
        'from file' if per_id else payload if isinstance(payload, str) else bytes(payload).hex(' '), period * 1000))

    def frame(i):
        return (per_id[i] if i in per_id else nibble_roller() if payload == 'roll' else
                [i & 0xFF, 0] + [0xFF] * 6 if payload == 'nm' else payload, period)

    def run(held):
        global CANDIDATES, extra_on
        while True:
            CANDIDATES = {i: frame(i) for i in held}
            extra_on = bool(held)
            time.sleep(1.0)
            clear()
            time.sleep(SETTLE)
            codes = read_dtcs()
            extra_on = False
            CANDIDATES = {}
            time.sleep(0.5)
            if codes is not None:
                return set(faults(codes))
            log('  no DTC reply (cluster asleep / power?) - retrying in 10 s')
            time.sleep(10)

    ctrl = run([])
    log('control:', ' '.join(sorted(ctrl)))

    def bisect(part, codes):
        if len(part) == 1:
            ok = codes - run(part)                             # confirm the single ID once more
            log('  *** 0x{:03X} keeps away: {}'.format(part[0], ' '.join(sorted(ok)) or 'nothing on repeat'))
            return
        half = len(part) // 2
        for p in (part[:half], part[half:]):
            gone = codes - run(p)
            if gone:
                bisect(p, gone)

    for k in range(0, len(ids), batch):
        b = ids[k:k + batch]
        got = run(b)
        gone, new = ctrl - got, got - ctrl
        log('batch 0x{:03X}-0x{:03X} ({}): gone {}  new {}'.format(
            b[0], b[-1], len(b), ' '.join(sorted(gone)) or '-', ' '.join(sorted(new)) or '-'))
        if gone:
            bisect(b, gone)
    log('done')

# ---- mute ----
# 0x3B3 keeps the cluster on. 0x42C is what makes it count the PCM as present: without it U0401 turns into U0100
MUTE_KEEP = {0x3B3, 0x42C}

def mute_scan(args):
    global muted
    keep, ranges = set(MUTE_KEEP), []
    for a in args:
        if a.startswith('keep='):
            keep = {int(x, 16) for x in a[5:].split(',') if x}
        elif '-' in a:
            ranges.append(tuple(int(x, 16) for x in a.split('-')))
        else:
            ranges.append((int(a, 16), int(a, 16)))
    cand = sorted(i for i in heartbeat_ids - keep
                  if not ranges or any(lo <= i <= hi for lo, hi in ranges))
    fmt = lambda ids: ' '.join('%03X' % i for i in sorted(ids)) or '-'

    log = open_log('dtc_mute')
    log('never muted', fmt(keep))
    log('muting {} heartbeat IDs: {}'.format(len(cand), fmt(cand)))

    def run(sent):
        # heartbeat with only `sent` of the candidates on the bus -> fault codes after a clear
        global muted
        while True:
            muted = set(cand) - set(sent)
            time.sleep(2.0)
            clear()
            time.sleep(SETTLE)
            codes = read_dtcs()
            if codes is not None:
                muted = set()
                return set(faults(codes))
            log('  no DTC reply (cluster asleep / power?) - retrying in 10 s')
            time.sleep(10)

    ctrl = run(cand)
    log('control (nothing muted):', fmt_codes(ctrl))
    got = run([])
    gone = ctrl - got
    log('all muted: gone {}  new {}'.format(fmt_codes(gone), fmt_codes(got - ctrl)))
    if not gone:
        log('no code needs a muted frame: look at the kept frames ({}) or a frame we do not send'.format(fmt(keep)))
        return

    def find(part, codes):
        # a code comes back whenever at least one of the frames it needs is on the bus again
        back = codes & run(part)
        log('  only {} sent: back {}'.format(fmt(part), fmt_codes(back)))
        if not back:
            return
        if len(part) == 1:
            log('  *** 0x{:03X} sets: {}'.format(part[0], fmt_codes(back)))
            return
        half = len(part) // 2
        find(part[:half], back)
        find(part[half:], back)

    half = len(cand) // 2
    find(cand[:half], gone)
    find(cand[half:], gone)
    log('done')

# ---- sweep ----
def sweep(args):
    # one heartbeat ID, one payload after another: which codes are set with each
    global CANDIDATES, extra_on, muted
    id, period, payloads = int(args[0], 16), 0.05, []
    for a in args[1:]:
        if a.startswith('ms='):
            period = int(a[3:]) / 1000
        elif a.startswith('bits='):                  # every single-bit flip of this payload
            base = int(a[5:].ljust(16, '0'), 16)
            payloads += ['%016X' % (base ^ (1 << (63 - n))) for n in range(64)]
        else:
            payloads.append(a)                       # 16 hex digits, or `off` = don't send the ID at all
    log = open_log('dtc_sweep')
    log('sweeping 0x{:03X}, {} payloads every {:.0f} ms'.format(id, len(payloads), period * 1000))

    def run(p):
        global CANDIDATES, extra_on, muted
        while True:
            if p == 'off':
                muted = {id}
            elif p:
                CANDIDATES = {id: (list(bytes.fromhex(p.ljust(16, '0')))[:8], period)}
                extra_on = True
            time.sleep(2.0)
            clear()
            time.sleep(SETTLE)
            codes = read_dtcs()
            extra_on, CANDIDATES, muted = False, {}, set()
            if codes is not None:
                return set(faults(codes))
            log('  no DTC reply (cluster asleep / power?) - retrying in 10 s')
            time.sleep(10)

    ctrl = run(None)
    log('control (heartbeat payload):', fmt_codes(ctrl))
    for p in payloads:
        got = run(p)
        label = p if p == 'off' else bytes.fromhex(p.ljust(16, '0')).hex(' ')
        log('{}: gone {}  new {}{}'.format(label, fmt_codes(ctrl - got), fmt_codes(got - ctrl),
                                          '   ***' if ctrl - got else ''))
    log('done')

# ---- watch ----
def watch(args):
    # no DTCs involved: one heartbeat ID at a time is muted or replaced, the times are logged to match by eye
    global CANDIDATES, extra_on, muted
    how, secs, ranges, key = 'off', 6.0, [], False
    for a in args:
        if a in ('off', 'zeros', 'ff', 'bits'):
            how = a
        elif a == 'key':
            key = True
        elif a.startswith('secs='):
            secs = float(a[5:])
        elif '-' in a:
            ranges.append(tuple(int(x, 16) for x in a.split('-')))
        else:
            ranges.append((int(a, 16), int(a, 16)))
    if how == 'bits':
        return watch_bits(sorted({i for lo, hi in ranges for i in range(lo, hi + 1)}), secs, key)
    skip = {0x3B3} | ({0x179} if how == 'ff' else set())    # 0x179 byte 5 is the odometer's distance counter
    ids = sorted(i for i in heartbeat_ids - skip
                 if not ranges or any(lo <= i <= hi for lo, hi in ranges))
    log = open_log('dtc_watch')
    log('{} IDs, each {} for {:.0f} s, then 3 s back to normal'.format(len(ids), how, secs))
    for i in ids:
        log('0x{:03X} {}'.format(i, how))
        if how == 'off':
            muted = {i}
        else:
            CANDIDATES = {i: ([0x00 if how == 'zeros' else 0xFF] * 8, 0.05)}
            extra_on = True
        time.sleep(secs)
        extra_on, CANDIDATES, muted = False, {}, set()
        time.sleep(3.0)
    log('done')

def watch_bits(ids, secs, key):
    # one bit of a heartbeat frame flipped at a time, on top of whatever the heartbeat would send right now
    global CANDIDATES, extra_on
    log = open_log('dtc_watch')
    for i in ids:
        if i not in last_hb:
            log('0x{:03X} is not a heartbeat ID, skipped'.format(i))
            continue
        # 0x3B3 byte 0 is the key state, flipping it turns the cluster off. `key` includes it
        first = 8 if i == 0x3B3 and not key else 0
        log('0x{:03X}: heartbeat sends {}, bits {} - 63, each flipped for {:.0f} s, then 3 s back to normal'.format(
            i, bytes(last_hb[i]).hex(' '), first, secs))
        for n in range(first, 64):
            byte, mask = n // 8, 0x80 >> (n % 8)
            def flipped(i=i, byte=byte, mask=mask):
                d = list(last_hb[i])
                d[byte] ^= mask
                return d
            log('0x{:03X} byte {} bit {} ({:02X}) {}: {}'.format(
                i, byte, 7 - n % 8, mask, 'cleared' if last_hb[i][byte] & mask else 'set', bytes(flipped()).hex(' ')))
            CANDIDATES = {i: (flipped, 0.05)}
            extra_on = True
            time.sleep(secs)
            extra_on, CANDIDATES = False, {}
            time.sleep(3.0)
    log('done')

# ---- supported / dids ----
def supported():
    # every code the cluster can set (19 0A), failed or not: the list of what it monitors
    r = uds([0x19, 0x0A], timeout=2.0)
    log = open_log('dtc_supported')
    if r is None or r[0] != 0x59:
        log('no list:', r.hex(' ') if r else 'no reply')
        return
    codes = [(dtc_name(r[i], r[i + 1], r[i + 2]), r[i + 3]) for i in range(3, len(r) - 3, 4)]
    log('{} supported codes'.format(len(codes)))
    for k, st in sorted(codes):
        log('{}  status {:02X}{}'.format(k, st, '  lamp' if st & 0x80 else ''))

def dids(args):
    # ask for every data ID (22 xxxx) and log the ones that answer. Run it twice, e.g. as is and with mute=46A
    # (U0146 set), and compare the two logs for the IDs that follow a fault
    global muted
    ranges = []
    for a in args:
        if a.startswith('mute='):
            muted = {int(x, 16) for x in a[5:].split(',') if x}
        else:
            lo, _, hi = a.partition('-')
            ranges.append((int(lo, 16), int(hi or lo, 16)))
    ranges = ranges or [(0x0000, 0xFFFF)]
    log = open_log('dtc_dids')
    log('ranges', ' '.join('%04X-%04X' % r for r in ranges), 'muted', ' '.join('%03X' % i for i in sorted(muted)) or '-')
    if muted:
        time.sleep(SETTLE)                           # let the muted frame's code set first
    found = 0
    for lo, hi in ranges:
        for d in range(lo, hi + 1):
            if d & 0xFF == 0:
                print('  {:04X} ... {} found'.format(d, found), flush=True)
            r = uds([0x22, d >> 8, d & 0xFF], timeout=0.3)
            if r and r[0] == 0x62:
                found += 1
                log('{:04X}: {}'.format(d, r[3:].hex(' ')))
    log('done, {} answered'.format(found))

# ---- firmware / strategy read ----
# The IPC's own software, not a CAN frame. FR33-14C026-xx is the strategy (DID F188); the file we want is its VBF.
# Tier 1 `ident` reads the F1xx identity DIDs (no security, like the DExx as-built already does). Tier 2 `memread`
# tries ReadMemoryByAddress. Tier 3 `upload` is the real strategy dump (RequestUpload -> TransferData), gated behind
# SecurityAccess seed/key - see security() below.

# Standard ISO-14229 / Ford identity DIDs. ASCII where printable, else hex.
IDENT_DIDS = [
    (0xF111, 'ECU core assembly PN'),     (0xF113, 'Ford part number (F113)'),
    (0xF124, 'calibration PN (14C088)'),  (0xF18C, 'ECU serial number'),
    (0xF180, 'boot software id'),         (0xF181, 'application software id'),
    (0xF182, 'application data id'),      (0xF186, 'active session'),
    (0xF187, 'mfr spare part number'),    (0xF188, 'STRATEGY (14C026)'),
    (0xF189, 'strategy version'),         (0xF18A, 'system supplier id'),
    (0xF18B, 'ECU manufacturing date'),   (0xF190, 'VIN'),
    (0xF191, 'ECU hardware number'),      (0xF192, 'supplier hw number'),
    (0xF193, 'supplier hw version'),      (0xF194, 'supplier sw number'),
    (0xF195, 'supplier sw version'),      (0xF1A0, 'Ford F1A0'),
    (0xF110, 'Ford F110'),                (0xF188, 'strategy (repeat ok)'),
]

def _ascii_or_hex(b):
    txt = ''.join(chr(x) if 0x20 <= x < 0x7F else '.' for x in b)
    printable = sum(0x20 <= x < 0x7F for x in b)
    return '{:28} {}'.format(repr(txt)[1:-1], b.hex(' ')) if printable >= len(b) * 0.6 else b.hex(' ')

def ident(args):
    # read the identity DIDs and log them. Add bare DIDs (hex) to read more, e.g. `ident F10C DD01`
    extra = [(int(a, 16), 'extra') for a in args if not a.startswith('session=')]
    sess = next((a[8:] for a in args if a.startswith('session=')), None)
    log = open_log('fw_ident')
    if sess:                                            # 01 default, 03 extended - some DIDs only answer extended
        r = uds([0x10, int(sess, 16)], timeout=2.0)
        log('session {}:'.format(sess), 'ok' if r and r[0] == 0x50 else (r.hex(' ') if r else 'no reply'))
    for did, name in IDENT_DIDS + extra:
        r = uds([0x22, did >> 8, did & 0xFF], timeout=0.5)
        if r is None:
            log('{:04X} {:24} no reply'.format(did, name)); continue
        if r[0] == 0x62 and (r[1] << 8 | r[2]) == did:
            log('{:04X} {:24} {}'.format(did, name, _ascii_or_hex(r[3:])))
        elif r[0] == 0x7F:
            log('{:04X} {:24} nrc {:02X}'.format(did, name, r[2]))   # 31 out-of-range, 33 security, 7E/7F session
        else:
            log('{:04X} {:24} ?? {}'.format(did, name, r.hex(' ')))
    log('done')

def _alfid(addr, size):
    # address-and-length-format id: low nibble = address bytes, high nibble = size bytes
    def nbytes(v): return max(1, (v.bit_length() + 7) // 8)
    an, sn = nbytes(addr), nbytes(size)
    return (sn << 4) | an, an, sn

def memread(args):
    # ReadMemoryByAddress (0x23). `memread <addr_hex> <len_hex> [step=100] [session=03] [sec=03]`
    # Walks addr.. in `step`-byte reads and writes a .bin. The app region NRCs 33 (security) unless sec= unlocks;
    # a window that answers 0x63 is readable. addr/len widths are inferred (pad with leading zeros to force).
    global tp_on
    if len(args) < 2:
        print('  memread <start_addr_hex> <total_len_hex> [step=100] [session=03] [sec=03]'); return
    start = int(args[0], 16); total = int(args[1], 16)
    step = int(next((a[5:] for a in args if a.startswith('step=')), '100'), 16)
    sess = next((a[8:] for a in args if a.startswith('session=')), '03')
    sec = next((a[4:] for a in args if a.startswith('sec=')), None)
    aw = (len(args[0]) + 1) // 2; sw = (len(args[1]) + 1) // 2   # width from how you wrote it
    log = open_log('fw_memread')
    tp_on = True                                        # hold the session while we walk the range
    r = uds([0x10, int(sess, 16)], timeout=2.0)
    log('session {}:'.format(sess), 'ok' if r and r[0] == 0x50 else (r.hex(' ') if r else 'no reply'))
    if sec and not security(int(sec, 16)):
        log('not unlocked at level {} - protected addresses will NRC 33'.format(sec))
    out = open(time.strftime('fw_mem_%Y%m%d_%H%M%S.bin'), 'wb')
    got = 0
    addr = start
    while addr < start + total:
        n = min(step, start + total - addr)
        alf = (sw << 4) | aw
        req = [0x23, alf] + list(addr.to_bytes(aw, 'big')) + list(n.to_bytes(sw, 'big'))
        r = uds(req, timeout=1.0)
        if r is None:
            log('{:0{w}X} no reply (stopping)'.format(addr, w=aw * 2)); break
        if r[0] == 0x63:
            data = r[1:]
            out.write(data); out.flush(); got += len(data)
            if (addr - start) % (step * 16) == 0:
                log('{:0{w}X} .. {} bytes'.format(addr, got, w=aw * 2))
            addr += len(data) or n
        elif r[0] == 0x7F:
            log('{:0{w}X} nrc {:02X} ({}) - stopping'.format(addr, r[2], _nrc(r[2]), w=aw * 2)); break
        else:
            log('{:0{w}X} ?? {} - stopping'.format(addr, r.hex(' '), w=aw * 2)); break
    log('wrote {} bytes to {}'.format(got, out.name)); out.close()
    uds([0x10, 0x01], timeout=1.0); tp_on = False        # default session -> re-lock, stop keep-alive

def _nrc(code):
    return {0x10: 'general reject', 0x11: 'service not supported', 0x12: 'subfn not supported',
            0x13: 'incorrect length/format', 0x14: 'response too long', 0x22: 'conditions not correct',
            0x24: 'request sequence error', 0x31: 'request out of range', 0x33: 'security access denied',
            0x35: 'invalid key', 0x36: 'exceeded attempts', 0x37: 'time delay not expired',
            0x70: 'upload not accepted', 0x72: 'general programming failure', 0x73: 'wrong block seq counter',
            0x7E: 'subfn not in session', 0x7F: 'service not in session'}.get(code, 'nrc %02X' % code)



def security(level=0x01, key_fn=None):
    # SecurityAccess. 27 <level> -> seed; key_fn(seed_bytes) -> key -> 27 <level+1> key.
    # Returns the seed either way. No key_fn, or an all-zero seed (already unlocked): seed only, no key sent.
    # DO NOT loop guesses: 3 bad keys (NRC 36) locks the module for ~10 min (NRC 37). Drop your own algo into key_fn.
    r = uds([0x27, level], timeout=2.0)
    if r is None or r[0] != 0x67:
        print('  seed request nrc', _nrc(r[2]) if r and r[0] == 0x7F else (r.hex(' ') if r else 'no reply'))
        return None
    seed = bytes(r[2:])
    print('  seed (27 {:02X}):'.format(level), seed.hex(' '))
    if not any(seed):
        print('  seed all zero -> already unlocked at this level'); return True
    if key_fn is None:
        key_fn = KEY_FNS.get(level)                     # fall back to the per-level function in uds_security.py
    if key_fn is None:
        print('  no key for level {:02X}: solve it (seedsniff + fw_solvekey.py) and add it to uds_security.KEY_FNS'.format(level))
        return False
    key = key_fn(seed)
    r = uds([0x27, level + 1] + list(key), timeout=2.0)
    ok = bool(r and r[0] == 0x67)
    print('  key:', 'accepted' if ok else ('nrc ' + _nrc(r[2]) if r and r[0] == 0x7F else 'no reply'))
    return ok

def seeds(args):
    # Request the seed (27 31) repeatedly and log each - safe, seed requests don't touch the bad-key lockout counter.
    # Tells you if the seed is static (same every time), rotating per-request, or session/time seeded.
    # This IPC uses level 0x31/0x32 (Ford), not the standard 0x01 - 27 01 just NRCs 7E. `seeds [n=10] [level=31] ...`
    n = int(next((a[2:] for a in args if a.startswith('n=')), '10'))
    level = int(next((a[6:] for a in args if a.startswith('level=')), '31'), 16)
    sess = next((a[8:] for a in args if a.startswith('session=')), '03')
    delay = float(next((a[6:] for a in args if a.startswith('delay=')), '0.5'))
    log = open_log('fw_seeds')
    r = uds([0x10, int(sess, 16)], timeout=2.0)
    log('session {}:'.format(sess), 'ok' if r and r[0] == 0x50 else _reply(r))
    seen = []
    for i in range(n):
        r = uds([0x27, level], timeout=2.0)
        if r is None or r[0] != 0x67:
            log('{:2}  {}'.format(i, _reply(r))); seen.append(None); time.sleep(delay); continue
        s = bytes(r[2:])
        log('{:2}  {}'.format(i, s.hex(' ')))
        seen.append(s)
        time.sleep(delay)
    good = [s for s in seen if s]
    if good:
        uniq = {s.hex() for s in good}
        if len(uniq) == 1:
            verdict = 'STATIC - same seed every request' + (' (all zero = unlocked)' if not any(good[0]) else '')
        elif len(uniq) == len(good):
            verdict = 'ROTATING - a new seed every request'
        else:
            verdict = '{} distinct seeds across {} requests (seeded by session/time?)'.format(len(uniq), len(good))
        log('verdict:', verdict)
        log('length:', len(good[0]), 'bytes')
    log('done - compare these against Forscan\'s 27 31 on the same module')

def seclevels(args):
    # Which SecurityAccess level does a given session offer? Enter the session, request a seed (27 <odd level>)
    # at each candidate, and report seed vs NRC. Safe: seed requests don't touch the lockout counter, and entering
    # a session is not a write. Use this to learn which level the programming session (02) wants for upload.
    # `seclevels [session=02]`
    global tp_on
    sess = next((a[8:] for a in args if a.startswith('session=')), '02')
    log = open_log('fw_seclevels')
    tp_on = True
    r = uds([0x10, int(sess, 16)], timeout=2.0)
    log('session {}:'.format(sess), 'ok' if r and r[0] == 0x50 else _reply(r))
    for lvl in [0x01, 0x03, 0x05, 0x07, 0x09, 0x0B, 0x11, 0x21, 0x31, 0x41, 0x51, 0x61, 0x71]:
        r = uds([0x27, lvl], timeout=1.0)
        if r is None:
            log('27 {:02X}: no reply'.format(lvl))
        elif r[0] == 0x67:
            log('27 {:02X}: SEED {}  <- level available here'.format(lvl, bytes(r[2:]).hex(' ')))
        elif r[0] == 0x7F:
            log('27 {:02X}: nrc {:02X} ({})'.format(lvl, r[2], _nrc(r[2])))
        else:
            log('27 {:02X}: ?? {}'.format(lvl, r.hex(' ')))
    uds([0x10, 0x01], timeout=1.0); tp_on = False
    log('done - a SEED line is a usable level for this session; capture its pairs with seedsniff, solve, add to KEY_FNS')

def seedsniff(args):
    # Passive logger. We can't compute the key, but Forscan can - so let Forscan unlock the IPC and we record every
    # seed (67 31 <seed>) and key (27 32 <key>) off the bus. Both adapters sit on the cluster's HS3, so we see its
    # traffic (same as scan reads arbitrary IDs). Run this, then in Forscan open the IPC and do something that needs
    # security (e.g. a config write or clear) a few times - it re-seeds on each session entry, so you collect several
    # seed/key pairs. Several pairs is what lets you derive a 3-byte algorithm. `seedsniff [secs=600]`  Ctrl+C to stop.
    secs = int(next((a[5:] for a in args if a.startswith('secs=')), '600'))
    log = open_log('fw_seedsniff')
    log('passive capture for {} s - unlock the IPC in Forscan a few times. watching 0x720/0x728 for 27/67 31/32 ...'.format(secs))
    pairs, pending = [], None
    end = time.time() + secs
    try:
        while time.time() < end:
            m = c.bus.recv(0.2)
            if not m or m.arbitration_id not in (REQ, RSP) or (m.data[0] >> 4) != 0:   # single frames only
                continue
            p = bytes(m.data)[1:1 + (m.data[0] & 0x0F)]
            if m.arbitration_id == REQ and len(p) >= 2 and p[0] == 0x27:
                if p[1] & 1 == 0:                               # even subfn = send key (32/34...)
                    key = p[2:]
                    log('key  (27 {:02X}): {}'.format(p[1], key.hex(' ')))
                    if pending is not None:
                        pairs.append((pending, bytes(key)))
                        log('  -> PAIR  seed {}  ->  key {}'.format(pending.hex(' '), key.hex(' ')))
                        pending = None
            elif m.arbitration_id == RSP and len(p) >= 2 and p[0] == 0x67:
                if p[1] & 1:                                    # odd subfn reply = seed (31/33...)
                    pending = bytes(p[2:])
                    log('seed (67 {:02X}): {}'.format(p[1], pending.hex(' ')))
                else:
                    log('key accepted (67 {:02X})'.format(p[1]))
            elif m.arbitration_id == RSP and p[:1] == b'\x7f' and len(p) >= 3 and p[1] == 0x27:
                log('key REJECTED nrc {:02X} ({})'.format(p[2], _nrc(p[2])))
    except KeyboardInterrupt:
        pass
    log('captured {} seed/key pair(s):'.format(len(pairs)))
    for s, k in pairs:
        log('  {}  ->  {}'.format(s.hex(' '), k.hex(' ')))

def unlock(args):
    # Test the key in isolation before risking anything else. `unlock [level=03] [session=03]`
    # One key attempt - the key is derived + verified, so it should pass. (3 wrong keys would lock ~10 min.)
    global tp_on
    level = int(next((a[6:] for a in args if a.startswith('level=')), '03'), 16)
    sess = next((a[8:] for a in args if a.startswith('session=')), '03')
    tp_on = True                                        # hold the session with 3E 80
    r = uds([0x10, int(sess, 16)], timeout=2.0)
    print('  session {}:'.format(sess), 'ok' if r and r[0] == 0x50 else _reply(r))
    print('  unlocked' if security(level) else '  NOT unlocked')
    uds([0x10, 0x01], timeout=1.0); tp_on = False       # back to default session -> re-locks, stop keep-alive

def trykeys(args):
    # Find the level's secret among candidates. `trykeys [level=01] [session=02] [start=0] [wait=620]`
    # One fresh seed + one key per candidate (uds_security.L01_CANDIDATES through ford_key). Seed/key only, no writes.
    # A wrong key is NRC 35. On NRC 36/37 (3 strikes / delay) it waits `wait` s and retries the same candidate.
    # start= resumes from a candidate index after a stop.
    global tp_on
    level = int(next((a[6:] for a in args if a.startswith('level=')), '01'), 16)
    try:
        import uds_security
        ford_key = uds_security.ford_key
        L01_CANDIDATES = getattr(uds_security, 'L%02X_CANDIDATES' % level)     # L01_ / L31_CANDIDATES ...
    except (ImportError, AttributeError):
        print('  needs ford_key + L{:02X}_CANDIDATES in uds_security.py'.format(level)); return
    sess = next((a[8:] for a in args if a.startswith('session=')), '02')
    i = int(next((a[6:] for a in args if a.startswith('start=')), '0'))
    wait = int(next((a[5:] for a in args if a.startswith('wait=')), '620'))
    log = open_log('fw_trykeys')
    tp_on = True
    while i < len(L01_CANDIDATES):
        secret = bytes.fromhex(L01_CANDIDATES[i])
        r = uds([0x10, int(sess, 16)], timeout=2.0)
        if not r or r[0] != 0x50:
            log('session {}: {} - stopping'.format(sess, _reply(r))); break
        r = uds([0x27, level], timeout=2.0)
        if r is None or r[0] != 0x67:
            if r and r[0] == 0x7F and r[2] in (0x36, 0x37):
                log('seed refused ({}), waiting {} s'.format(_nrc(r[2]), wait)); time.sleep(wait); continue
            log('seed request: {} - stopping'.format(_reply(r))); break
        seed = bytes(r[2:])
        if not any(seed):
            log('seed all zero - already unlocked'); break
        key = ford_key(seed, secret)
        r = uds([0x27, level + 1] + list(key), timeout=2.0)
        if r and r[0] == 0x67:
            log('#{} {} ACCEPTED  (seed {} key {})'.format(i, secret.hex(' '), seed.hex(' '), key.hex(' ')))
            log('add to uds_security.KEY_FNS: {:#04x}: lambda s: ford_key(s, bytes.fromhex(\'{}\'))'.format(level, secret.hex(' ')))
            break
        nrc = r[2] if r and r[0] == 0x7F else None
        log('#{} {} rejected: {}'.format(i, secret.hex(' '), _reply(r)))
        if nrc == 0x35:
            i += 1
        elif nrc in (0x36, 0x37):
            i += 1                                      # this candidate was still tested before the lockout
            log('lockout, waiting {} s'.format(wait)); time.sleep(wait)
        else:
            log('unexpected reply - stopping'); break
    else:
        log('no candidate accepted')
    uds([0x10, 0x01], timeout=1.0); tp_on = False

def _upload_range(log, addr, size):
    # one RequestUpload of [addr, addr+size) -> bytes, or (None, nrc) when refused. A TransferData reply that loses a
    # frame is re-requested with the same sequence counter (the ECU repeats the block), slowing the ECU down on retry.
    global FC_STMIN
    r = uds([0x35, 0x00, 0x44] + list(addr.to_bytes(4, 'big')) + list(size.to_bytes(4, 'big')), timeout=2.0)
    if not r or r[0] != 0x75:
        return None, (r[2] if r and r[0] == 0x7F else None)
    data, seq = bytearray(), 1
    while len(data) < size:
        for attempt in range(4):
            r = uds([0x36, seq], timeout=3.0)
            if r and r[0] == 0x76 and r[1] == seq:
                break
            FC_STMIN = min(FC_STMIN + 1, 5)
            log('   36 seq {} retry {} ({}), STmin now {} ms'.format(seq, attempt + 1, _reply(r), FC_STMIN))
        else:
            uds([0x37], timeout=2.0)
            return None, 'transfer failed at {:08X}'.format(addr + len(data))
        if len(r) <= 2:
            break
        data += r[2:]; seq = (seq + 1) & 0xFF
    r = uds([0x37], timeout=3.0)
    log('   {:08X}+{:X}: {} bytes, 37 -> {}'.format(addr, size, len(data), r.hex(' ') if r else 'no reply'))
    return bytes(data[:size]), None

def upload(args):
    # The strategy dump: programming session, level 01, SBL into RAM + activate (as sblprobe), then RequestUpload in
    # chunk-sized pieces from start until the bootloader says out of range. Read-only for flash (no erase, no download
    # to flash). `upload [start=8000] [end=200000] [chunk=10000] [vbf=vbf/FR33-14C025-AB.vbf]`
    # Writes fw_upload_<start>_<time>.bin (contiguous from start). Key off afterwards.
    global tp_on
    start = int(next((a[6:] for a in args if a.startswith('start=')), '8000'), 16)
    end = int(next((a[4:] for a in args if a.startswith('end=')), '200000'), 16)
    chunk = int(next((a[6:] for a in args if a.startswith('chunk=')), '10000'), 16)
    path = next((a[4:] for a in args if a.startswith('vbf=')), 'vbf/FR33-14C025-AB.vbf')
    log = open_log('fw_upload')
    tp_on = True
    if not _boot_sbl(log, path):
        tp_on = False; return
    name = time.strftime('fw_upload_{:08X}_%Y%m%d_%H%M%S.bin'.format(start))
    out = open(name, 'wb')
    addr, t0 = start, time.time()
    while addr < end:
        size = min(chunk, end - addr)
        data, err = _upload_range(log, addr, size)
        while data is None and err == 0x31 and size > 0x100:       # the last chunk may cross the end of the app area
            size //= 2
            data, err = _upload_range(log, addr, size)
        if data is None:
            log('{:08X}: stopped ({})'.format(addr, _nrc(err) if isinstance(err, int) else err)); break
        out.write(data); out.flush(); addr += len(data)
        log('{:08X} done, {} KB in {:.0f} s'.format(addr, (addr - start) // 1024, time.time() - t0))
    out.close()
    log('wrote {:08X}-{:08X} ({} bytes) to {}'.format(start, addr, addr - start, name))
    log('done - key off / power cycle now (nothing in flash was touched)')
    tp_on = False

def upprobe(args):
    # Read-only: why does the bootloader refuse 0x35? One programming session + level 01, then the bootloader's identity
    # DIDs and RequestUpload with several address / length / format variants. Never sends 0x31 routines or 0x34/0x36
    # downloads. An accepted upload is closed straight away with 0x37. `upprobe`  Log: fw_upprobe_<time>.txt
    global tp_on
    log = open_log('fw_upprobe')
    tp_on = True
    r = uds([0x10, 0x02], timeout=2.0)
    log('session 02:', 'ok' if r and r[0] == 0x50 else _reply(r))
    time.sleep(1.5)
    ok = None
    for _ in range(3):
        ok = security(0x01)
        if ok is not None:
            break
        time.sleep(1.0)
    log('level 01:', 'unlocked' if ok else 'NOT unlocked')
    for did in (0xF180, 0xF181, 0xF182, 0xF186, 0xF188, 0xF110, 0xF111, 0xF113, 0xF124, 0xF125, 0xD100, 0xF162):
        r = uds([0x22, did >> 8, did & 0xFF], timeout=1.0)
        log('22 {:04X}: {}'.format(did, _ascii_or_hex(r[3:]) if r and r[0] == 0x62 else _reply(r)))
    tries = [  # (dfi, address, size, addr bytes, size bytes)
        (0x00, 0x00008000, 0x100, 4, 4), (0x00, 0x00000000, 0x100, 4, 4), (0x00, 0x00010000, 0x100, 4, 4),
        (0x00, 0x00008000, 0x100, 4, 2), (0x00, 0x00008000, 0x100, 3, 3), (0x00, 0x00008000, 0x100, 4, 3),
        (0x00, 0x40000000, 0x100, 4, 4), (0x00, 0x40008000, 0x100, 4, 4), (0x00, 0x00FFC000, 0x100, 4, 4),
        (0x00, 0x00200000, 0x100, 4, 4), (0x00, 0x001F0000, 0x100, 4, 4), (0x11, 0x00008000, 0x100, 4, 4),
        (0x00, 0x00008000, 0x10, 4, 4), (0x00, 0x00008000, 0x200000 - 0x8000, 4, 4),
    ]
    for dfi, addr, size, aw, sw in tries:
        req = [0x35, dfi, (sw << 4) | aw] + list(addr.to_bytes(aw, 'big')) + list(size.to_bytes(sw, 'big'))
        r = uds(req, timeout=2.0)
        tag = 'dfi {:02X} addr {:0{}X} size {:X} ({}/{})'.format(dfi, addr, aw * 2, size, aw, sw)
        if r and r[0] == 0x75:
            log(tag, '-> ACCEPTED', r.hex(' '))
            r = uds([0x36, 0x01], timeout=2.0)
            log('   36 01:', r[:18].hex(' ') if r and r[0] == 0x76 else _reply(r))
            log('   37:', _reply(uds([0x37], timeout=2.0)))
        else:
            log(tag, '->', _reply(r))
        uds([0x3E, 0x00], timeout=0.5)
    log('done - key off / power cycle returns to the app')
    tp_on = False

def _vbf_blocks(path):
    # Volvo-format VBF: ASCII header to the closing brace, then blocks of addr(4) len(4) data crc16(2), big-endian
    raw = open(path, 'rb').read()
    hdr_end = raw.index(b'\n}') + 2
    call = re.search(rb'call\s*=\s*0x([0-9A-Fa-f]+)', raw[:hdr_end])
    body, blocks, p = raw[hdr_end:], [], 0
    while p + 8 <= len(body):
        addr, n = int.from_bytes(body[p:p + 4], 'big'), int.from_bytes(body[p + 4:p + 8], 'big')
        blocks.append((addr, body[p + 8:p + 8 + n], body[p + 8 + n:p + 10 + n]))
        p += 10 + n
    return blocks, int(call.group(1), 16) if call else None

def _boot_sbl(log, path):
    # programming session, level 01, the SBL (a flash driver) into RAM, activate it (31 01 03 01 <call>). RAM only:
    # never sends the erase routine (31 01 FF 00) or any download to flash. True when RequestUpload can follow.
    blocks, call = _vbf_blocks(path)
    log('{}: {} block(s) {}, call {}'.format(path, len(blocks),
        ' '.join('{:08X}+{:X}'.format(a, len(d)) for a, d, _ in blocks), '{:08X}'.format(call) if call else '?'))
    if call is None or not (0x40000000 <= call < 0x40010000):
        log('call address is not in RAM - refusing'); return False
    r = uds([0x10, 0x02], timeout=2.0)
    log('session 02:', 'ok' if r and r[0] == 0x50 else _reply(r))
    time.sleep(1.5)                                     # 10 02 resets into the bootloader (display goes dark)
    ok = None
    for _ in range(3):                                  # the bootloader may still be starting: retry a silent seed
        ok = security(0x01)
        if ok is not None:
            break
        time.sleep(1.0)
    if not ok:
        log('level 01 not unlocked - stopping'); return False
    for addr, data, crc in blocks:
        r = uds([0x34, 0x00, 0x44] + list(addr.to_bytes(4, 'big')) + list(len(data).to_bytes(4, 'big')), timeout=2.0)
        log('34 {:08X} {:X}:'.format(addr, len(data)), r.hex(' ') if r and r[0] == 0x74 else _reply(r))
        if not r or r[0] != 0x74:
            return False
        maxblk = int.from_bytes(r[2:2 + (r[1] >> 4)], 'big')
        step = max(1, maxblk - 2)                       # maxNumberOfBlockLength includes SID + sequence counter
        seq = 1
        for p in range(0, len(data), step):
            r = uds([0x36, seq] + list(data[p:p + step]), timeout=3.0)
            if not r or r[0] != 0x76:
                log('36 seq {}: {} - stopping'.format(seq, _reply(r))); return False
            seq = (seq + 1) & 0xFF
        log('36: {} bytes sent in {} block(s)'.format(len(data), seq - 1))
        r = uds([0x37], timeout=3.0)
        log('37: {} (VBF block crc {})'.format(r.hex(' ') if r else 'no reply', crc.hex()))
    r = uds([0x31, 0x01, 0x03, 0x01] + list(call.to_bytes(4, 'big')), timeout=5.0)
    log('31 01 0301 activate SBL:', r.hex(' ') if r and r[0] == 0x71 else _reply(r))
    return bool(r and r[0] == 0x71)

def sblprobe(args):
    # OPT-IN. _boot_sbl, then two small RequestUploads. Key off / power cycle afterwards.
    # `sblprobe [vbf=vbf/FR33-14C025-AB.vbf]`  Log: fw_sblprobe_<time>.txt
    global tp_on
    path = next((a[4:] for a in args if a.startswith('vbf=')), 'vbf/FR33-14C025-AB.vbf')
    log = open_log('fw_sblprobe')
    tp_on = True
    if not _boot_sbl(log, path):
        tp_on = False; return
    for addr, size in ((0x00008000, 0x100), (0x00010000, 0x100)):
        r = uds([0x35, 0x00, 0x44] + list(addr.to_bytes(4, 'big')) + list(size.to_bytes(4, 'big')), timeout=2.0)
        if r and r[0] == 0x75:
            log('35 {:08X} {:X}: ACCEPTED'.format(addr, size), r.hex(' '))
            r = uds([0x36, 0x01], timeout=2.0)
            log('   36 01:', r[:34].hex(' ') if r and r[0] == 0x76 else _reply(r))
            log('   37:', _reply(uds([0x37], timeout=2.0)))
        else:
            log('35 {:08X} {:X}:'.format(addr, size), _reply(r))
    log('done - key off / power cycle now (nothing in flash was touched)')
    tp_on = False

ODO_RAM = 0x40008ABC  # FR33 main counter, whole km in packed BCD (FR33_NOTES.md "Main counter storage")

def _odo_read(log):
    r = uds([0x22, 0x40, 0x4C], timeout=1.0)
    total = int.from_bytes(r[3:6], 'big') if r and r[0] == 0x62 else None
    m = uds([0x23, 0x14] + list(ODO_RAM.to_bytes(4, 'big')) + [0x04], timeout=1.0)
    main = int(m[1:5].hex()) if m and m[0] == 0x63 and all(c in '0123456789' for c in m[1:5].hex()) else None
    log('22 404C total: {}   23 RAM {:08X} main: {}'.format(
        '{:.1f} km'.format(total / 10) if total is not None else _reply(r), ODO_RAM,
        '{} km (BCD {})'.format(main, m[1:5].hex(' ')) if main is not None else _reply(m)))
    return total, main

def odo(args):
    # FR33 main counter. `odo` reads it (22 404C total, 23 RAM main). `odo set=<km>` writes RAM via 3D (no security,
    # up or down) and reads back. RAM only: it becomes permanent when the next km of 0x179 counts commits it to NvM
    # (increment 0x34142); a power cycle before that reverts it. [session=03] sends 10 03 first.
    # Log: fw_odo_<time>.txt
    global tp_on
    log = open_log('fw_odo')
    sess = next((a[8:] for a in args if a.startswith('session=')), None)
    km = next((a[4:] for a in args if a.startswith('set=')), None)
    if sess:
        tp_on = True
        r = uds([0x10, int(sess, 16)], timeout=2.0)
        log('session {}:'.format(sess), 'ok' if r and r[0] == 0x50 else _reply(r))
    total, main = _odo_read(log)
    if km is not None:
        km = int(km)
        if not 0 <= km <= 999999:
            log('set= must be 0..999999 km'); tp_on = False; return
        bcd = bytes.fromhex('{:08d}'.format(km))
        r = uds([0x3D, 0x14] + list(ODO_RAM.to_bytes(4, 'big')) + [0x04] + list(bcd), timeout=2.0)
        log('3D {:08X} <- {} ({} km):'.format(ODO_RAM, bcd.hex(' '), km), r.hex(' ') if r and r[0] == 0x7D else _reply(r))
        _odo_read(log)
    tp_on = False

def selftest(args):
    # FR33 routine 0202 (see vbf/FR33_NOTES.md, Gauge sweep): 10 03, 31 01 02 02, then 31 03 02 02 results every
    # 0.5 s. The sequence chimes, sweeps the needles (2.0 s up, 0.5 s hold, 2.0 s down) and runs more steps after.
    # [stop=<s>] sends 31 02 02 02 that long after the start, [secs=<s>] how long to watch. Log: fw_selftest_<time>.txt
    global tp_on
    log = open_log('fw_selftest')
    secs = float(next((a[5:] for a in args if a.startswith('secs=')), 15))
    stop = next((float(a[5:]) for a in args if a.startswith('stop=')), None)
    tp_on = True
    r = uds([0x10, 0x03], timeout=2.0)
    log('session 03:', 'ok' if r and r[0] == 0x50 else _reply(r))
    r = uds([0x31, 0x01, 0x02, 0x02], timeout=2.0)
    log('31 01 02 02 start:', _reply(r))
    if r and r[0] == 0x7F and r[2] == 0x22:
        # the start gate 0x166FE: power state 2 (key in run), 0x400081E9 set, and speed < 300 raw or not valid
        for addr, n, name in ((0x40008B06, 1, 'power state (wants 02)'), (0x400081E9, 1, 'enable (wants non-zero)'),
                              (0x40007E38, 1, 'speed valid (00 = valid)'), (0x400078F0, 2, 'speed status')):
            g = uds([0x23, 0x14] + list(addr.to_bytes(4, 'big')) + [n], timeout=2.0)
            log('  {:08X} {}:'.format(addr, name), g[1:].hex(' ') if g and g[0] == 0x63 else _reply(g))
    t0 = time.time()
    last = None
    while time.time() - t0 < secs:
        if stop is not None and time.time() - t0 >= stop:
            log('{:5.1f} s  31 02 02 02 stop:'.format(time.time() - t0), _reply(uds([0x31, 0x02, 0x02, 0x02], timeout=2.0)))
            stop = None
        res = _reply(uds([0x31, 0x03, 0x02, 0x02], timeout=2.0))
        if res != last:
            log('{:5.1f} s  31 03 02 02 results:'.format(time.time() - t0), res)
            last = res
        time.sleep(0.5)
    tp_on = False

def needle(args):
    # FR33: hold one needle where we say, through its sweep state in RAM (s550_cluster.SWEEP_RAM, vbf/FR33_NOTES.md):
    # +6 = position (0xFFFF full scale), +E mode 1 = hold there. `needle <gauge 0-3> <percent> [<percent> ...]
    # [secs=3]` steps through the positions, then mode 0 gives the gauge back. No session or key (0x3D)
    log = open_log('fw_needle')
    secs = float(next((a[5:] for a in args if a.startswith('secs=')), 3))
    vals = [a for a in args if '=' not in a]
    base = c.SWEEP_RAM[int(vals[0])]
    for pct in vals[1:]:
        pos = round(max(0.0, min(100.0, float(pct))) / 100 * 0xFFFF)
        ok = c._ram_write(base + 6, pos.to_bytes(2, 'big')) and c._ram_write(base + 0x0E, b'\x01')
        log('gauge {} ({:08X}) at {}% ({:04X}):'.format(vals[0], base, pct, pos), 'ok' if ok else 'no reply')
        time.sleep(secs)
    log('mode 0 (CAN / input value again):', 'ok' if c._ram_write(base + 0x0E, b'\x00') else 'no reply')

def _reply(r):
    return 'nrc ' + _nrc(r[2]) if r and r[0] == 0x7F else (r.hex(' ') if r else 'no reply')

def fmt_codes(codes):
    return ' '.join(sorted(codes)) or '-'

if __name__ == '__main__':
    dummy = 'dummy' in sys.argv
    hb_zeros = 'hb' in sys.argv
    sys.argv = [a for a in sys.argv if a not in ('dummy', 'hb')]
    mode = sys.argv[1] if len(sys.argv) > 1 else 'read'
    if mode == 'probe' and len(sys.argv) > 2:
        CANDIDATES = parse_candidates(sys.argv[2:])
    c.SWEEP = False                                  # its 0x3D writes would cross this script's requests
    if dummy:                                        # same as interactive_brute_force.py --dummydata
        c.SCHEDULE.extend(c.DUMMY_SCHEDULE)
        print('* dummy data: 0x217 0x415 0x85 0x91 0x200 0x82 0x230')
    c.clusterdata = s550_data.s550_ipc('none')        # defaults, no game
    threading.Thread(target=c._scheduler, daemon=True).start()
    threading.Thread(target=_extra_loop, daemon=True).start()
    threading.Thread(target=_tp_loop, daemon=True).start()
    c.keys()                                         # arrow keys / enter -> menu nav, same as s550_cluster.py
    print('* heartbeat running, waiting {} s for the cluster'.format(BOOT_WAIT))
    time.sleep(BOOT_WAIT)

    if mode == 'read':
        show('DTCs', read_dtcs())
    elif mode == 'clear':
        show('before clear', read_dtcs())
        clear_and_read('{} s after clear'.format(SETTLE))
    elif mode == 'scan':
        scan(sys.argv[2:])
    elif mode == 'mute':
        mute_scan(sys.argv[2:])
    elif mode == 'sweep':
        sweep(sys.argv[2:])
    elif mode == 'watch':
        watch(sys.argv[2:])
    elif mode == 'supported':
        supported()
    elif mode == 'dids':
        dids(sys.argv[2:])
    elif mode == 'ident':
        ident(sys.argv[2:])
    elif mode == 'memread':
        memread(sys.argv[2:])
    elif mode == 'unlock':
        unlock(sys.argv[2:])
    elif mode == 'upload':
        upload(sys.argv[2:])
    elif mode == 'trykeys':
        trykeys(sys.argv[2:])
    elif mode == 'upprobe':
        upprobe(sys.argv[2:])
    elif mode == 'sblprobe':
        sblprobe(sys.argv[2:])
    elif mode == 'odo':
        odo(sys.argv[2:])
    elif mode == 'selftest':
        selftest(sys.argv[2:])
    elif mode == 'needle':
        needle(sys.argv[2:])
    elif mode == 'seeds':
        seeds(sys.argv[2:])
    elif mode == 'seedsniff':
        seedsniff(sys.argv[2:])
    elif mode == 'seclevels':
        seclevels(sys.argv[2:])
    elif mode == 'probe':
        cluster_tx = set()                           # what the cluster transmits itself, as scan
        end = time.time() + 2
        with rx_lock:
            while FILE_IDS and time.time() < end:
                m = c.bus.recv(0.05)
                if m:
                    cluster_tx.add(m.arbitration_id)
        for i in FILE_IDS & (heartbeat_ids | SCAN_SKIP | cluster_tx):    # a file / range only adds IDs, the heartbeat keeps its own
            del CANDIDATES[i]
        if hb_zeros:                                 # a set bit in a frame we already send: zero them all at once
            hb = sorted(heartbeat_ids - MUTE_KEEP - set(CANDIDATES))
            CANDIDATES.update({i: ([0] * 8, 0.1) for i in hb})
            print('* heartbeat IDs zeroed:', ' '.join('%03X' % i for i in hb))
        print('* {} candidates, {:.0f} frames/s'.format(len(CANDIDATES), sum(1 / p for _, p in CANDIDATES.values())))
        base = clear_and_read('CONTROL (heartbeat only)')
        extra_on = True
        print('* adding', ', '.join(hex(i) for i in CANDIDATES) if len(CANDIDATES) <= 40 else '{} IDs'.format(len(CANDIDATES)))
        n0, t0 = sum(c.sent_count[i] for i in list(CANDIDATES)), time.time()
        time.sleep(ADD_WAIT)
        n1 = sum(c.sent_count[i] for i in list(CANDIDATES))
        print('* handed to the adapter: {:.0f} candidate frames/s, {} failed'.format(
            (n1 - n0) / (time.time() - t0), sum(c.fail_count.values())))
        print('* clearing')
        test = clear_and_read('WITH candidates')
        base, test = set(faults(base)), set(faults(test))
        gone = sorted(base - test)
        new = sorted(test - base)
        print('\nRESULT: gone with candidates:', gone or 'none', '| new:', new or 'none')
        print('Watch the cluster too: blind-spot lamp / charge / wrench while candidates are on.')
        print('Candidates stay on. Arrows / enter navigate the menu. Ctrl+C to stop.')
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
