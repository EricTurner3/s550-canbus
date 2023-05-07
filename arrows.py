'''
    CanBus - Arrow Keys
    Eric Turner
    6 May 2023

    
    

    This script allows you use your arrow keys / enter to interface with the cluster
'''
import can
import time
from pynput import keyboard
from multiprocessing.pool import ThreadPool as Pool


key = None

start = time.time()

# VARIABLES
# change the channel and bitrate as needed
bus = can.interface.Bus(bustype='slcan', channel='COM3', bitrate=500000)
speed = 0.1 # speed in ms to send messages
can_ids = (0x81,) # tuple of CAN Ids to brute force. They will all be set to the same
sample_data = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00] # sample set of data to start with

# SAMPLE DATA - 2015 Ford Mustang GT - Manual - MyColor
# 200 => [0x00, 0x00, 0x7F, 0xF0, 0x81, 0x57, 0x00, 0x00]
# 204 => [0xC0, 0x00, 0x7D, 0x00, 0x00, 0x00, 0x00, 0x00]
# 3B3 => [0x40, 0x8B, 0x0a, 0x12, 0x18, 0x05, 0xC0, 0xE2]

def send_msg(id, ts, data, verbose=True):
    try:
        msg = can.Message(timestamp = time.time() - ts, arbitration_id=id,
                    data=data,
                    is_extended_id=False)
        bus.send(msg)
        if (verbose):
            print(msg, end="")
    except can.CanError:
        print("   {} - Message NOT sent".format(str(hex(id))))

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
    
    send_msg(0x81, start, data)  
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

'''
    Generates a random byte from 0x00 to 0xFF in order
    Pass a tuple index to modify the sample data to the random byte for a brute force method of determining what the code does
'''


def send_on():
    while(True):
        send_msg(0x3B3, start, [0x40, 0x8B, 0x02, 0x0a, 0x18, 0x05, 0xC0, 0xE2], verbose=False)
        time.sleep(speed)

def send_null():
    while(True):
        send_msg(0x81, start, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        print('')
        time.sleep(speed*2)

def keys():
    listener = keyboard.Listener(on_press=on_press)
    listener.start()  # start to listen on a separate thread
    listener.join()  # remove if main thread is polling self.keys
    
pool = Pool(3)
pool.apply_async(send_on) # send the 0x3B3 on command
pool.apply_async(send_null) # send a blank version of 0x81
pool.apply_async(keys) # send whatever key is pressed to send to the cluster
pool.close()
pool.join()