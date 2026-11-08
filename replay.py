'''
    CanBus - Log Replay
    Eric Turner

    Replays a python-can CSV log (the files in /can) onto the bus at the speed it was recorded.

    7 Nov 2026 - rewritten. Frames are paced off the log timestamps instead of being sent as fast as possible,
    per frame printing is gone (it throttled the bus to a trickle), and bytes can be overridden during the replay

    Usage
        python replay.py longerdrive                     -> can/longerdrive.csv
        python replay.py can/start.csv --loop
        python replay.py longerdrive --speed 0.5         -> half speed
        python replay.py longerdrive --skip 0x81         -> drop IDs from the log
        python replay.py longerdrive --only 0x3B3,0x204  -> only send these IDs
        python replay.py longerdrive --set 0x178:7=0x14  -> force byte 7 of 0x178 to 0x14 (repeatable)
        python replay.py "other_refs/v-ivanyshyn_parse_can_logs/log Mustang S550.txt"  -> v-ivanyshyn's 2015 GT log

    Keys
        arrows / enter - menu navigation
        space          - pause / resume
'''
import argparse
import base64
import csv
import os
import threading
import time
import can
from pynput import keyboard

can_adapter_channel = 'COM3'

# 7 Nov 2026 - IDs the cluster (IPC) transmits itself, captured with interactive_brute_force.py (cluster_tx.csv).
# Logs from a car include its cluster's frames, sending them too puts two senders on one ID. Skipped unless --include-ipc
CLUSTER_TX_IDS = {0x18B, 0x19A, 0x220, 0x225, 0x287, 0x2F4, 0x2FD, 0x30A, 0x313, 0x315, 0x316, 0x317, 0x318,
                  0x346, 0x348, 0x350, 0x353, 0x3C8, 0x3E0, 0x3FB, 0x430, 0x434, 0x45A, 0x591,
                  # sent once at power up
                  0x087, 0x123, 0x190, 0x193, 0x195, 0x1EE, 0x1F2, 0x1F8, 0x1F9, 0x1FA, 0x1FB, 0x1FC, 0x363}

# frames sent / failed since the last status line
sent = 0
failed = 0
position = 0.0 # seconds into the log
lag = 0.0 # how far behind the log timestamps we are, grows if the adapter can't keep up
paused = threading.Event()

def parse_ids(text):
    '''
        0x81,0x3B3 or ranges 0x500-0x57F
    '''
    ids = set()
    for part in (text or '').split(','):
        if '-' in part:
            lo, hi = part.split('-')
            ids.update(range(int(lo, 16), int(hi, 16) + 1))
        elif part:
            ids.add(int(part, 16))
    return ids

def parse_set(items):
    '''
        0x178:7=0x14 -> {0x178: {7: 0x14}}
    '''
    overrides = {}
    for item in items or []:
        id, rest = item.split(':')
        byte, value = rest.split('=')
        overrides.setdefault(int(id, 16), {})[int(byte)] = int(value, 0)
    return overrides

def find_log(name):
    for path in (name, name + '.csv', os.path.join('can', name), os.path.join('can', name + '.csv')):
        if os.path.isfile(path):
            return path
    raise SystemExit('Could not find log {}'.format(name))

def read_csv(path):
    '''
        python-can logger CSV (the files in /can)
        columns: timestamp, arbitration_id, extended, remote, error, dlc, data (base64)
    '''
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            if row['remote'] == '1' or row['error'] == '1':
                continue
            yield float(row['timestamp']), int(row['arbitration_id'], 16), base64.b64decode(row['data'])

def read_txt(path):
    '''
        v-ivanyshyn's log format (other_refs/v-ivanyshyn_parse_can_logs), timestamp in ms
            820298   0x085: 7C 33 80 00 47 E0 7C 7F
    '''
    with open(path) as f:
        for line in f:
            parts = line.split(':')
            if len(parts) != 2:
                continue
            ts, id = parts[0].split()
            yield int(ts) / 1000, int(id, 16), bytes.fromhex(parts[1])

