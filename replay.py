import csv
import base64
import sys 
import can
import time

from multiprocessing.pool import ThreadPool as Pool

gap = 0.05

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
        time.sleep(gap)


data.remove(data[0]) # remove header

pool = Pool(2)
#pool.apply_async(send_on) # send the 0x3B3 on command at 0.16 interval to keep cluster alive
pool.apply_async(replay, (data,)) # replay the data from log at a slower pace to rev eng
pool.close()
pool.join()