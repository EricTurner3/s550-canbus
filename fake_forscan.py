'''
    CanBus - Fake Forscan
    Eric Turner
    9 Nov 2026

    Runs interactive_brute_force.py and answers a scan tool (Forscan) as the modules a bench doesn't have, so it finds
    a car and goes on to the cluster (0x720). Forscan first asks the PCM (OBD on 0x7DF, UDS on 0x7E0) for the VIN, then
    pings each module with 22 02 00 and stops at the BCM (0x726) if it doesn't answer. Any answer, even 7F (not
    supported), counts as the module being there. The real cluster always answers for itself.

    Every option but --modules goes to interactive_brute_force.py. The test defaults to idle (nothing under test) and
    the speed to 0 (modules can refuse config writes while moving)
        python fake_forscan.py --dummydata --respond --config --vin 1FA6P8...
        python fake_forscan.py --dummydata --respond --config --vin 1FA6P8... --modules 0x726,0x7E1,0x7D0,0x784,0x736
        python fake_forscan.py epasbyte1 --dummydata --vin 1FA6P8...

    Prints each request a fake module answers (- fake) and every other diagnostic frame (- diag, 0x700 - 0x7FF): the
    scan tool's requests to the real modules and their replies. --status brings back the frames/s line
'''
import argparse
import sys
import time
import replay

PCM_REQ = 0x7E0 # engine diagnostic request, 0x7DF = functional (all modules). Each module answers on request + 8
CLUSTER_REQ = 0x720

# diagnostic request ID -> module, for the log. From the Ford DBC's TesterPhysicalReq / Res messages, Forscan's own
# scan (ICM, PAM, BdyCM) and database.md (OCSM). Forscan also pings these, names not known yet:
# 0x701 0x714 0x751 0x776 0x783 0x790 0x7A5 0x7B0 0x7B1 0x7B2 0x7B7 0x7D5
MODULES = {
    0x6F2: 'SODCMC - Side Obstacle Detection Control Module C',
    0x6F3: 'SODCMD - Side Obstacle Detection Control Module D',
    0x706: 'IPMA - Image Processing Module A',
    0x716: 'GWM - Gateway Module',
    0x720: 'IPC - Instrument Panel Cluster',
    0x721: 'VDM - Vehicle Dynamics Module',
    0x724: 'SCCM - Steering Column Control Module',
    0x726: 'BCM - Body Control Module',
    0x727: 'ACM - Audio Control Module',
    0x730: 'PSCM - Power Steering Control Module',
    0x733: 'HVAC - Climate Control Module',
    0x734: 'HCM - Headlamp Control Module',
    0x736: 'PAM - Parking Aid Module',
    0x737: 'RCM - Restraints Control Module',
    0x740: 'DDM - Driver Door Module',
    0x741: 'PDM - Passenger Door Module',
    0x744: 'DSM - Driver Seat Module',
    0x754: 'TCU - Telematics Control Unit',
    0x760: 'ABS - Anti-lock Brake / Stability Control',
    0x761: 'TCCM - Transfer Case Control Module',
    0x764: 'CCM - Cruise Control Module (radar)',
    0x765: 'OCSM - Occupant Classification Sensor Module',
    0x784: 'ICM - Information Center Module',
    0x7A7: 'FCIM - Front Controls Interface Module',
    0x7C1: 'CMR - Camera Module Rear',
    0x7C4: 'SODL - Side Obstacle Detection Left',
    0x7C6: 'SODR - Side Obstacle Detection Right',
    0x7D0: 'APIM - SYNC',
    0x7DF: 'all modules (OBD functional)',
    0x7E0: 'PCM - Powertrain Control Module',
    0x7E1: 'TCM - Transmission Control Module',
    0x7E6: 'SOBDMC - Secondary On-Board Diagnostic Control Module',
}

def module_name(id):
    '''
        '0x720 (IPC - Instrument Panel Cluster)', replies (request + 8) get 'reply' added. Unknown IDs print bare
    '''
    if id in MODULES:
        return '{:#05x} ({})'.format(id, MODULES[id])
    if id - 8 in MODULES and id - 8 != 0x7DF:
        return '{:#05x} ({} reply)'.format(id, MODULES[id - 8])
    return '{:#05x}'.format(id)

parser = argparse.ArgumentParser(description='Answer Forscan as a PCM / BCM, everything else goes to interactive_brute_force.py')
parser.add_argument('--modules', type=replay.parse_ids, default={0x726}, metavar='IDS',
                    help='diagnostic request IDs to answer as fake modules besides the PCM (reply on ID + 8), '
                         'default 0x726 (BCM). 0x720 (the cluster) is never faked')
parser.add_argument('--status', action='store_true',
                    help="show interactive_brute_force.py's once a second frames/s line (off here, the log is about the scan tool)")