def load(path, only, skip, overrides):
    '''
        Returns [(seconds from start, id, data)]
    '''
    frames = []
    reader = read_csv if path.endswith('.csv') else read_txt
    for t, id, data in reader(path):
        if (only and id not in only) or id in skip:
            continue
        data = bytearray(data)
        for i, v in overrides.get(id, {}).items():
            if i < len(data):
                data[i] = v
        frames.append((t, id, data))
    if not frames:
        raise SystemExit('No frames to send from {}'.format(path))
    t0 = frames[0][0]
    return [(t - t0, id, data) for t, id, data in frames]

def send_msg(id, data):
    global sent, failed
    try:
        bus.send(can.Message(arbitration_id=id, data=data, is_extended_id=False))
        sent += 1
    except can.CanError:
        failed += 1

def replay(frames, speed, loop):
    global position, lag
    while True:
        base = time.perf_counter()
        for t, id, data in frames:
            if paused.is_set():
                pause_start = time.perf_counter()
                while paused.is_set():
                    time.sleep(0.05)
                base += time.perf_counter() - pause_start # pick up where we left off
            target = base + t / speed
            wait = target - time.perf_counter()
            if wait > 0.001:
                time.sleep(wait) # frames closer than 1ms apart go out back to back
            lag = max(0.0, -wait)
            position = t
            send_msg(id, data)
        if not loop:
            return
        print('* Looping')

def menu_nav(direction):
    buttons = {'up': 0x08, 'down': 0x01, 'left': 0x02, 'right': 0x04, 'enter': 0x10}
    send_msg(0x81, [buttons[direction], 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

def on_press(key):
    try:
        k = key.char  # single-char keys
    except:
        k = key.name  # other keys
    if k in ['up', 'down', 'left', 'right', 'enter']:
        menu_nav(k)
        print(' - KEY PRESSED: {} - MENU_NAV'.format(k))
    elif k == 'space':
        if paused.is_set():
            paused.clear()
        else:
            paused.set()
        print(' - {}'.format('PAUSED' if paused.is_set() else 'RESUMED'))

def _status(duration):
    global sent, failed
    while True:
        time.sleep(1)
        print('* {:6.1f} / {:.1f}s, {} frames/s, {} failed, {:.2f}s behind'.format(position, duration, sent, failed, lag))
        sent = 0
        failed = 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Replay a CAN log from /can onto the bus')
    parser.add_argument('log', help='log file, e.g. longerdrive or can/longerdrive.csv')
    parser.add_argument('--speed', type=float, default=1.0, help='playback speed, < 1 slows down')
    parser.add_argument('--loop', action='store_true', help='restart the log when it ends')
    parser.add_argument('--only', type=parse_ids, default=set(), help='comma separated IDs to send, everything else is dropped')
    parser.add_argument('--skip', type=parse_ids, default=set(), help='comma separated IDs to drop')
    parser.add_argument('--include-ipc', action='store_true', help="also send the IDs the cluster transmits itself")
    parser.add_argument('--set', action='append', metavar='ID:BYTE=VALUE', help='override a byte, e.g. 0x178:7=0x14')
    args = parser.parse_args()

    path = find_log(args.log)
    skip = args.skip if args.include_ipc else args.skip | CLUSTER_TX_IDS
    frames = load(path, args.only, skip, parse_set(args.set))
    duration = frames[-1][0]
    print('* Loaded {}: {} frames, {:.1f}s ({:.0f} frames/s at 1x)'.format(path, len(frames), duration, len(frames) / duration))
    print('* Keys: arrows / enter navigate, space pause')

    bus = can.ThreadSafeBus(interface='slcan', channel=can_adapter_channel, bitrate=500000)
    try:
        keyboard.Listener(on_press=on_press).start()
        threading.Thread(target=_status, args=(duration,), daemon=True).start()
        replay(frames, args.speed, args.loop)
        print('* Done')
    except KeyboardInterrupt:
        pass
    finally:
        bus.shutdown()
