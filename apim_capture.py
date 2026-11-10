'''
    CanBus - APIM Capture
    Eric Turner
    10 Nov 2026

    Logs everything the APIM (SYNC) sends on the bench. Start the script first, then power the APIM, so its first
    frames are in the log. Ctrl+C stops it and prints a summary of each ID it heard.

    1. Listen only, nothing sent. Does it talk with just power, or wait for the car?
        python apim_capture.py
    2. Our car on the bus (interactive_brute_force.py idle --dummydata --respond --config --speed 0), what changes
        python apim_capture.py --ignition --vin 1FA6P8...
       Any other interactive_brute_force.py option is passed along (--gt, --freeze, --nm ...). 0x044 0x048 0x109 are
       frames the car sends the APIM, it doesn't boot without them. --mute one at a time to find which it needs
    3. Same, through fake_forscan.py so Forscan finds a car. Wait for 0x290 01 -> 7f (booted) before connecting
        python apim_capture.py --forscan --vin 1FA6P8...
       fake_forscan.py's --modules is passed along too. The APIM should answer diagnostics on 0x7D8 (requests on 0x7D0)
    4. --ignition, and once 0x290 says booted, ask every diagnostic ID 0x700 - 0x7F7 (and 0x7DF) for a session, then
       repeat a few common requests to 0x7D0. Every 0x7xx frame heard is printed. Unplug Forscan for this one
        python apim_capture.py --probe --vin 1FA6P8...

    The adapter doesn't echo our frames, so everything logged came from another module: with the APIM alone on the
    bus, that's the APIM. With the cluster plugged in too, --hide-ipc leaves the cluster's IDs out of the summary.
    The adapter still has to ACK, without another node to ACK the APIM's frames it repeats the first one forever.

    Saves can/apim/apim_<mode>_<time>.csv (python-can CSV like the other logs, replay.py / decode_can_log.py read it)
    and can/apim/apim_<mode>_<time>_summary.csv. Its own folder, the web viewer reads can/*.csv as the GT350's logs.
    --ignition / --forscan also write _tx.csv / _changes.csv (interactive_brute_force.py's cluster_tx.csv /
    cluster_tx_changes.csv, kept apart so the cluster's copies aren't overwritten)
'''
import argparse
import atexit
import os
import sys
import threading
import time
import can
import replay

# IDs worth a note in the summary
NOTES = {
    0x044: 'we send this (APIM_1), the APIM should not',
    0x048: 'we send this (APIM_2), the APIM should not',
    0x109: 'we send this (APIM_3), the APIM should not',
    0x290: 'APIM state, byte 0: 01 starting, 7F up, 4F up without 0x048',
    0x2E3: 'byte 0 01 starting / 02 up. Held at zeros clears the cluster U0253 (lost comm APIM)',
    0x7D8: 'APIM diagnostic reply',
}
WATCH = {0x290, 0x2E3} # printed every time they change
SHOW_FIRST = 40 # frames printed in full from power up, after that only new IDs

parser = argparse.ArgumentParser(description='Log what the APIM sends, listen only or with our car on the bus')
parser.add_argument('--ignition', action='store_true',
                    help='also send our car (interactive_brute_force.py idle --dummydata --respond --config --speed 0)')
parser.add_argument('--forscan', action='store_true', help='--ignition through fake_forscan.py, so Forscan finds a car')
parser.add_argument('--probe', action='store_true', help='--ignition, then look for the diagnostic ID the APIM answers on')
parser.add_argument('--hide-ipc', action='store_true', help="leave the cluster's own IDs (replay.CLUSTER_TX_IDS) out of the summary")
parser.add_argument('--verbose', action='store_true', help='print every frame, not just the first {}'.format(SHOW_FIRST))
parser.add_argument('--watch', type=replay.parse_ids, default=WATCH, metavar='IDS',
                    help='comma separated IDs printed every time they change (default 0x290,0x2E3, the APIM state)')
args, rest = parser.parse_known_args()

args.ignition = args.ignition or args.probe
mode = 'forscan' if args.forscan else 'probe' if args.probe else 'ignition' if args.ignition else 'listen'
os.makedirs(os.path.join('can', 'apim'), exist_ok=True)
base = os.path.join('can', 'apim', 'apim_{}_{}'.format(mode, time.strftime('%Y%m%d_%H%M%S')))
start = time.time()

