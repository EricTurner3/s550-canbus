'''
    CanBus - Interactive Brute Force
    Eric Turner
    6 May 2023

    This script allows you use your arrow keys / enter to interface with the cluster.
    Also allows you to test brute force options

    7 Nov 2026 - rebuilt on top of s550_cluster.py's scheduler. The full set of cluster messages is sent
    so the IPC is awake and running like it is in a car, and the IDs under test are taken over by this script.
    The test frame is sent at the ID's normal rate and the value under test is stepped separately,
    so the cluster never sees the ID drop out while you are watching it.

    Keys
        arrows / enter - menu navigation
        space          - pause / resume the sweep
        + / -          - step the value up / down (works while paused, hold a value and watch the cluster)
        r              - reset the value to the start of the range

    7 Nov 2026 - tests are presets, pick one on the command line
        python interactive_brute_force.py afr
        python interactive_brute_force.py cht
        python interactive_brute_force.py map
        python interactive_brute_force.py boost
        python interactive_brute_force.py iat
        python interactive_brute_force.py coolant
        python interactive_brute_force.py oil
        python interactive_brute_force.py accel
        python interactive_brute_force.py gx
        python interactive_brute_force.py gy
        python interactive_brute_force.py trackapps
        python interactive_brute_force.py trackapps3b2
        python interactive_brute_force.py config04 --vin 1FA6P8...
        python interactive_brute_force.py config10 --vin 1FA6P8...

    --gt also sends every ID from v-ivanyshyn's GT log that s550_cluster.py doesn't, looping through the recorded frames
    so rolling counters / checksums stay valid. Use it to find which ID a gauge needs, then narrow it down with
    --gt-only / --gt-skip. IDs in --gt-only replace s550_cluster.py's version (e.g. 0x416)
        python interactive_brute_force.py cht --gt
        python interactive_brute_force.py cht --gt-only 0x421,0x434,0x435
        python interactive_brute_force.py cht --gt --gt-skip 0x421
        python interactive_brute_force.py cht --gt-only 0x4b0,0x416,0x92,0x7d,0x415,0x216,0x85,0x77
    --gt-all sends every GT log ID live (s550_cluster.py's versions too), s550_cluster.py only fills what the log lacks
        python interactive_brute_force.py cht --gt-all
    --nm sends Ford "module alive" frames (like 0x596: 96 00 FF FF FF FF FF FF) for a range of IDs, to fake modules
    that are missing. New IDs the cluster transmits are printed as they show up
        python interactive_brute_force.py cht --gt-all --nm 0x500-0x5FF
        python interactive_brute_force.py cht --gt-all --nm 0x500-0x57F
    --dummydata adds a small set of chassis messages from database.md with steady values. All speed signals are built
    from the same speed so they agree (mismatched wheel speeds trip Hill Start Assist). A quiet baseline for --nm
        python interactive_brute_force.py cht --dummydata
        python interactive_brute_force.py cht --dummydata --nm 0x500-0x5FF
    --respond answers the cluster's 0x3E0 startup requests (04 01, 04 03 ... 04 11) on 0x3E3 the way v-ivanyshyn's GT log
    does (00 01 04 11 80 ..). Without an answer the cluster waits 5s on each request, in a car each is answered in ~40ms.
    The value is byte 1 of the reply (GT log 0x01)
        python interactive_brute_force.py cht --dummydata --respond
        python interactive_brute_force.py cht --dummydata --respond 0x00
    With 00 01 xx xx 80 00 00 00 the cluster takes every request but 04 07 (and the 07 01 it sends after). It repeats
    an unanswered request every ~1s for 5s, --respond-sweep steps one reply byte on each repeat so a few values get
    tried per power up. A request that ends before the 5s timeout is printed as accepted, with the reply that did it.
    --respond-tail sets bytes 5 - 7 (freeze frame from the car this cluster came out of: 00 01 04 11 80 01 64 00)
        python interactive_brute_force.py cht --dummydata --respond --respond-tail "01 64 00"
        python interactive_brute_force.py cht --dummydata --respond --respond-sweep 5
    Each module answers on its own ID in the 0x3Dx / 0x3Ex range (idle 00 00 00 00 80 ..). The GT350 (start.csv) answers
    04 07 on 0x3E6 7ms after the request, so 04 07 goes out on 0x3E6, everything else on 0x3E3

    --freeze sends the freeze frame from the car this cluster came out of (other_refs/2015GTPremium_FreezeFrame.csv) for
    every ID nothing else sends, one static frame each at the GT log's rate (1 Hz if the GT log doesn't have it).
    With --gt, the GT log's live frames win (rolling counters), the freeze frame fills the rest
        python interactive_brute_force.py cht --dummydata --respond --freeze
        python interactive_brute_force.py cht --gt --respond --freeze

    --config sends 0x40A, the body control module's vehicle config broadcast, in the order a car sends it (one page every
    0.2s). The equipment pages come from this cluster's car's as-built (BCM 726-12 / 726-13). --vin adds the VIN pages
        python interactive_brute_force.py cht --dummydata --respond --config --vin 1FA6P8...
    --config-page replaces one page's 6 data bytes, e.g. v-ivanyshyn's automatic GT (manuals send 40 88 20 24 80 00)
        python interactive_brute_force.py cht --dummydata --respond --config --config-page "10=40 88 20 25 00 00"
'''
import argparse
import csv
import threading
import time
import itertools
from pynput import keyboard
import s550_cluster as cluster
import s550_data
import replay