args, rest = parser.parse_known_args()
if not rest or rest[0].startswith('-'):
    rest = ['idle'] + rest
if '--speed' not in rest:
    rest += ['--speed', '0']
sys.argv = ['interactive_brute_force.py'] + rest

import interactive_brute_force as ib # parses sys.argv and opens the bus

fake_modules = {PCM_REQ: PCM_REQ + 8} # request ID -> response ID
fake_modules.update({id: id + 8 for id in args.modules - {CLUSTER_REQ}})
pending = {} # response ID -> ISO-TP consecutive frames waiting for the tester's flow control
vin = (ib.args.vin or '').encode('ascii')

def module_reply(rsp, payload):
    '''
        One UDS / OBD reply from a fake module, split into ISO-TP frames when it doesn't fit in one.
        The rest goes out when the tester sends flow control (30 ..) to the module
    '''
    if len(payload) <= 7:
        ib._send_msg(rsp, ib.cluster.start, [len(payload)] + list(payload) + [0x00] * (7 - len(payload)))
        return
    ib._send_msg(rsp, ib.cluster.start, [0x10 | len(payload) >> 8, len(payload) & 0xFF] + list(payload[:6]))
    rest = payload[6:]
    pending[rsp] = [[0x20 | (n + 1) & 0x0F] + list(rest[i:i + 7]) + [0x00] * (7 - len(rest[i:i + 7]))
                    for n, i in enumerate(range(0, len(rest), 7))]

def module_respond(id, data):
    '''
        PCM only, OBD: 01 00 / 09 00 supported PIDs, 09 02 VIN, 01 0C rpm / 01 0D speed (0), 03 / 07 / 0A no DTCs.
        Every fake module: 22 F190 VIN, 10 sessions, 3E tester present, 7F (not supported) for the rest.
        Functional (0x7DF) requests are answered by the PCM only, and only the ones it supports
    '''
    rsp = fake_modules.get(id, PCM_REQ + 8)
    if data[0] >> 4 == 3: # flow control for a multi frame reply
        stmin = data[2] / 1000 if data[2] <= 0x7F else 0
        for frame in pending.pop(rsp, []):
            ib._send_msg(rsp, ib.cluster.start, frame)
            time.sleep(max(stmin, 0.001))
        return
    if data[0] >> 4 != 0:
        return
    req = data[1:1 + (data[0] & 0x0F)]
    if not req:
        return
    sid = req[0]
    pcm = rsp == PCM_REQ + 8
    reply = None
    if pcm and req == b'\x01\x00':
        reply = b'\x41\x00\x00\x18\x00\x00' # PIDs 0C, 0D
    elif pcm and req == b'\x01\x0C':
        reply = b'\x41\x0C\x00\x00'
    elif pcm and req == b'\x01\x0D':
        reply = b'\x41\x0D\x00'
    elif pcm and sid in (0x03, 0x07, 0x0A): # stored / pending / permanent DTCs: none
        reply = bytes([sid + 0x40, 0x00])
    elif pcm and req == b'\x09\x00':
        reply = b'\x49\x00\x40\x00\x00\x00' # PID 02 (VIN)
    elif pcm and req == b'\x09\x02' and vin:
        reply = b'\x49\x02\x01' + vin
    elif req == b'\x22\xF1\x90' and vin:
        reply = b'\x62\xF1\x90' + vin
    elif sid == 0x10 and len(req) > 1:
        reply = bytes([0x50, req[1], 0x00, 0x32, 0x01, 0xF4])
    elif sid == 0x3E and len(req) > 1:
        reply = None if req[1] & 0x80 else b'\x7E\x00'
    elif id != 0x7DF:
        reply = bytes([0x7F, sid, 0x31 if sid == 0x22 else 0x11])
    if reply:
        module_reply(rsp, reply)
        print(' - fake {} {} -> {:#05x} {}'.format(module_name(id), req.hex(' '), rsp, reply.hex(' ')))
    else:
        print(' - fake {} {} (no reply)'.format(module_name(id), req.hex(' ')))

def on_frame(msg):
    if msg.arbitration_id in fake_modules or msg.arbitration_id == 0x7DF:
        module_respond(msg.arbitration_id, bytes(msg.data))
    elif msg.arbitration_id >= 0x700: # the scan tool's requests to other modules and their replies
        print(' - diag {}: {}'.format(module_name(msg.arbitration_id), msg.data.hex(' ')))

if __name__ == '__main__':
    if not vin:
        print('* No --vin, the fake modules answer VIN requests with 7F (Forscan asks you to pick the car)')
    print('* Fake modules: {}'.format(', '.join(module_name(id) for id in sorted(fake_modules))))
    ib.rx_hooks.append(on_frame)
    ib.show_status = args.status
    ib.main()
