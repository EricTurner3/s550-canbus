import csv
import base64
import sys 
import can
import time
from pynput import keyboard

from multiprocessing.pool import ThreadPool as Pool

gap = 0.01

start = time.time()

# VARIABLES
# change the channel and bitrate as needed
bus = can.interface.Bus(bustype='slcan', channel='COM3', bitrate=500000)

data = []

def send_msg(id, ts, data, verbose=True):
    try:
        msg = can.Message(timestamp = ts, arbitration_id=id,
                    data=data,
                    is_extended_id=False)
        bus.send(msg)
        if (verbose):
            print(msg)
    except can.CanError:
        print("   {} - Message NOT sent".format(str(hex(id))))

with open(sys.argv[1], newline='') as f:
    reader = csv.reader(f)
    for row in reader:
        data.append(row)
            
def send_on():
    while(True):
        send_msg(0x3B3, start, [0x40, 0x8B, 0x02, 0x0b, 0x18, 0x05, 0xC0, 0xE2], verbose=False)
        time.sleep(0.16)


def replay(data):
    for row in data:
        id = int(row[1],16)
        ts = float(row[0])
        #convert the b64 to hex
        c = base64.b64decode(row[6]).hex()
        # convert the hex string into an int range
        data = [int(c[i:i+2],16) for i in range(0,len(c),2)]
        # replace that in the function
        send_msg(id, ts, data)

# 4 Feb 2024 - add ability to interact with cluster during a replay
def arrows_test(direction):
    UP = 0x08
    DOWN = 0x01
    LEFT = 0x02
    RIGHT = 0x04
    ENTER = 0x10
    data = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

    if(direction == 'up'):
        data[0] = UP
    elif(direction == 'down'):
        data[0] = DOWN
    elif(direction == 'left'):
        data[0] = LEFT
    elif(direction == 'right'):
        data[0] = RIGHT
    elif(direction == 'enter'):
        data[0] = ENTER
    
    send_msg(0x81, start, data, verbose=False)  
    print('')        

def on_press(key):
    try:
        k = key.char  # single-char keys
    except:
        k = key.name  # other keys
    if k in ['up', 'down', 'left', 'right', 'enter']:  # keys of interest
        # self.keys.append(k)  # store it in global-like variable
        print('Key pressed: ' + k)
        arrows_test(k)
        #return k  # stop listener; remove this if want more keys

def keys():
    listener = keyboard.Listener(on_press=on_press)
    listener.start()  # start to listen on a separate thread
    listener.join()  # remove if main thread is polling self.keys

data.remove(data[0]) # remove header

pool = Pool(3)
#pool.apply_async(send_on) # send the 0x3B3 on command at 0.16 interval to keep cluster alive
pool.apply_async(replay, (data,)) # replay the data from log at a slower pace to rev eng
pool.apply_async(keys) # send whatever key is pressed to send to the cluster.
pool.close()
pool.join()