if args.ignition or args.forscan:
    if not rest or rest[0].startswith('-'):
        rest = ['idle'] + rest
    for flag in ('--dummydata', '--respond', '--config'):
        if flag not in rest:
            rest.append(flag)
    if '--speed' not in rest:
        rest += ['--speed', '0']
    if args.forscan:
        sys.argv = ['fake_forscan.py'] + rest
        import fake_forscan # takes --modules, imports interactive_brute_force (parses the rest, opens the bus)
        ib = fake_forscan.ib
        fake_forscan.start()
    else:
        sys.argv = ['interactive_brute_force.py'] + rest
        import interactive_brute_force as ib # parses sys.argv and opens the bus
    ib.tx_name = 'apim'
    ib.CLUSTER_TX_LOG = base + '_tx.csv'
    ib.CLUSTER_TX_CHANGES = base + '_changes.csv'
    bus = ib.cluster.bus
elif rest:
    raise SystemExit('unknown options without --ignition / --forscan: {}'.format(' '.join(rest)))
else:
    import s550_cluster # opens the bus, sends nothing until activate()
    bus = s550_cluster.bus

writer = can.CSVWriter(base + '.csv')
lock = threading.Lock()
frames = 0
first_frame = None # seconds from start
heard = {} # id -> {'count', 'first', 'last', 'payloads': set, 'data'}

def on_frame(msg, show_new=True):
    '''
        Every frame from the bus. show_new prints new IDs, off with --ignition (interactive_brute_force.py prints them)
    '''
    global frames, first_frame
    t = time.time() - start
    data = bytes(msg.data)
    with lock:
        writer.on_message_received(msg)
        frames += 1
        if first_frame is None:
            first_frame = t
            print('* first frame at +{:.3f}s'.format(t))
        seen = heard.get(msg.arbitration_id)
        if seen is None:
            seen = heard[msg.arbitration_id] = {'count': 0, 'first': t, 'payloads': set()}
            if show_new:
                print('* apim sends {:#05x}: {}{}'.format(msg.arbitration_id, data.hex(' '), note(msg.arbitration_id)))
            if args.probe and 0x700 <= msg.arbitration_id <= 0x7FF:
                print('   +{:8.3f}s {:#05x} {} <- diagnostic reply'.format(t, msg.arbitration_id, data.hex(' ')))
        elif args.probe and 0x700 <= msg.arbitration_id <= 0x7FF:
            print('   +{:8.3f}s {:#05x} {} <- diagnostic reply'.format(t, msg.arbitration_id, data.hex(' ')))
        elif msg.arbitration_id in args.watch and seen['data'] != data:
            print('   +{:8.3f}s {:#05x} {} -> {}'.format(t, msg.arbitration_id, seen['data'].hex(' '), data.hex(' ')))
        seen['count'] += 1
        seen['last'] = t
        seen['data'] = data
        seen['payloads'].add(data)
        if args.verbose or frames <= SHOW_FIRST:
            print('   +{:8.3f}s {:#05x} [{}] {}'.format(t, msg.arbitration_id, msg.dlc, data.hex(' ')))

def note(id):
    if id in NOTES:
        return ' ({})'.format(NOTES[id])
    if id in replay.CLUSTER_TX_IDS:
        return ' (cluster ID)'
    return ''

def _listen():
    while True:
        msg = bus.recv(1.0)
        if msg is not None and not msg.is_error_frame:
            on_frame(msg)

# single frame UDS requests, padded with 00 like Forscan's
PROBE_SESSION = [0x02, 0x10, 0x01, 0, 0, 0, 0, 0] # default session, every module answers it (50 01 or 7F 10 ..)
PROBE_REQUESTS = [
    [0x02, 0x10, 0x01, 0, 0, 0, 0, 0],          # default session
    [0x02, 0x3E, 0x00, 0, 0, 0, 0, 0],          # tester present
    [0x03, 0x22, 0xF1, 0x90, 0, 0, 0, 0],       # VIN
    [0x03, 0x22, 0xF1, 0x88, 0, 0, 0, 0],       # strategy
    [0x03, 0x22, 0x02, 0x00, 0, 0, 0, 0],       # what Forscan pings modules with
    [0x02, 0x10, 0x03, 0, 0, 0, 0, 0],          # extended session
]

