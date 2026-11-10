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
#   python ipc_dtc_test.py scan [000-6FF ...] [file=<freeze frame csv>] [batch=24] [payload=<16 hex>|roll|nm] [ms=100]
#                                          hold batches of IDs, keep the ones that make a code stay away,
#                                          and bisect each down to the single ID. Log: dtc_scan_<time>.txt
#
#   add `dummy` to any of these to also send s550_cluster.DUMMY_SCHEDULE (interactive_brute_force.py --dummydata)
#
# A candidate with the same ID as a heartbeat frame replaces it while it is on.
# Run with the venv from this folder; it imports s550_cluster (opens COM3), so close s550_cluster.py first.
import sys, time, threading
import can
import s550_cluster as c
import s550_data

REQ, RSP = 0x720, 0x728
SETTLE = 12          # s after a clear: lost-comm codes re-set ~5 s, counter codes up to ~10 s

# candidate frames for `probe`: id -> (payload or function returning one, period s)
CANDIDATES = {
    0x3A6: ([0x00, 0x40, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00], 0.1),   # Side_Detect_L (blind spot)
    0x3A7: ([0x00, 0x40, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00], 0.1),   # Side_Detect_R
}
extra_on = False

# PSCM SteeringPinion_Data, wheel straight (drive.csv). Counter = b5 high nibble,
# b4 = 0xFF - (b0 + b1 + counter + b6 + b7): matches all 10696 frames in can/drive.csv. 100 Hz in the car
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
# (checked against can/drive.csv). The heartbeat's 0x202 has neither; this replaces it while on.
# The counter goes up by 2 every frame at 50 Hz (14137 of 14559 GT350 steps; ivan's log drops frames, steps 2/4/6)
def speed_roller():
    cnt = 0
    def roll():
        nonlocal cnt
        cnt = (cnt + 2) & 0x0F
        v = int(c.clusterdata.value_speed) * 175 if c.clusterdata else 0     # same scale as send_speed
        d = [0x00, 0x00, cnt << 3, 0x00, 0x60, 0x00, (v >> 8) & 0xFF, v & 0xFF]
        d[1] = (0xFF - (cnt + 3 + d[6] + d[7])) & 0xFF
        return d
    return roll

ROLLERS['202roll'] = (0x202, speed_roller(), 0.02)

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

def _send_heartbeat(id, ts, data):
    heartbeat_ids.add(id)
    if extra_on and id in CANDIDATES:
        return
    return _send_raw(id, ts, data)

c.send_msg = _send_heartbeat

def _extra_loop():
    nxt = {}
    while True:
        now = time.time()
        if extra_on:
            for i, (d, p) in list(CANDIDATES.items()):
                if now >= nxt.get(i, 0):
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

def uds(req, timeout=1.0):
    with rx_lock:
        while c.bus.recv(0):          # drop anything queued
            pass
        _send_raw(REQ, c.start, [len(req)] + list(req) + [0] * (7 - len(req)))
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
                _send_raw(REQ, c.start, [0x30, 0, 0, 0, 0, 0, 0, 0])
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

def clear():
    r = uds([0x14, 0xFF, 0xFF, 0xFF], timeout=2.0)
    print('  clear:', 'ok' if r and r[0] == 0x54 else ('FAILED ' + (r.hex(' ') if r else 'no reply')))

def clear_and_read(label):
    clear()
    time.sleep(SETTLE)
    codes = read_dtcs()
    show(label, codes)
    return codes or {}

def parse_candidates(args):
    # <id>[=<16 hex>][@<ms>] or a ROLLERS name; no payload = zeros, no period = 100 ms
    out = {}
    for a in args:
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
        out[int(i, 16)] = (list(bytes.fromhex(h.ljust(16, '0')))[:8], int(ms or 100) / 1000)
    return out

def open_log(name):
    log_f = open(time.strftime(name + '_%Y%m%d_%H%M%S.txt'), 'w')
    def log(*x):
        line = time.strftime('%H:%M:%S ') + ' '.join(str(v) for v in x)
        print(line, flush=True)
        log_f.write(line + '\n')
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

if __name__ == '__main__':
    dummy = 'dummy' in sys.argv
    sys.argv = [a for a in sys.argv if a != 'dummy']
    mode = sys.argv[1] if len(sys.argv) > 1 else 'read'
    if mode == 'probe' and len(sys.argv) > 2:
        CANDIDATES = parse_candidates(sys.argv[2:])
    if dummy:                                        # same as interactive_brute_force.py --dummydata
        c.SCHEDULE.extend(c.DUMMY_SCHEDULE)
        print('* dummy data: 0x217 0x415 0x85 0x91 0x200 0x82 0x230')
    c.clusterdata = s550_data.s550_ipc('none')        # defaults, no game
    threading.Thread(target=c._scheduler, daemon=True).start()
    threading.Thread(target=_extra_loop, daemon=True).start()
    c.keys()                                         # arrow keys / enter -> menu nav, same as s550_cluster.py
    print('* heartbeat running, waiting 3 s for the cluster')
    time.sleep(3)

    if mode == 'read':
        show('DTCs', read_dtcs())
    elif mode == 'clear':
        show('before clear', read_dtcs())
        clear_and_read('{} s after clear'.format(SETTLE))
    elif mode == 'scan':
        scan(sys.argv[2:])
    elif mode == 'probe':
        base = clear_and_read('CONTROL (heartbeat only)')
        extra_on = True
        print('* adding', ', '.join(hex(i) for i in CANDIDATES))
        time.sleep(2)
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