GT_LOG = 'other_refs/v-ivanyshyn_parse_can_logs/log Mustang S550.txt'
FREEZE_FRAME = 'other_refs/2015GTPremium_FreezeFrame.csv'

def temp(v):
    c = v - 60
    return '{} ({}) -> {}c / {:.0f}f'.format(hex(v), v, c, c * 9 / 5 + 32)

def bit(v):
    return 'byte {} bit {} ({:#04x}) -> {}'.format(v // 8, v % 8, 1 << (v % 8), ' '.join('{:02X}'.format(b) for b in build_frame()))

def boost(v):
    kpa = (v >> 3) * 0.1 - 206.9
    gauge = '{:.1f} inHg'.format(-kpa / 3.386) if kpa < 0 else '{:.1f} psi'.format(kpa / 6.895)
    return '{} ({}) -> {:.1f} kPa / {}'.format(hex(v), v, kpa, gauge)

# VARIABLES
# the CAN adapter / COM port is set in s550_cluster.py
#   can_ids      - tuple of CAN Ids to brute force. They will all be set to the same
#   test_bytes   - bytes under test (0 - 7). Keep the trailing comma for a single byte, (7) is just an int
#   mode         - sequential:  every byte in test_bytes gets the same value
#                  incremental: test_bytes are treated as one big number, first byte is the most significant
#                  bits:        value is a bit number 0 - 63, that one bit of sample_data is flipped (byte value // 8)
#   value_range  - values to sweep, inclusive
#   step_size    - how much each step / keypress changes the value
#   step_period  - seconds between value steps
#   send_period  - how often the test frame is sent, match the ID's real rate
#   sample_data  - frame to start with, the bytes under test are replaced
#   describe     - how the value under test is printed
TESTS = {
    # 0x43E byte 3, raw / 10. 0x6E - 0xC8 is 11.0 - 20.0
    'afr': dict(can_ids=(0x43E,), test_bytes=(3,), mode='sequential', value_range=(0x6E, 0xC8), step_size=2,
                step_period=1.0, send_period=cluster.SPEED_THREE, sample_data=[0x00, 0x93, 0x10, 0x8B, 0x9D, 0x31, 0x30, 0x00],
                describe=lambda v: '{} ({}) -> {:.1f} AFR'.format(hex(v), v, v / 10)),
    # 0x43E byte 4, raw - 60 = Celsius. 0x3C - 0xF0 is 0c - 180c
    'cht': dict(can_ids=(0x43E,), test_bytes=(4,), mode='sequential', value_range=(0x3C, 0xF0), step_size=4,
                step_period=1.0, send_period=cluster.SPEED_THREE, sample_data=[0x00, 0x93, 0x10, 0x8B, 0x9D, 0x31, 0x30, 0x00],
                describe=temp),
    # 0x167 bytes 5 & 6, manifold pressure: 0.2 kPa per bit, atmospheric ~0x1B3A (see database.md)
    # 0x1940 - 0x1BA0 is past full decel vacuum to a little boost. Byte 0 0x72 = engine running, bytes 1 & 2 are torque
    'map': dict(can_ids=(0x167,), test_bytes=(5, 6), mode='incremental', value_range=(0x1940, 0x1BA0), step_size=10,
                step_period=1.0, send_period=cluster.SPEED_ONE, sample_data=[0x72, 0x7F, 0x4B, 0x00, 0x00, 0x1A, 0xED, 0x00],
                describe=lambda v: '{} ({}) -> ~{:.0f} kPa / {:.1f} inHg vacuum'.format(hex(v), v, (0x1B3A - v) / 5, (0x1B3A - v) / 5 * 0.2953)),
    # 0x43E bytes 5 & 6, Boost / Vacuum gauge. 13 bit, (raw >> 3) * 0.1 - 206.9 = gauge kPa
    # 0x20E8 - 0x6BB8 is the full gauge, 30 inHg vacuum to 20 psi boost
    'boost': dict(can_ids=(0x43E,), test_bytes=(5, 6), mode='incremental', value_range=(0x20E8, 0x6BB8), step_size=0x100,
                step_period=1.0, send_period=cluster.SPEED_THREE, sample_data=[0x00, 0x93, 0x10, 0x8B, 0x9D, 0x31, 0x30, 0x00],
                describe=boost),
    # 0x42D bytes 1 & 2, Inlet Air Temp. 10 bit (byte 1 & 0x03), raw * 0.25 - 128 = Celsius, 0x291 shows 97f
    # 0x160 - 0x3D0 is -40c to 116c, the radial gauge is 0f - 240f
    'iat': dict(can_ids=(0x42D,), test_bytes=(1, 2), mode='incremental', value_range=(0x160, 0x3D0), step_size=8,
                step_period=1.0, send_period=0.5, sample_data=[0x00, 0x02, 0x91, 0x00, 0x00, 0x00, 0xF0, 0x00],
                describe=lambda v: '{} ({}) -> {:.2f}c / {:.0f}f'.format(hex(v), v, (v & 0x3FF) * 0.25 - 128, ((v & 0x3FF) * 0.25 - 128) * 9 / 5 + 32)),
    # 0x421, sending it changes Oil Pressure from Low (and a warning) to Normal. The GT has a switch, no radial gauge
    # Sweeping bytes 2 and 6 did not change it, so flip one bit at a time across the whole frame and watch for Low
    # Track Apps. Another project (2016 Mustang) shows it with 0x3B2 byte 4 bit 0x10. 0x3B2 has 0x3B3's layout
    # (40 activate, byte 3 backlight, byte 4 0x08 / byte 6 0x40 turn lamps, byte 7 02). Flips one bit of a running car's
    # 0x3B3 at a time, slow enough to check the menu. Byte 0 bits can turn the cluster off, pause (space) to look
    'trackapps': dict(can_ids=(0x3B3,), test_bytes=tuple(range(8)), mode='bits', value_range=(0, 63), step_size=1,
                step_period=4.0, send_period=cluster.SPEED_FOUR, sample_data=[0x40, 0x48, 0x06, 0x12, 0x10, 0x05, 0x00, 0x02],
                describe=bit),
    # 0x3B2 itself, with the Track Apps frame from the other project, one bit flipped at a time
    'trackapps3b2': dict(can_ids=(0x3B2,), test_bytes=tuple(range(8)), mode='bits', value_range=(0, 63), step_size=1,
                step_period=4.0, send_period=cluster.SPEED_FOUR, sample_data=[0x40, 0x00, 0x00, 0x12, 0x10, 0x00, 0x00, 0x02],
                describe=bit),
    # 0x40A vehicle config pages C1 04 / C1 10 (BCM as-built 726-12 / 726-13), one bit of bytes 2 - 7 flipped at a time.
    # Turns on --config, the page under test takes its turn in the page rotation
    'config04': dict(can_ids=(0x40A,), test_bytes=tuple(range(2, 8)), mode='bits', value_range=(16, 63), step_size=1,
                step_period=4.0, send_period=0.2, sample_data=[0xC1, 0x04, 0x01, 0x63, 0x08, 0x27, 0x55, 0xC1],
                describe=bit),
    'config10': dict(can_ids=(0x40A,), test_bytes=tuple(range(2, 8)), mode='bits', value_range=(16, 63), step_size=1,
                step_period=4.0, send_period=0.2, sample_data=[0xC1, 0x10, 0x40, 0x88, 0x20, 0x24, 0x80, 0x00],
                describe=bit),
    'oil': dict(can_ids=(0x421,), test_bytes=tuple(range(8)), mode='bits', value_range=(0, 63), step_size=1,
                step_period=2.0, send_period=0.2, sample_data=[0x00, 0x00, 0x50, 0x00, 0x00, 0x00, 0x4D, 0x00],
                describe=bit),
    # Track Apps g meter on 0x76 (another project's firmware, mustang.c). Byte 0 & 1 steering angle center 0x3E80
    # byte 2 = 16 + x * 8 (x in g, +-1.5 -> 4 - 28), one step every second
    'gx': dict(can_ids=(0x76,), test_bytes=(2,), mode='sequential', value_range=(4, 28), step_size=1,
                step_period=1.0, send_period=cluster.SPEED_TWO, sample_data=[0x3E, 0x80, 0x10, 0x04, 0x00, 0x00, 0x00, 0x00],
                describe=lambda v: '{} -> x {:+.2f}g'.format(hex(v), (v - 16) / 8)),
    # bytes 3 & 4 = 1024 + y * 512 (y in g, +-1.5 -> 0x0100 - 0x0700)
    'gy': dict(can_ids=(0x76,), test_bytes=(3, 4), mode='incremental', value_range=(0x0100, 0x0700), step_size=0x40,
                step_period=1.0, send_period=cluster.SPEED_TWO, sample_data=[0x3E, 0x80, 0x10, 0x04, 0x00, 0x00, 0x00, 0x00],
                describe=lambda v: '{} -> y {:+.2f}g'.format(hex(v), (v - 1024) / 512)),
    # 0x92 bytes 0 & 1, lateral acceleration (Track Apps accelerometer?). 13 bit, value / 100 - 40 = m/s^2
    # bytes 2 & 3 longitudinal, 4 & 5 vertical (9.8 at rest). Top 3 bits of each pair are 0x6_ in the logs
    # 0x6FA0 - 0x7770 sweeps 0 to +2g
    'accel': dict(can_ids=(0x92,), test_bytes=(0, 1), mode='incremental', value_range=(0x6FA0, 0x7770), step_size=0x31,
                step_period=1.0, send_period=cluster.SPEED_THREE, sample_data=[0x6F, 0xA0, 0x6F, 0xD8, 0x73, 0x5C, 0x00, 0x00],
                describe=lambda v: '{} -> {:.2f} m/s^2 / {:.2f}g'.format(hex(v), (v & 0x1FFF) / 100 - 40, ((v & 0x1FFF) / 100 - 40) / 9.81)),
    # 0x156 byte 0, coolant temp gauge, raw - 60 = Celsius. Needle holds center from ~0xA6 - 0xC0
    # 0x3C - 0xF0 is 0c - 180c. Byte 1 is oil temp. s550_cluster.py's send_engine_temp is replaced while this runs
    'coolant': dict(can_ids=(0x156,), test_bytes=(0,), mode='sequential', value_range=(0x3C, 0xF0), step_size=2,
                step_period=1.0, send_period=cluster.SPEED_THREE, sample_data=[0x9E, 0x99, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00],
                describe=temp),
}
parser = argparse.ArgumentParser(description='Sweep a CAN signal on the cluster')
parser.add_argument('test', nargs='?', default='afr', choices=TESTS)
parser.add_argument('--gt', action='store_true', help="also send the GT log IDs s550_cluster.py doesn't")
parser.add_argument('--gt-only', type=replay.parse_ids, default=set(), help='comma separated GT log IDs to send (implies --gt)')
parser.add_argument('--gt-skip', type=replay.parse_ids, default=set(), help='comma separated GT log IDs to leave out')
parser.add_argument('--gt-all', action='store_true', help="send every GT log ID, replacing s550_cluster.py's versions too. "
                    "s550_cluster.py only fills the IDs the log doesn't have")
parser.add_argument('--dummydata', action='store_true',
                    help='add steady chassis messages (wheel speeds, yaw, accelerometer, steering ...) with matching speeds')
parser.add_argument('--nm', type=replay.parse_ids, default=set(), metavar='IDS',
                    help='send "module alive" frames (ID low byte, 00, FF x6 at 1 Hz) for these IDs, e.g. 0x500-0x5FF. '
                         "IDs the cluster sends itself are skipped")
parser.add_argument('--respond', type=lambda v: int(v, 0), nargs='?', const=0x01, default=None, metavar='VALUE',
                    help='answer the 0x3E0 requests on 0x3E3, VALUE is byte 1 of the reply (default 0x01, as in the GT log)')
parser.add_argument('--respond-tail', type=lambda v: bytes.fromhex(v)[:3].ljust(3, bytes(1)), default=bytes(3), metavar='"B5 B6 B7"',
                    help='bytes 5 - 7 of the 0x3E3 reply, e.g. "01 64 00" (default 00 00 00)')
parser.add_argument('--respond-sweep', type=int, choices=range(8), default=None, metavar='BYTE',
                    help='add 1 to this reply byte each time the cluster repeats a request')
parser.add_argument('--freeze', action='store_true',
                    help="send the freeze frame from this cluster's car for every ID nothing else sends")
parser.add_argument('--config', action='store_true', help="send 0x40A vehicle config pages from this cluster's car")
parser.add_argument('--vin', default=None, help='17 character VIN for the --config VIN pages, left out without it')
parser.add_argument('--config-page', action='append', default=[], metavar='PAGE=BYTES',
                    help='replace a 0x40A page, e.g. "10=40 88 20 25 00 00" (page is byte 1, hex). Repeatable')
args = parser.parse_args()
test = args.test
cfg = TESTS[test]
can_ids = cfg['can_ids']
test_bytes = cfg['test_bytes']
mode = cfg['mode']
value_range = cfg['value_range']
step_size = cfg['step_size']
step_period = cfg['step_period']
send_period = cfg['send_period']
sample_data = cfg['sample_data']
describe = cfg['describe']

cluster_speed = 40 # mph shown on the cluster

# SAMPLE DATA - 2015 Ford Mustang GT - Manual - MyColor
# 200 => [0x00, 0x00, 0x7F, 0xF0, 0x81, 0x57, 0x00, 0x00]
# 204 => [0xC0, 0x00, 0x7D, 0x00, 0x00, 0x00, 0x00, 0x00]
# 3B3 => [0x40, 0x8B, 0x0a, 0x12, 0x18, 0x05, 0xC0, 0xE2]

value = value_range[0]
paused = False

def build_frame():
    data = list(sample_data)
    if mode == 'incremental':
        new_bytes = value.to_bytes(len(test_bytes), 'big')
        for i, b in zip(test_bytes, new_bytes):
            data[i] = b
    elif mode == 'bits':
        data[value // 8] ^= 1 << (value % 8)
    else:
        for i in test_bytes:
            data[i] = value
    return data

def set_value(v):
    global value
    # wrap around the range so a sweep repeats
    lo, hi = value_range
    value = lo if v > hi else hi if v < lo else v
    print(' - {} bytes {} = {}'.format([hex(i) for i in can_ids], test_bytes, describe(value)))

# the regular cluster functions still run, drop anything they send on an ID this script owns
_send_msg = cluster.send_msg
gt_ids = set() # GT log IDs taken over with --gt-only, s550_cluster.py's versions are dropped
def _filtered_send_msg(id, ts, data):
    if id in can_ids or id in gt_ids:
        return
    return _send_msg(id, ts, data)
cluster.send_msg = _filtered_send_msg

def send_test(clusterdata):
    data = build_frame()
    for id in can_ids:
        if id == 0x92: # accelerometer counter (+5) and checksum (all bytes add up to 0x16), like send_accelerometer
            data[7] = (cluster.accelerometer_counter + 5) & 0xFF
            cluster.accelerometer_counter = data[7]
            data[6] = (0x16 - sum(data[:6]) - data[7]) & 0xFF
        if id != 0x40A: # multiplexed, config_sender sends the page under test in its turn
            _send_msg(id, cluster.start, data)

_cluster_ids = None
def cluster_ids():
    '''
        IDs s550_cluster.py sends, found by running its schedule once without sending anything.
        Kept from the first call, later the schedule has this script's senders (step, test, GT log ...) that send for real
    '''
    global _cluster_ids
    if _cluster_ids is not None:
        return set(_cluster_ids)
    seen = set()
    real = cluster.send_msg
    cluster.send_msg = lambda id, ts, data: seen.add(id)
    try:
        for period, funcs in cluster.SCHEDULE:
            for m in funcs:
                m(cluster.clusterdata)
    finally:
        cluster.send_msg = real
    _cluster_ids = seen
    return set(seen)

def gt_log_frames(only, skip, replace_all=False):
    '''
        [(period, id, [frames])] from the GT log at the log's rate.
        Without --gt-only, only the IDs s550_cluster.py doesn't send. IDs listed in --gt-only replace s550_cluster.py's
    '''
    frames = list(replay.read_txt(GT_LOG))
    duration = frames[-1][0] - frames[0][0]
    by_id = {}
    for t, id, data in frames:
        by_id.setdefault(id, []).append(list(data))
    # 0x40A is the GT's VIN, keep another car's VIN off the cluster unless asked for with --gt-only
    keep_cluster = set() if replace_all else cluster_ids() - only
    keep_cluster |= replay.CLUSTER_TX_IDS # the GT log has the GT's cluster frames, never send over ours
    exclude = keep_cluster | set(can_ids) | skip | ({0x40A} - only)
    out = []
    for id, recorded in sorted(by_id.items()):
        if id in exclude or (only and id not in only):
            continue
        out.append((max(cluster.SPEED_ONE, duration / len(recorded)), id, recorded))
    return out

def freeze_frames(skip):
    '''
        [(period, id, [frame])] from the freeze frame, for the IDs s550_cluster.py and the cluster don't send.
        One sample per ID, so the rate comes from the GT log
    '''
    log = list(replay.read_txt(GT_LOG))
    duration = log[-1][0] - log[0][0]
    counts = {}
    for t, id, data in log:
        counts[id] = counts.get(id, 0) + 1
    exclude = cluster_ids() | replay.CLUSTER_TX_IDS | set(can_ids) | skip
    out = []
    with open(FREEZE_FRAME, newline='') as f:
        for row in csv.DictReader(f):
            id = int(row['ID (HEX)'], 16)
            if id in exclude:
                continue
            period = max(cluster.SPEED_ONE, duration / counts[id]) if id in counts else cluster.SPEED_FIVE
            out.append((period, id, [list(bytes.fromhex(row['Sample Data']))]))
    return sorted(out, key=lambda f: f[1])

# 0x40A pages, byte 0 & 1 select the page. From this cluster's car (freeze frame + as-built)
CONFIG_PAGES = [
    [0xC1, 0x04, 0x01, 0x63, 0x08, 0x27, 0x55, 0xC1], # BCM as-built 726-12 (01 63 08 27 55 | C1)
    [0xC1, 0x10, 0x40, 0x88, 0x20, 0x24, 0x80, 0x00], # BCM as-built 726-13 (40 88 20 24 80 | 00), same in the freeze frame
]
config_time = 0x83680000 # page C0 00, 10 counts a second

def config_pages(vin):
    '''
        Car order: C1 02, C1 04, C1 10, C0 00, C1 00, C1 01. VIN in ASCII, 6 + 6 + 5 characters (C1 02 ends in FF)
    '''
    pages = []
    if vin:
        vin = vin.encode('ascii')
        pages.append([0xC1, 0x02] + list(vin[12:17]) + [0xFF])
    pages += [list(p) for p in CONFIG_PAGES]
    for item in args.config_page:
        page, data = item.split('=')
        data = list(bytes.fromhex(data))
        if len(data) != 6:
            raise SystemExit('--config-page needs 6 bytes: {}'.format(item))
        matches = [p for p in pages if p[1] == int(page, 16)]
        if matches:
            matches[0][2:] = data
        else:
            pages.append([0xC1, int(page, 16)] + data)
    pages.append(None) # C0 00, built when sent
    if vin:
        pages += [[0xC1, 0x00] + list(vin[0:6]), [0xC1, 0x01] + list(vin[6:12])]
    return pages

def config_sender(vin):
    pages = itertools.cycle(config_pages(vin))
    def send_config(clusterdata):
        data = next(pages)
        if data is not None and 0x40A in can_ids and data[1] == sample_data[1]:
            data = build_frame() # config04 / config10, the page under test
        if data is None:
            t = (config_time + int((time.time() - cluster.start) * 10)) & 0xFFFFFFFF
            data = [0xC0, 0x00, 0x00] + list(t.to_bytes(4, 'big')) + [0x00]
        _send_msg(0x40A, cluster.start, data)
    return send_config

def gt_frame_sender(id, recorded):
    '''
        Loops through the frames recorded for this ID in order. Many safety system messages (0x4B0, 0x416, 0x92 ...)
        have a rolling counter / checksum, a frozen copy looks stale to the cluster
    '''
    frames = itertools.cycle(recorded)
    def send(clusterdata):
        _send_msg(id, cluster.start, next(frames))
    send.__name__ = 'send_gt_{}'.format(hex(id))
    return send

def step(clusterdata):
    if not paused:
        set_value(value + step_size)

def on_press(key):
    global paused
    cluster.on_press(key) # arrows / enter
    try:
        k = key.char  # single-char keys
    except:
        k = key.name  # other keys
    if k in ('up', 'down', 'left', 'right', 'enter'):
        # in cluster_tx_changes.csv too, so menu changes on the cluster can be lined up with its frames
        cluster_tx_changes.append((time.time() - cluster.start, 'key', k))
    if k == 'space':
        paused = not paused
        print(' - {}'.format('PAUSED' if paused else 'RESUMED'))
    elif k in ('+', '='):
        set_value(value + step_size)
    elif k == '-':
        set_value(value - step_size)
    elif k == 'r':
        set_value(value_range[0])

cluster_tx = {} # IDs the cluster itself transmits, filled in by _listen
CLUSTER_TX_LOG = 'cluster_tx.csv'
cluster_tx_log = {} # id -> {data: count}, every distinct frame the cluster has sent this run
CLUSTER_TX_CHANGES = 'cluster_tx_changes.csv'
cluster_tx_changes = [] # (seconds, id, data) each time a cluster ID changes value, plus key presses
rx_count = 0 # frames received since the last status line
rx_errors = 0

def _listen():
    '''
        Print each new ID the cluster sends (the adapter doesn't echo our own frames back)
    '''
    global rx_count, rx_errors
    while True:
        msg = cluster.bus.recv(1.0)
        if msg is None:
            continue
        if msg.is_error_frame:
            rx_errors += 1
            continue
        rx_count += 1
        if msg.arbitration_id not in cluster_tx:
            print('* cluster sends {:#05x}: {}'.format(msg.arbitration_id, msg.data.hex(' ')))
        if cluster_tx.get(msg.arbitration_id) != bytes(msg.data):
            cluster_tx_changes.append((time.time() - cluster.start, '{:#05x}'.format(msg.arbitration_id), msg.data.hex(' ')))
        cluster_tx[msg.arbitration_id] = bytes(msg.data)
        if args.respond is not None and msg.arbitration_id == 0x3E0:
            if msg.data[0] and msg.data[4] & 0x04:
                respond(msg.data)
            else:
                request_done()
        counts = cluster_tx_log.setdefault(msg.arbitration_id, {})
        counts[bytes(msg.data)] = counts.get(bytes(msg.data), 0) + 1

REPLY_IDS = {bytes([0x04, 0x07]): 0x3E6} # request -> the ID its module answers on, 0x3E3 for the rest
reply_tries = {} # request bytes 0 & 1 -> replies sent
last_reply = None # (time of the first reply, request, last reply) waiting to see if the cluster moves on

def respond(request):
    '''
        0x3E0 request 04 11 00 00 84 -> 0x3E3 reply 00 01 04 11 80 (v-ivanyshyn's GT log, HS3 only)
        Bytes 2 & 3 echo the request, byte 1 is args.respond, bytes 5 - 7 args.respond_tail. Sent on every request
        frame, the cluster repeats a request until it's answered. --respond-sweep adds the try count to one byte
    '''
    global last_reply
    key = bytes(request[:2])
    tries = reply_tries.get(key, 0)
    reply_tries[key] = tries + 1
    data = [0x00, args.respond, request[0], request[1], 0x80] + list(args.respond_tail)
    if args.respond_sweep is not None:
        data[args.respond_sweep] = (data[args.respond_sweep] + tries) & 0xFF
    _send_msg(REPLY_IDS.get(key, 0x3E3), cluster.start, data)
    last_reply = (last_reply[0] if last_reply and last_reply[1] == key else time.time(), key, bytes(data))
    cluster_tx_changes.append((time.time() - cluster.start, 'reply', bytes(data).hex(' ')))
    print(' - 0x3e0 request {} -> {:#05x} reply {} (try {})'.format(key.hex(' '), REPLY_IDS.get(key, 0x3E3), bytes(data).hex(' '), tries + 1))

def request_done():
    '''
        0x3E0 went back to idle. A taken reply ends the request in ~50ms, an untaken one is repeated ~1/s until the
        cluster gives up 5s after the request started. Time from the first reply, the last one always looks recent
    '''
    global last_reply
    if last_reply is None:
        return
    sent, key, data = last_reply
    last_reply = None
    result = 'accepted' if time.time() - sent < 4.0 else 'timed out'
    cluster_tx_changes.append((time.time() - cluster.start, result, data.hex(' ')))
    print(' - 0x3e0 request {} {}, last reply {}'.format(key.hex(' '), result.upper(), data.hex(' ')))

def send_wheel_speeds(clusterdata):
    '''
        0x217, four 13 bit wheel speeds (FL, FR, RL, RR), raw ~= MPH * 144, low 2 bits always 0
    '''
    raw = cluster.clamp(clusterdata.value_speed * 144, 0, 0x1FFF) & ~0x3
    cluster.send_msg(0x217, cluster.start, [raw >> 8, raw & 0xFF] * 4)

def send_vehicle_speed_77(clusterdata):
    '''
        0x77, bytes 0 & 1 speed (14 bit, MPH * 175), bytes 2 & 3 lateral centered at 0x0800
        byte 6 0xE6 keeps Hill Start Assist Not Available off
    '''
    raw = cluster.clamp(clusterdata.value_speed * 175, 0, 0x3FFF)
    cluster.send_msg(0x77, cluster.start, [raw >> 8, raw & 0xFF, 0x08, 0x00, 0x7F, 0xF7, 0xE6, 0x02])

def send_vehicle_speed_415(clusterdata):
    '''
        0x415, bytes 0 & 1 speed (14 bit, MPH * 175), bytes 4 - 7 yaw / lateral centered (GT log at rest 07 FD 07 FD)
    '''
    raw = cluster.clamp(clusterdata.value_speed * 175, 0, 0x3FFF)
    cluster.send_msg(0x415, cluster.start, [raw >> 8, raw & 0xFF, 0xD0, 0xFA, 0x07, 0xFD, 0x07, 0xFD])

# --dummydata. Speed signals follow clusterdata.value_speed, the rest are s550_cluster.py's unscheduled senders
DUMMY_SCHEDULE = [
    (cluster.SPEED_ONE, [send_wheel_speeds, cluster.send_misc_4, cluster.send_misc_5]), # 0x217, 0x85 steering angle, 0x91 yaw
    (cluster.SPEED_TWO, [send_vehicle_speed_77, send_vehicle_speed_415, cluster.send_misc_7, cluster.send_misc_12,
                         cluster.send_misc_13]), # 0x200 torque, 0x82 steering mode, 0x230 gear
]

def nm_sender(id):
    '''
        Ford "module alive" frame like the 0x5xx series in the logs: byte 0 is the low byte of the ID, then 00 FF FF ...
    '''
    def send(clusterdata):
        if id not in cluster_tx: # never talk over the cluster's own ID
            _send_msg(id, cluster.start, [id & 0xFF, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    send.__name__ = 'send_nm_{}'.format(hex(id))
    return send

def _status():
    global rx_count, rx_errors
    while True:
        time.sleep(1)
        sent = sum(cluster.sent_count.values())
        failed = sum(cluster.fail_count.values())
        cluster.sent_count.clear()
        cluster.fail_count.clear()
        print('* {} frames/s, {} failed, cluster sent {} frames/s ({} IDs, {} errors), testing {}'.format(
            sent, failed, rx_count, len(cluster_tx), rx_errors, describe(value)))
        rx_count = 0
        rx_errors = 0
        _save_cluster_tx()


def _save_cluster_tx():
    '''
        Rewrites cluster_tx.csv with every distinct frame the cluster sent this run, so it can be checked after
    '''
    try:
        with open(CLUSTER_TX_LOG, 'w') as f:
            f.write('id,count,data\n')
            for id in sorted(cluster_tx_log):
                for data, count in sorted(cluster_tx_log[id].items()):
                    f.write('{:#05x},{},{}\n'.format(id, count, data.hex(' ')))
        with open(CLUSTER_TX_CHANGES, 'w') as f:
            f.write('seconds,id,data\n')
            for t, id, data in list(cluster_tx_changes):
                f.write('{:.3f},{},{}\n'.format(t, id, data))
    except OSError as e:
        print('* could not write {}: {}'.format(CLUSTER_TX_LOG, e))


if __name__ == "__main__":
    if isinstance(test_bytes, int):
        test_bytes = (test_bytes,)
    if isinstance(can_ids, int):
        can_ids = (can_ids,)
    max_value = {'sequential': 0xFF, 'bits': 63}.get(mode, 256 ** len(test_bytes) - 1)
    if any(i < 0 or i > 7 for i in test_bytes) or value_range[0] < 0 or value_range[1] > max_value:
        raise SystemExit('test_bytes must be 0 - 7 and value_range must fit in {}'.format(hex(max_value)))

    # default cluster data, no game. Engine on and moving so the cluster acts like it is driving
    cluster.clusterdata = s550_data.s550_ipc('none')
    cluster.clusterdata.value_speed = cluster_speed
    # the cluster saves distance from the 0x179 counter, don't add test miles to the odometer while sitting at 40 mph
    cluster.ODOMETER_COUNTS_PER_MILE = 0
    # warm idle values (v-ivanyshyn's GT log) so the gauges not under test read normal
    cluster.clusterdata.engine_temp = 90
    cluster.clusterdata.oil_temp = 95
    cluster.clusterdata.cylinder_head_temp = 97
    cluster.clusterdata.intake_temp = 36
    cluster.clusterdata.value_afr = 13.9
    cluster.clusterdata.value_boost = -7.2 # 14.6 inHg vacuum

    cluster_ids() # before this script adds to the schedule
    log_frames = []
    if args.gt or args.gt_only or args.gt_all:
        # before the test is scheduled, it runs the schedule once
        # --respond owns 0x3E3, the log's copy is a frozen reply
        log_frames = gt_log_frames(args.gt_only - ({0x40A} if args.config else set()),
                                   args.gt_skip | ({0x3E3} if args.respond is not None else set()) | ({0x40A} if args.config else set()),
                                   args.gt_all)
        print('* GT log IDs: {}'.format(' '.join(hex(id) for _, id, _ in log_frames)))
    if args.freeze:
        # --respond owns the reply IDs, the freeze frame holds old replies
        replies = {0x3E3} | set(REPLY_IDS.values()) if args.respond is not None else set()
        frozen = freeze_frames(set(id for _, id, _ in log_frames) | replies | ({0x40A} if args.config else set()))
        print('* Freeze frame IDs: {}'.format(' '.join(hex(id) for _, id, _ in frozen)))
        log_frames += frozen
    if 0x40A in can_ids:
        args.config = True
    if args.config:
        if args.vin and len(args.vin) != 17:
            raise SystemExit('--vin needs all 17 characters')
        cluster.SCHEDULE.append((0.2, [config_sender(args.vin)]))
        gt_ids.add(0x40A)
        print('* Config 0x40A: {} pages{}'.format(len(config_pages(args.vin)), '' if args.vin else ', no VIN (add --vin)'))
    cluster.SCHEDULE.append((send_period, [send_test]))
    cluster.SCHEDULE.append((step_period, [step]))
    gt_ids.update(id for _, id, _ in log_frames)
    for period, id, recorded in log_frames:
        cluster.SCHEDULE.append((period, [gt_frame_sender(id, recorded)]))
    if args.dummydata:
        cluster.SCHEDULE.extend(DUMMY_SCHEDULE)
        print('* Dummy data: 0x217 0x77 0x415 (speeds follow {} mph), 0x85 0x91 0x200 0x82 0x230'.format(cluster_speed))
    if args.respond is not None:
        print('* Answering 0x3E0 requests on 0x3E3 (04 07 on 0x3E6): 00 {:02x} xx xx 80 {}{}'.format(args.respond, args.respond_tail.hex(' '),
              '' if args.respond_sweep is None else ', byte {} +1 per repeat'.format(args.respond_sweep)))
    nm_ids = sorted(args.nm - cluster_ids() - gt_ids - set(can_ids) - replay.CLUSTER_TX_IDS)
    if nm_ids:
        print('* Module alive frames: {} IDs, {:#05x} - {:#05x}'.format(len(nm_ids), nm_ids[0], nm_ids[-1]))
        # one group, so the scheduler spreads them across the second instead of sending a burst
        cluster.SCHEDULE.append((cluster.SPEED_FIVE, [nm_sender(id) for id in nm_ids]))

    print('* Test {}: {} bytes {} ({}), sweeping {} - {} every {}s'.format(
        test, [hex(i) for i in can_ids], test_bytes, mode, hex(value_range[0]), hex(value_range[1]), step_period))
    print('* Keys: arrows / enter navigate, space pause, + / - step, r reset')
    keyboard.Listener(on_press=on_press).start()
    threading.Thread(target=_status, daemon=True).start()
    threading.Thread(target=_listen, daemon=True).start()
    set_value(value)
    cluster._scheduler()