def _probe():
    '''
        Waits for 0x290 byte 0 7F (booted), or 30 s for a bus it doesn't send 0x290 on (HS1), then 0x7D0 first, a sweep of every request ID, the functional ID, and
        PROBE_REQUESTS to 0x7D0 three times. Replies are printed by on_frame as they come in
    '''
    waited = time.time()
    while True:
        with lock:
            state = heard.get(0x290, {}).get('data')
        if state and state[0] == 0x7F:
            print('* APIM booted, probing')
            break
        if time.time() - waited > 30:
            print('* no 0x290 7F after 30 s, probing anyway')
            break
        time.sleep(0.5)
    ids = [0x7D0] + [id for id in range(0x700, 0x7F8) if id not in (0x7D0, 0x7DF)] + [0x7DF]
    for id in ids:
        ib._send_msg(id, ib.cluster.start, PROBE_SESSION)
        time.sleep(0.05)
    print('* sweep 0x700 - 0x7F7 done, now 0x7D0 requests')
    for n in range(3):
        for data in PROBE_REQUESTS:
            print(' - 0x7d0 {}'.format(bytes(data).hex(' ')))
            ib._send_msg(0x7D0, ib.cluster.start, data)
            time.sleep(0.3)
    print('* probe done, Ctrl+C to stop')

def _status():
    '''
        Frames/s every 2 s, and a reminder if the bus is still quiet
    '''
    last = 0
    while True:
        time.sleep(2)
        with lock:
            count, ids = frames, len(heard)
        if count == 0:
            print('* +{:.0f}s nothing heard yet - power the APIM (check CAN H / L and 120 ohm at each end)'.format(time.time() - start))
        else:
            print('* {:.0f} frames/s, {} IDs, {} frames total'.format((count - last) / 2, ids, count))
        last = count

def changing_bytes(payloads):
    '''
        Positions whose value differs between payloads, e.g. "0 6 7" (counters, checksums, signals)
    '''
    payloads = list(payloads)
    width = max(len(p) for p in payloads)
    return ' '.join(str(i) for i in range(width) if len(set(p[i] if i < len(p) else None for p in payloads)) > 1)

def summary():
    with lock:
        writer.stop()
        ids = sorted(id for id in heard if not (args.hide_ipc and id in replay.CLUSTER_TX_IDS))
        rows = []
        for id in ids:
            s = heard[id]
            span = s['last'] - s['first']
            hz = (s['count'] - 1) / span if span > 0 else 0
            rows.append((id, s['count'], hz, s['first'], len(s['payloads']), changing_bytes(s['payloads']), s['data'].hex(' ')))
    print('\n* {} frames, {} IDs{} - {}.csv'.format(frames, len(rows), ', first at +{:.3f}s'.format(first_frame) if first_frame is not None else '', base))
    if not rows:
        return
    print('   {:>5}  {:>6}  {:>7}  {:>9}  {:>8}  {:<15}  {}'.format('id', 'count', 'hz', 'first s', 'payloads', 'changing bytes', 'last data'))
    for id, count, hz, first, payloads, changing, data in rows:
        print('   {:#05x}  {:>6}  {:>7.2f}  {:>9.3f}  {:>8}  {:<15}  {}{}'.format(id, count, hz, first, payloads, changing or '-', data, note(id)))
    with open(base + '_summary.csv', 'w') as f:
        f.write('id,count,hz,first_s,payloads,changing_bytes,last_data,note\n')
        for id, count, hz, first, payloads, changing, data in rows:
            f.write('{:#05x},{},{:.2f},{:.3f},{},{},{},{}\n'.format(id, count, hz, first, payloads, changing, data, NOTES.get(id, '')))
    print('* summary saved to {}_summary.csv'.format(base))

if __name__ == '__main__':
    atexit.register(summary) # before the bus closes (atexit runs last registered first)
    print('* Logging to {}.csv - power the APIM now, Ctrl+C to stop'.format(base))
    threading.Thread(target=_status, daemon=True).start()
    try:
        if args.ignition or args.forscan:
            ib.show_status = False # _status above prints the APIM's rate instead
            ib.rx_hooks.append(lambda msg: on_frame(msg, show_new=False))
            if args.probe:
                threading.Thread(target=_probe, daemon=True).start()
            ib.main()
        else:
            print('* Listen only, nothing is sent')
            _listen()
    except KeyboardInterrupt:
        pass
