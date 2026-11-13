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
        python interactive_brute_force.py keymsg
        python interactive_brute_force.py occupant
        python interactive_brute_force.py occupantbits
        python interactive_brute_force.py tpmssys / tpmslamp / tpmslf / tpmsrf / tpmsrr / tpmslr
        python interactive_brute_force.py trans / transwarm
        python interactive_brute_force.py oil
        python interactive_brute_force.py epasfail / epasbyte1 / epasstat
        python interactive_brute_force.py idle --dummydata --respond --config --vin 1FA6P8... --speed 0
    idle sends the background frames with nothing under test. fake_forscan.py runs it with a fake PCM / BCM for Forscan
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
    --mute stops s550_cluster.py (and --dummydata) sending the listed IDs, to find which frame raises a warning
        python interactive_brute_force.py afr --dummydata --mute 0x82,0x85
    --gt-all sends every GT log ID live (s550_cluster.py's versions too), s550_cluster.py only fills what the log lacks
        python interactive_brute_force.py cht --gt-all
    --pscm sends the power steering frames that go with 0x82: 0x85 and 0x7E with a rolling counter and checksum, and
    0x3A8 (s550_cluster.PSCM_SCHEDULE). Turned on by itself for the 0x82 tests, --mute 0x7E etc. drops one
        python interactive_brute_force.py epasbyte1 --dummydata
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
    07 01 is answered on 0x3E1 with the freeze frame's 80 00 00 07 01 80 00 00, --respond-0701 sends another frame
        python interactive_brute_force.py cht --dummydata --respond --respond-0701 "00 00 07 01 80 00 00 00"
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

# Ford power mode, the apimpower guess for 0x048 byte 4
POWER_MODES = {0: 'key out', 1: 'key recently out', 2: 'key approved', 3: 'post accessory', 4: 'accessory',
               5: 'post ignition', 6: 'ignition on', 7: 'running', 9: 'crank'}

def bit(v):
    return 'byte {} bit {} ({:#04x}) -> {}'.format(v // 8, v % 8, 1 << (v % 8), ' '.join('{:02X}'.format(b) for b in build_frame()))

def boost(v):
    kpa = (v >> 3) * 0.1 - 206.9
    gauge = '{:.1f} inHg'.format(-kpa / 3.386) if kpa < 0 else '{:.1f} psi'.format(kpa / 6.895)
    return '{} ({}) -> {:.1f} kPa / {}'.format(hex(v), v, kpa, gauge)

# 0x3B4 Tire_Pressure_Status (Ford DBC, CGEA 1.2 2011). Base is the freeze frame (system 4, lamp off, every tire 1).
# Byte 0: system status bits 7 - 4, lamp bits 3 - 2. Bytes 1 - 3: one status nibble per tire,
# LF b1 high, RF b1 low, RR b2 high, LR b2 low, inner rears (duallys) b3. Pressures stay on 0x3B5
# Tire statuses showed nothing with system 4, so the tire presets start from system 3 (Tire Pressure Low window)
# with the lamp solid, 34 like v-ivanyshyn's GT log
def tpms_test(byte, lo, hi, step, what, b0=0x40):
    return dict(can_ids=(0x3B4,), test_bytes=(byte,), mode='sequential', value_range=(lo, hi), step_size=step,
                step_period=4.0, send_period=0.5, sample_data=[b0, 0x11, 0x11, 0xFF, 0x20, 0x20, 0x00, 0x00],
                describe=lambda v: '{} -> {}'.format(hex(v), what(v)))

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
    # 0x38D byte 4 high nibble, immoMsgTxt_D_Rq (Ford DBC Body_Info_6_FD1), key / immobilizer messages:
    # 4 = No Key Detected, 6 = Run Power Active. Byte 0 0x20 = 2 admin keys (freeze frame / v-ivanyshyn's GT log)
    # Sending 0x38D at all also shows Track Apps in the menu
    'keymsg': dict(can_ids=(0x38D,), test_bytes=(4,), mode='sequential', value_range=(0x00, 0xF0), step_size=0x10,
                step_period=4.0, send_period=0.5, sample_data=[0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                describe=lambda v: '{} -> message {}'.format(hex(v), v >> 4)),
    # 0x42C byte 0. The GT350 always sends 8C 00 00 00 9C 60 00 00 (84 briefly in start.csv), which shows Occupant
    # Sensor Blocked on this cluster. 2018 GWM bench: bits 7 - 5 are cruise status, so the occupant bits should be the
    # low nibble. Sending 0x42C at all also stops U0100 (lost comm with the PCM). 51 ms in the GT350 logs
    'occupant': dict(can_ids=(0x42C,), test_bytes=(0,), mode='sequential', value_range=(0x80, 0x8F), step_size=1,
                step_period=4.0, send_period=0.05, sample_data=[0x80, 0x00, 0x00, 0x00, 0x9C, 0x60, 0x00, 0x00],
                describe=lambda v: '{} -> low nibble {:04b}'.format(hex(v), v & 0x0F)),
    # same frame, low nibble of byte 0 cleared, one bit of bytes 0 - 5 flipped at a time (bytes 1, 4, 5 carry data
    # in the GT350 / v-ivanyshyn logs: 9C 60 here, 60 .. B2 20 in v-ivanyshyn's)
    'occupantbits': dict(can_ids=(0x42C,), test_bytes=tuple(range(6)), mode='bits', value_range=(0, 47), step_size=1,
                step_period=4.0, send_period=0.05, sample_data=[0x80, 0x00, 0x00, 0x00, 0x9C, 0x60, 0x00, 0x00],
                describe=bit),
    # 0x82 EPAS_INFO from the power steering module (Ford DBC), GT350 driving frame 83 00 14 34 AF 00 44 FF.
    # Byte 1 bits 1 - 0 EPAS_Failure (0 in every log). Byte 6 bits 7 - 5 module state: 0 key on engine off,
    # 4 cranking, 1 ramping, 2 assisting (start.csv); bits 3 - 2 steering mode (0x44 sport). 20 ms in the logs
    'epasfail': dict(can_ids=(0x82,), test_bytes=(1,), mode='sequential', value_range=(0x00, 0x03), step_size=1,
                step_period=6.0, send_period=0.02, sample_data=[0x83, 0x00, 0x14, 0x34, 0xAF, 0x00, 0x44, 0xFF],
                describe=lambda v: 'EPAS_Failure {}'.format(v)),
    # nothing under test, only the background frames (e.g. a steady car for Forscan: idle --config --vin ... --speed 0)
    'idle': dict(can_ids=(), test_bytes=(), mode='sequential', value_range=(0, 0), step_size=0,
                step_period=3600.0, send_period=1.0, sample_data=[0] * 8, describe=lambda v: 'nothing under test'),
    # every value of byte 1: EPAS_Failure (bits 1 - 0), driver steer active (bit 2), park assist status (bits 7 - 3)
    'epasbyte1': dict(can_ids=(0x82,), test_bytes=(1,), mode='sequential', value_range=(0x00, 0xFF), step_size=1,
                step_period=3.0, send_period=0.02, sample_data=[0x83, 0x00, 0x14, 0x34, 0xAF, 0x00, 0x44, 0xFF],
                describe=lambda v: '{} -> EPAS_Failure {}, steer active {}, SAPP {:05b}'.format(hex(v), v & 3, (v >> 2) & 1, v >> 3)),
    'epasstat': dict(can_ids=(0x82,), test_bytes=(6,), mode='sequential', value_range=(0x04, 0xE4), step_size=0x20,
                step_period=6.0, send_period=0.02, sample_data=[0x83, 0x00, 0x14, 0x34, 0xAF, 0x00, 0x44, 0xFF],
                describe=lambda v: 'module state {}'.format(v >> 5)),
    # 0x3B4 TPMS, see tpms_test. v-ivanyshyn's GT log has 34 11 21 (system 3 low, lamp solid, RR 2)
    'tpmssys': tpms_test(0, 0x00, 0xF0, 0x10, lambda v: 'system status {}'.format(v >> 4)),
    'tpmslamp': tpms_test(0, 0x40, 0x4C, 0x04, lambda v: 'lamp {}'.format((v >> 2) & 3)),
    'tpmslf': tpms_test(1, 0x01, 0xF1, 0x10, lambda v: 'LF status {}'.format(v >> 4), b0=0x34),
    'tpmsrf': tpms_test(1, 0x10, 0x1F, 0x01, lambda v: 'RF status {}'.format(v & 0x0F), b0=0x34),
    'tpmsrr': tpms_test(2, 0x01, 0xF1, 0x10, lambda v: 'RR status {}'.format(v >> 4), b0=0x34),
    'tpmslr': tpms_test(2, 0x10, 0x1F, 0x01, lambda v: 'LR status {}'.format(v & 0x0F), b0=0x34),
    # 0x431 transmission messages, not in any DBC. ~1 Hz in the GT350 logs. Warm (longerdrive.csv) 05 1B 40 04 0F 83 42 00,
    # idle 05 1D 42 03 97 83 42 00, freeze frame 05 1D 40 EB B7 83 46 00 shows Transmission Warming Up.
    # byte 3 or byte 6 = FF shows Transmission Limited Function (2018 bench). One bit flipped at a time:
    #   trans     - from the warm frame, look for bits that raise a message
    #   transwarm - from the freeze frame, look for the bit that clears Warming Up
    'trans': dict(can_ids=(0x431,), test_bytes=tuple(range(8)), mode='bits', value_range=(0, 63), step_size=1,
                step_period=4.0, send_period=cluster.SPEED_FIVE, sample_data=[0x05, 0x1B, 0x40, 0x04, 0x0F, 0x83, 0x42, 0x00],
                describe=bit),
    'transwarm': dict(can_ids=(0x431,), test_bytes=tuple(range(8)), mode='bits', value_range=(0, 63), step_size=1,
                step_period=4.0, send_period=cluster.SPEED_FIVE, sample_data=[0x05, 0x1D, 0x40, 0xEB, 0xB7, 0x83, 0x46, 0x00],
                describe=bit),
    # 0x048 (s550_cluster.py APIM_2), the APIM doesn't boot without it. Its 0x290 byte 0 goes 01 (starting) -> 7F (up),
    # and drops to 4F when 0x048 stops. Only bytes 4 (07) and 6 (E0) have bits set, flip one bit of 4 - 6 at a time,
    # slow enough for the APIM to drop and come back. Run with apim_capture.py --ignition, it prints 0x290 as it changes
    'apim048': dict(can_ids=(0x048,), test_bytes=(4, 5, 6), mode='bits', value_range=(32, 55), step_size=1,
                step_period=12.0, send_period=cluster.SPEED_THREE, sample_data=[0x00, 0x00, 0x00, 0x00, 0x07, 0x00, 0xE0, 0x00],
                describe=bit),
    # 0x77 A/B: our 40 mph frame (send_vehicle_speed_77) and FF FF FF FF FF FF 00 FC, reported to stop the steering assist
    # warnings (every ABS signal at max = invalid, longitudinal accel -9 m/s^2). Switches every 20 s, run with
    # --dummydata --speed 40 and EPAS enabled in the as-built. The whole frame is one number, one step goes A -> B -> A
    'steer77': dict(can_ids=(0x77,), test_bytes=tuple(range(8)), mode='incremental',
                value_range=(0x1B5808007FF7E602, 0xFFFFFFFFFFFF00FC), step_size=0xFFFFFFFFFFFF00FC - 0x1B5808007FF7E602,
                step_period=20.0, send_period=cluster.SPEED_TWO, sample_data=[0] * 8,
                describe=lambda v: '{} -> {}'.format(v.to_bytes(8, 'big').hex(' '),
                                                     'FF frame' if v == 0xFFFFFFFFFFFF00FC else 'normal 40 mph')),
    # 0x3B3 byte 4, the APIM shows -26f with s550_cluster.py's 0x10: the digital cluster's outside temp scale
    # (raw * 0.5 - 40 c) gives -25.6f. The 2015 - 2017 logs only have 10 (18 with turn signals, E0 / E6 at shutdown),
    # so stay under E0. 0x50 = 0c / 32f, 0x78 = 20c / 68f
    'apimtemp': dict(can_ids=(0x3B3,), test_bytes=(4,), mode='sequential', value_range=(0x10, 0xC0), step_size=0x10,
                step_period=8.0, send_period=cluster.SPEED_FOUR, sample_data=[0x40, 0x48, 0x02, 0x0A, 0x10, 0x05, 0x00, 0x02],
                describe=lambda v: '{:#04x} -> {:.1f}c / {:.0f}f if outside temp'.format(v, v * 0.5 - 40, (v * 0.5 - 40) * 9 / 5 + 32)),
    # 0x048 byte 4 every value 00 - 1F. apim048 found 07 / 06 on, 03 / 17 off, 05 no change, 27 on: looks like Ford's
    # power mode (names below are a guess). Booting takes up to ~25 s (0x290 01 -> 7F), so each value is held 30 s
    'apimpower': dict(can_ids=(0x048,), test_bytes=(4,), mode='sequential', value_range=(0x00, 0x1F), step_size=1,
                step_period=30.0, send_period=cluster.SPEED_THREE, sample_data=[0x00, 0x00, 0x00, 0x00, 0x07, 0x00, 0xE0, 0x00],
                describe=lambda v: '{:#04x} -> {}'.format(v, POWER_MODES.get(v, '?'))),
}
parser = argparse.ArgumentParser(description='Sweep a CAN signal on the cluster')
parser.add_argument('test', nargs='?', default='afr', choices=TESTS)
parser.add_argument('--gt', action='store_true', help="also send the GT log IDs s550_cluster.py doesn't")
parser.add_argument('--gt-only', type=replay.parse_ids, default=set(), help='comma separated GT log IDs to send (implies --gt)')
parser.add_argument('--gt-skip', type=replay.parse_ids, default=set(), help='comma separated GT log IDs to leave out')
parser.add_argument('--mute', type=replay.parse_ids, default=set(),
                    help="comma separated IDs s550_cluster.py (and --dummydata) won't send, to find which one causes a warning")
parser.add_argument('--speed', type=float, default=40, help='mph shown on the cluster and sent in the speed frames (default 40)')
parser.add_argument('--gt-all', action='store_true', help="send every GT log ID, replacing s550_cluster.py's versions too. "
                    "s550_cluster.py only fills the IDs the log doesn't have")
parser.add_argument('--dummydata', action='store_true',
                    help='add steady chassis messages (wheel speeds, yaw, accelerometer, steering ...) with matching speeds')
parser.add_argument('--pscm', action='store_true',
                    help='send the power steering frames that go with 0x82: 0x85 and 0x7E (rolling counter + checksum), '
                         '0x3A8. On by itself when 0x82 is under test')
parser.add_argument('--nm', type=replay.parse_ids, default=set(), metavar='IDS',
                    help='send "module alive" frames (ID low byte, 00, FF x6 at 1 Hz) for these IDs, e.g. 0x500-0x5FF. '
                         "IDs the cluster sends itself are skipped")
parser.add_argument('--respond', type=lambda v: int(v, 0), nargs='?', const=0x01, default=None, metavar='VALUE',
                    help='answer the 0x3E0 requests on 0x3E3, VALUE is byte 1 of the reply (default 0x01, as in the GT log)')
parser.add_argument('--respond-tail', type=lambda v: bytes.fromhex(v)[:3].ljust(3, bytes(1)), default=bytes(3), metavar='"B5 B6 B7"',
                    help='bytes 5 - 7 of the 0x3E3 reply, e.g. "01 64 00" (default 00 00 00)')
parser.add_argument('--respond-sweep', type=int, choices=range(8), default=None, metavar='BYTE',
                    help='add 1 to this reply byte each time the cluster repeats a request')
parser.add_argument('--respond-0701', type=lambda v: bytes.fromhex(v)[:8].ljust(8, bytes(1)), metavar='"B0 .. B7"',
                    default=bytes.fromhex('8000000701800000'),
                    help='the whole 0x3E1 reply to request 07 01 (default 80 00 00 07 01 80 00 00, the freeze frame)')
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

cluster_speed = args.speed # mph shown on the cluster

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
    # in cluster_tx_changes.csv too, so what the module did can be lined up with the value under test
    cluster_tx_changes.append((time.time() - cluster.start, 'test', describe(value).replace(',', ';')))

# the regular cluster functions still run, drop anything they send on an ID this script owns
_send_msg = cluster.send_msg
gt_ids = set() # GT log IDs taken over with --gt-only, s550_cluster.py's versions are dropped
def _filtered_send_msg(id, ts, data):
    if id in can_ids or id in gt_ids or id in args.mute:
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
        cluster_tx_changes.append((time.time() - cluster.start, 'key', 'paused' if paused else 'resumed'))
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
rx_hooks = [] # functions called with every received frame (fake_forscan.py's fake modules)
show_status = True # the once a second frames/s line, fake_forscan.py turns it off
tx_name = 'cluster' # the module on the other end of the bus, for the new ID lines. apim_capture.py sets 'apim'
quiet_ids = () # IDs left out of the new ID lines, fake_forscan.py prints the diagnostic range itself

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
        if msg.arbitration_id not in cluster_tx and msg.arbitration_id not in quiet_ids:
            print('* {} sends {:#05x}: {}'.format(tx_name, msg.arbitration_id, msg.data.hex(' ')))
        if cluster_tx.get(msg.arbitration_id) != bytes(msg.data):
            cluster_tx_changes.append((time.time() - cluster.start, '{:#05x}'.format(msg.arbitration_id), msg.data.hex(' ')))
        cluster_tx[msg.arbitration_id] = bytes(msg.data)
        for hook in rx_hooks:
            hook(msg)
        if args.respond is not None and msg.arbitration_id == 0x3E0:
            if msg.data[0] and msg.data[4] & 0x04:
                respond(msg.data)
            else:
                request_done()
        counts = cluster_tx_log.setdefault(msg.arbitration_id, {})
        counts[bytes(msg.data)] = counts.get(bytes(msg.data), 0) + 1

# request -> the ID its module answers on, 0x3E3 for the rest. 12 Nov 2026 - 07 01 on 0x3E1: the freeze frame from this
# cluster's car has 0x3E1 as 80 00 00 07 01 80 00 00, a different layout (--respond-0701 sends the whole frame)
REPLY_IDS = {bytes([0x04, 0x07]): 0x3E6, bytes([0x07, 0x01]): 0x3E1}
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
    if key == bytes([0x07, 0x01]):
        data = list(args.respond_0701)
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
        if show_status:
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


def main():
    '''
        Schedules everything the command line asked for and runs the cluster. fake_forscan.py imports this file and
        calls it after adding its rx_hooks
    '''
    global test_bytes, can_ids
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
        cluster.SCHEDULE.extend(cluster.DUMMY_SCHEDULE)
        print('* Dummy data: 0x217 0x415 (speeds follow {} mph), 0x85 0x91 0x200 0x82 0x230'.format(cluster_speed))
    if 0x82 in can_ids:
        args.pscm = True
    if args.pscm:
        for period, funcs in cluster.PSCM_SCHEDULE:
            # --dummydata already sends 0x85, a second copy would put two counters on the bus
            funcs = [f for f in funcs if not (args.dummydata and f is cluster.send_misc_4)]
            cluster.SCHEDULE.append((period, funcs))
        print('* Power steering: 0x85 0x7E (counter + checksum), 0x3A8')
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


if __name__ == "__main__":
    main()
