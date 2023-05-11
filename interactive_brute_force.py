'''
    CanBus - Interactive Brute Force
    Eric Turner
    6 May 2023

    
    

    This script allows you use your arrow keys / enter to interface with the cluster.
    Also allows you to test brute force options
'''
import can
import time
from pynput import keyboard
from multiprocessing.pool import ThreadPool as Pool
from random import randint


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
        send_msg(0x81, start, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], verbose=False)
        print('')





        time.sleep(speed*2)


def send_random_pairs(id, index):
    rand = randint(0, 65535) # 0x00 - 0xFF
    rand_hex = bytearray(rand.to_bytes(2, 'big'))
    data = [0x40, 0x8B, 0x02, 0x12, 0x18, 0x05, 0xC0, 0xE2]
    data[index] = rand_hex[0]
    send_msg(id, start, data)
    print(' - {}'.format(rand_hex[0]))

'''
    Generates a random byte from 0x00 to 0xFF in order
    Pass a tuple index to modify the sample data to the random byte for a brute force method of determining what the code does
'''
def send_sequential_byte(index, can_ids, speed, data=[00,00,00,00,00,00,00,00]):
    for x in range(0x00, 0xFF):
        for id in can_ids:
            data = data
            for i in index:
                data[i] = x
            send_msg(id, start, data)
            print(' - {}'.format(str(x)))
        time.sleep(speed)

# m#erged bruteforce.py into here
'''
    Similar to the above function, except this one will increment over multiple byte ranges.
    So it will treat multiple bytes as one large number and increment it all together. 
'''
def send_incremental_bytes(starting_index, starting_byte, num_bytes, can_ids, speed, data=[00,00,00,00,00,00,00,00]):
    min = starting_byte
    max = int('0x' + ('FF' * num_bytes), 16)
    for x in range(min, max):
        new_bytes = x.to_bytes(num_bytes, 'big')
        for id in can_ids:
            for i in range(len(new_bytes)):
                data[i + (starting_index)] = new_bytes[i] # replace bytes
            send_msg(id, start, data)
            print(' - {}'.format(str(x)))
        time.sleep(speed)
# this method allows us to also run the brute force commands but still use arrows
# this way I can start experimenting with digital gauges such as oil pressure or air/fuel ratio
def brute_force():
    while(True):
        send_incremental_bytes(
                        starting_index=0 , #0 tart
                        starting_byte = 0x3000,
                        num_bytes= 2, # 1 start
                        can_ids=(0x454,), 
                        speed=0.16, 
                        data=[0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30]
                    )

def send_0x5__series():
    x5xx_SERIES_1 = 0x581
    x5xx_SERIES_2 = 0x596
    x5xx_SERIES_3 = 0x59E
    x5xx_SERIES_4 = 0x5B3
    x5xx_SERIES_5 = 0x5B5
    # not sure what these do but since they seem to be hard coded, gonna send them
    send_msg(x5xx_SERIES_1, start, [0x81, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    send_msg(x5xx_SERIES_2, start, [0x96, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    send_msg(x5xx_SERIES_3, start, [0x9E, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    send_msg(x5xx_SERIES_4, start, [0xB3, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    send_msg(x5xx_SERIES_5, start, [0xB5, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])

def keys():
    listener = keyboard.Listener(on_press=on_press)
    listener.start()  # start to listen on a separate thread
    listener.join()  # remove if main thread is polling self.keys
    


pool = Pool(5)
pool.apply_async(send_on) # send the 0x3B3 on command
pool.apply_async(send_null) # send a blank version of 0x81
pool.apply_async(keys) # send whatever key is pressed to send to the cluster.
pool.apply_async(brute_force) # test out our brute force data, comment this out if not needed
pool.apply_async(send_0x5__series)
pool.close()
pool.join()