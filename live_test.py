'''
    Live Test UI
    9 Nov 2026

    Sliders and buttons for every value in s550_data.py, sent to the cluster live through s550_cluster.py's
    scheduler. Lets you check each gauge / icon / warning without a game running. Standard library only.

        python live_test.py                 # COM port from s550_cluster.py, opens http://127.0.0.1:8550
        python live_test.py --com COM5      # different adapter port
        python live_test.py --virtual       # no adapter, frames go to a python-can virtual bus (UI / encoding checks)
        python live_test.py --dummydata     # also send s550_cluster.DUMMY_SCHEDULE (interactive_brute_force.py --dummydata)

    The controls are built from s550_ipc's attributes, so new fields in s550_data.py show up on their own (as a plain
    number box until FIELDS below gives them a range). The comment next to each field is shown as its hint, and fields
    s550_cluster.py never reads are marked "not sent".
    Arrow keys / enter in the page (outside a slider) are the cluster's menu buttons, like s550_cluster.py's keyboard nav
'''
import argparse
import inspect
import json
import os
import re
import threading
import time
import webbrowser
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import can

parser = argparse.ArgumentParser(description='Live test UI for s550_data.py values')
parser.add_argument('--com', help="CAN adapter port, overrides s550_cluster.py's can_adapter_channel")
parser.add_argument('--virtual', action='store_true', help='no adapter, send to a python-can virtual bus')
parser.add_argument('--dummydata', action='store_true', help='also send s550_cluster.DUMMY_SCHEDULE')
parser.add_argument('--port', type=int, default=8550, help='web UI port (default 8550)')
parser.add_argument('--no-browser', action='store_true', help="don't open the browser")
args = parser.parse_args()

# s550_cluster.py opens the bus on import, so swap the adapter / port in before importing it
_real_bus = can.ThreadSafeBus
def _bus(*a, **kw):
    if args.virtual:
        kw.update(interface='virtual', channel='s550_live_test')
    elif args.com:
        kw['channel'] = args.com
    return _real_bus(*a, **kw)
can.ThreadSafeBus = _bus

# no game here, and games.fh5 binds Forza's UDP port on import (fails if s550_cluster.py is running)
import sys
import types
sys.modules['games.fh5'] = types.ModuleType('games.fh5')
sys.modules['games.ats'] = types.ModuleType('games.ats')

import s550_cluster as cluster
import s550_data

HERE = os.path.dirname(os.path.abspath(__file__))

# kind: tri (0 off / 1 on / 2 flashing, `states` limits it), switch (0 / 1 int), bool, range, number
# fields not listed here get a group from their prefix and a number box
FIELDS = {
    'engine_on':              dict(group='Power', kind='switch'),
    'steering_warning_fix':   dict(group='Power', kind='switch'),

    'icon_launch_control':    dict(group='Icons', kind='tri'),
    'icon_abs':               dict(group='Icons', kind='tri'),
    'icon_traction_control':  dict(group='Icons', kind='tri'),
    'icon_airbag':            dict(group='Icons', kind='tri'),
    'icon_seatbelt':          dict(group='Icons', kind='tri', states=[0, 1]),
    'icon_parking_brake':     dict(group='Icons', kind='tri', states=[0, 1]),
    'icon_left_signal':       dict(group='Icons', kind='tri'),
    'icon_right_signal':      dict(group='Icons', kind='tri'),
    'icon_high_beams':        dict(group='Icons', kind='tri', states=[0, 1]),
    'icon_check_engine':      dict(group='Icons', kind='tri'),

    'value_speed':            dict(group='Gauges', kind='range', min=0, max=200, step=1, unit='mph'),
    'value_rpm':              dict(group='Gauges', kind='range', min=0, max=10000, step=50, unit='rpm'),
    'value_rpm_max':          dict(group='Gauges', kind='range', min=1000, max=12000, step=100, unit='rpm'),
    'value_odometer':         dict(group='Gauges', kind='number', min=0, max=0xFFFFFF, step=1, unit='km'),
    'value_fuel':             dict(group='Gauges', kind='range', min=0, max=100, step=1, unit='%'),

    'value_boost':            dict(group='Engine', kind='range', min=-14.7, max=25, step=0.1, unit='psi'),
    'value_afr':              dict(group='Engine', kind='range', min=6, max=25.5, step=0.1, unit=':1'),
    'oil_temp':               dict(group='Engine', kind='range', min=-40, max=195, step=1, unit='C'),
    'engine_temp':            dict(group='Engine', kind='range', min=-40, max=195, step=1, unit='C'),
    'cylinder_head_temp':     dict(group='Engine', kind='range', min=-40, max=195, step=1, unit='C'),
    'intake_temp':            dict(group='Engine', kind='range', min=-40, max=127, step=1, unit='C'),
    'outside_temp':           dict(group='APIM', kind='range', min=-40, max=71, step=0.5, unit='C'),
    'compass_heading':        dict(group='APIM', kind='range', min=0, max=315, step=45, unit='°'),

    'accel_lateral':          dict(group='Accelerometer', kind='range', min=-20, max=20, step=0.1, unit='m/s²'),
    'accel_longitudinal':     dict(group='Accelerometer', kind='range', min=-20, max=20, step=0.1, unit='m/s²'),
    'accel_vertical':         dict(group='Accelerometer', kind='range', min=-20, max=40, step=0.1, unit='m/s²'),

    'tire_pressure_fl':       dict(group='Tires', kind='range', min=0, max=60, step=0.5, unit='psi'),
    'tire_pressure_fr':       dict(group='Tires', kind='range', min=0, max=60, step=0.5, unit='psi'),
    'tire_pressure_rr':       dict(group='Tires', kind='range', min=0, max=60, step=0.5, unit='psi'),
    'tire_pressure_rl':       dict(group='Tires', kind='range', min=0, max=60, step=0.5, unit='psi'),
}
PREFIX_GROUPS = [('warning_tire', 'Tire Warnings'), ('warning_trans', 'Transmission Warnings'),
                 ('warning_key', 'Key / Start Warnings'), ('warning_', 'Other Warnings'), ('icon_', 'Icons'),
                 ('tire_', 'Tires'), ('accel_', 'Accelerometer'), ('value_', 'Gauges')]


