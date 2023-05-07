'''
    CanBus - Brute Force
    Eric Turner
    6 May 2023

    This script allows you to sequentially brute force a canbus message. Useful for determining what bytes do what function
'''
import can
import time
from random import randint

start = time.time()

# VARIABLES
# change the channel and bitrate as needed
bus = can.interface.Bus(bustype='slcan', channel='COM3', bitrate=500000)
speed = 0.1 # speed in ms to send messages
can_ids = (0x4C,) # tuple of CAN Ids to brute force. They will all be set to the same
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
def send_sequential_byte(index, data=sample_data):
    for x in range(0x00, 0xFF):
        for id in can_ids:
            # 0x3B3 must be passed on the IPC will not turn on
            if (id != 0x3B3):
                # verbose=False to supress the output to console and only see the ID we are brute forcing
                send_msg(0x3B3, start, [0x40, 0x8B, 0x02, 0x0a, 0x18, 0x05, 0xC0, 0xE2], verbose=False)
            data = data
            for i in index:
                data[i] = x
            send_msg(id, start, data)
            print(' - {} - ({})'.format(hex(x), x))
        time.sleep(speed)

# inf loop time
while(True):
    # Index 0 -> 7, can pass a single digit or all digits at once
    # for single digit, ensure you keep the comma after such as (1, )
    # 2+ digits are similar to a list (0, 1, 2, 3)
    send_sequential_byte((1,))