def _hints():
    # the comment after each `self.x = ...` in s550_data.py
    with open(os.path.join(HERE, 's550_data.py')) as f:
        return dict(re.findall(r'self\.(\w+)\s*=[^#\n]*#\s*(.*)', f.read()))

def _wired():
    # fields the scheduled senders read, as clusterdata.x or by name (the warning tables are module level, so the
    # whole module counts for those). A sender that isn't scheduled (send_odometer) doesn't count
    scheduled = {m for period, funcs in cluster.SCHEDULE for m in funcs}
    unscheduled = [obj for name, obj in vars(cluster).items()
                   if name.startswith('send_') and callable(obj) and obj not in scheduled and name != 'send_msg']
    with open(os.path.join(HERE, 's550_cluster.py')) as f:
        source = f.read()
    for m in unscheduled:
        source = source.replace(inspect.getsource(m), '')
    return lambda name: re.search(r'\b{}\b'.format(name), source) is not None

def schema():
    hints, wired = _hints(), _wired()
    fields = []
    for name, value in vars(state.data).items():
        if name == 'game':
            continue
        meta = dict(FIELDS.get(name, {}))
        if 'kind' not in meta:
            meta['kind'] = 'bool' if isinstance(value, bool) else 'number'
        if 'group' not in meta:
            meta['group'] = next((g for p, g in PREFIX_GROUPS if name.startswith(p)), 'Other')
        meta.update(name=name, value=value, hint=hints.get(name, ''), wired=wired(name))
        fields.append(meta)
    return fields


class State:
    def __init__(self):
        self.data = s550_data.s550_ipc('live_test')
        self.defaults = dict(vars(self.data))
        self.lock = threading.Lock()

    def set(self, values):
        with self.lock:
            for name, value in values.items():
                if name == 'game' or name not in self.defaults:
                    continue
                default = self.defaults[name]
                # keep each field the type the senders expect (odometer goes through int.to_bytes)
                if isinstance(default, bool):
                    value = bool(value)
                elif isinstance(default, int):
                    value = int(round(float(value)))
                else:
                    value = float(value)
                setattr(self.data, name, value)

    def reset(self):
        with self.lock:
            self.data = s550_data.s550_ipc('live_test')
            cluster.clusterdata = self.data

state = State()


# every frame sent, for the frame table. send_msg is looked up as a module global, so replacing it catches all senders
last_frame = {}
frame_count = Counter()
frame_rate = {}
_send_msg = cluster.send_msg

def send_msg(id, ts, data):
    last_frame[id] = list(data)
    frame_count[id] += 1
    return _send_msg(id, ts, data)
cluster.send_msg = send_msg

# CAN ID -> constant name from s550_cluster.py
ID_NAMES = {}
for _name, _value in vars(cluster).items():
    if not _name.islower() and type(_value) is int and _value < 0x800:
        ID_NAMES.setdefault(_value, _name)

def _rates():
    previous = Counter()
    while True:
        time.sleep(1)
        current = Counter(frame_count)
        for id in current:
            frame_rate[id] = current[id] - previous[id]
        previous = current

def frames():
    return {
        'fails': sum(cluster.fail_count.values()),
        'frames': [dict(id=id, name=ID_NAMES.get(id, ''), hz=frame_rate.get(id, 0), data=last_frame[id])
                   for id in sorted(last_frame)],
    }


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            with open(os.path.join(HERE, 'live_test.html'), 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/api/schema':
            self._json(dict(fields=schema(), virtual=args.virtual, dummydata=args.dummydata,
                            channel='virtual' if args.virtual else (args.com or cluster.can_adapter_channel)))
        elif self.path == '/api/frames':
            self._json(frames())
        else:
            self._json({'error': 'not found'}, 404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length) or b'{}')
        if self.path == '/api/set':
            state.set(body)
            self._json({'ok': True})
        elif self.path == '/api/reset':
            state.reset()
            self._json(dict(fields=schema()))
        elif self.path == '/api/nav':
            cluster.MENU_NAV(body.get('direction'))
            self._json({'ok': True})
        else:
            self._json({'error': 'not found'}, 404)

    def log_message(self, *a):
        pass # the UI posts on every slider move, keep the console quiet


if __name__ == '__main__':
    cluster.clusterdata = state.data
    if args.dummydata:
        cluster.SCHEDULE.extend(cluster.DUMMY_SCHEDULE)
    threading.Thread(target=cluster._scheduler, daemon=True).start()
    threading.Thread(target=_rates, daemon=True).start()

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    url = 'http://127.0.0.1:{}'.format(args.port)
    print('* Sending to {}{}'.format('virtual bus' if args.virtual else (args.com or cluster.can_adapter_channel),
                                     ' with dummy data' if args.dummydata else ''))
    print('* Live test UI at {} (ctrl+c to stop)'.format(url))
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
