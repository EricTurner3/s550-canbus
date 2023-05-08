import can
import time
from multiprocessing import Process
from random import randint
import forza # https://github.com/nikidziuba/Forza_horizon_data_out_python
import sys

can_adapter_channel = 'COM3'

pool_size = 8
# start time for timestamps
start = time.time()
# different messages have different polling intervals
# this can be determined by taking one of the converted logs and doing a pivot on id, count(id). Sort by count(id). Notice the groupings of messages
# the higher the speed, the more common it is / the more times that ID is visible in CAN traffic

# this will easily speed up or slow down the traffic while still keeping the speeds at the same interval
# < 1 speeds up; > 1 slows down
modifier = 0.75 
SPEED_ONE = 0.16 * modifier
SPEED_TWO = 0.32  * modifier
SPEED_THREE = 0.48  * modifier
SPEED_FOUR = 0.64  * modifier
SPEED_FIVE = 0.80  * modifier
SPEED_SIX = 1.6  * modifier
SPEED_SEVEN = 3.2  * modifier 
SPEED_EIGHT = 6.4  * modifier

#CAN IDs
RPM = 0x204
SPEED = 0x202
DOOR_STATUS = 0x3B3
SEATBELT = 0x4C
ODOMETER = 0x430
MISC_1 = 0x3C3
MISC_2 = 0x416
MISC_3 = 0x217
MISC_4 = 0x85
MISC_5 = 0x91
MISC_6 = 0x92
MISC_7 = 0x200
MISC_8 = 0x167
MISC_9 = 0x415
MISC_10 = 0x130
LC = 0x178
WARNINGS_1 = 0x179
ENGINE_TEMP = 0x156



# Stock slcan firmware on Windows
bus = can.ThreadSafeBus(bustype='slcan', channel=can_adapter_channel, bitrate=500000)

def send_msg(id, ts, data):
    try:
        msg = can.Message(timestamp = time.time() - ts, arbitration_id=id,
                    data=data,
                    is_extended_id=False)
        bus.send(msg)
        print(msg, end="")
    except can.CanError:
        print("   {} - Message NOT sent".format(str(hex(id))))


def send_seatbelt_icon(forza_data):
    '''
        Byte 0 - 
            0x0_ - Airbag Indicator Off
            0x4_ - Airbag Indicator On
            0x8_ - Airbag Indicator Flashing
        Byte 1 - Seatbelt: 
            0x00 (no icon); 
            0xAF both seltbeats undone
            0x5F pass / driver seatbelts on
            0x6F driver only seatbelt on
            0x9F pass only seatbelt on
    '''

    data = [0x10, 0x5F, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00]
    return send_msg(SEATBELT, start, data)

def send_misc_1(forza_data):
    '''
        Bunch of unknown functions. Can set off vehcile alarm, high beam icon, parking brake message
        Byte 0
            0x4_ -> ?
            0x5_ -> ?
            0x_C -> High Beams Off 
            0x_E -> High Beams On
        Byte 1 - Dimming?
            First Bit: 0, 4, 8, C
            Second Bit: C, D, 8
        Byte 2
            0x0_ -> Parking Brake Off
            0x1_ -> Parking Brake On
        Byte 6  
            0x00 -> ? 
            0x80 -> ?
    '''
    print(int(forza_data['HandBrake']))
    if(int(forza_data['HandBrake'])>0):
        parking_brake_light = 0x10 # on
    else:
        parking_brake_light = 0x00 # off
    
    data =  [0x4C, 0x48, parking_brake_light, 0x01, 0x00, 0x00, 0x00, 0x00]
    return send_msg(MISC_1, start, data)

def send_misc_2(forza_data):
    '''
        ABS, Traction Control Off, Traction Control Loss Icons, Airbag
        Also Advance Trac Service / Brake System Service Warnings (First two bytes)
        Byte 5 has to do with a solid traction control or a flashing icon
            0x00 - Off
            0x02 - Solid
            0x0F - Flashing
    '''
    # flash the traction control icon when wheel slip ratio of any tire is above 10
    # in normal road driving from a track car, seems to stay less than 1
    threshold = 10
    if(forza_data['TireSlipRatioFrontLeft'] >= threshold or \
       forza_data['TireSlipRatioFrontRight'] >= threshold or \
       forza_data['TireSlipRatioRearLeft'] >= threshold or \
       forza_data['TireSlipRatioRearRight'] >= threshold):
        traction_control = 0x0F
    else:
        traction_control = 0x00
    data =  [00, 00, 00, 00, 00, traction_control, 00, 00]
    return send_msg(MISC_2, start, data)

def send_misc_3(forza_data):
    data = [0x1A, 0x58, 0x1A, 0x58, 0x1A, 0x84, 0x1A, 0x74]
    return send_msg(MISC_3, start, data)

def send_misc_4(forza_data):
    data = [0x7C, 0xFF, 0x80, 0x00, 0x7A, 0x40, 0x7C, 0xEA]
    return send_msg(MISC_4, start, data)

def send_misc_5(forza_data):
    data = [0x7E, 0xE3, 0x7F, 0x39, 0x3D, 0x93, 0xF0, 0x00]
    return send_msg(MISC_5, start, data)

def send_misc_6(forza_data):
    data = [0x6F, 0xBA, 0x6F, 0x92, 0x73, 0x62, 0x94, 0x93]
    return send_msg(MISC_6, start, data)

def send_misc_7(forza_data):
    data = [0x00, 0x00, 0x80, 0x47, 0x80, 0x47, 0x00, 0x00]
    return send_msg(MISC_7, start, data)

def send_misc_8(forza_data):
    '''
    Byte 2
        First Byte: 3, 4, F
    '''
    data = [0x72, 0x7F, 0x4B, 0x00, 0x00, 0x19, 0xED, 0x00]
    return send_msg(MISC_8, start, data)
def send_misc_9(forza_data):
    '''
    
    '''
    data = [00, 0x00, 0xD0, 0xFA, 0x0F, 0xFE, 0x0F, 0xFE]
    return send_msg(MISC_9, start, data)

def send_misc_10(forza_data):
    '''
    
    '''
    data = [0x82, 0x00, 0x14, 0x40, 0x7B, 0x00, 0x64, 0xFF]
    return send_msg(MISC_10, start, data)

def send_warnings_1(forza_data):
    '''
        Several Warning messages such as fuel service inlet, change oil soon, oil change required
    '''
    data = [0x00, 0x00, 0x00, 0x00, 0x96, 0x00, 0x02, 0xC8]
    return send_msg(WARNINGS_1, start, data)

def send_launch_control(forza_data):
    '''
    Byte 0 
        0x2_ - LC Icon
        0x8_ - RPM Icon, LC Fault
        0xa_ - LC Flashing Icon
    '''
    data = [0xa0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
    return send_msg(LC, start, data)

def send_door_status(forza_data):
    '''
        Byte 0 & 1 have to do with if the IPC is on
                40 48 is running, doors closed
                41 48 is running, trunk ajar
        Byte 3  has to do with backlight
                0x00 is backlight off
                0x0a is backlight on (mycolor)
                0x10 is backlight on (white)
        Byte 7 is Parking Brake On (0x80/0xC0) or Off (0x00)
        Byte 8 deals with the doors
            First digit 0, 1, 2, 3 is Closed, Passenger Ajar, Driver Ajar, Both Ajar respectively.
            Second Digit is 2 for closed or A for Hood Ajar
            02 - All Closed, 32 - Driver/Pass Door Open, 2A - Driver + Hood Doors Open
    '''
    # forza provides a value 0 - 255 for handbrake. If it's a button it will just be 0 - off and 255 - on
    # if you have a gaming sim hand brake, it could be a range
    if(int(forza_data['HandBrake'])>0):
        parking_brake_light = 0xC0 # on
    else:
        parking_brake_light = 0x00 # off
    data = [0x40, 0x48, 0x02, 0x0a, 0x18, 0x05, parking_brake_light, 0x02]
    return send_msg(DOOR_STATUS, start, data)

def send_rpm(forza_data):
    '''
    Gauge goes from 0 to 4000. Seems to be 1/2 of the actual RPM
    If RPM is 5000, the int that is passed should be 2500
    '''
    gauge_max = 4000
    if ('CurrentEngineRpm' in forza_data):
        # some cars can have larger or smaller max RPM. We need to get it to be the equivalent of the max 4k (half the 8k gauge)
        try:
            rpm = (gauge_max * int(forza_data['CurrentEngineRpm']))/forza_data['EngineMaxRpm']
        except:
            rpm = 0 # if the game is paused, these values will be 0 and cause a ZeroDivisionError
    else:
        rpm =  0 # in MPH
    rpm_hex = bytearray(int(rpm).to_bytes(2, 'big'))
    #print("    RPM: {}  HEX: {}; 1: {} 2:{}".format(rpm*2, rpm_hex, rpm_hex[0], rpm_hex[1]))

    #data = [0xC1, 0x5F, 0x7D, rpm_hex[0], rpm_hex[1], 0x00, 0x00, 0x00]
    data = [0xC0, 0x69, 0x7D, rpm_hex[0], rpm_hex[1], 0x00, 0x00, 0x00]
    return send_msg(RPM, start, data)

def send_speed(forza_data):
    '''
    Byte 4 must have a first digit of 6 or the gauge does not work
    Bytes 6 & 7 are the speed gauge 
    '''
    if ('Speed' in forza_data):
        speed = forza_data['Speed'] * 2
    else:
        speed =  0 # in MPH
    gauge_pos = int(speed) * 158
    speed_hex = bytearray((gauge_pos).to_bytes(2, 'big'))
    #print("    speed: {}  HEX: {}; 1: {} 2:{}".format(speed, speed_hex, speed_hex[0], speed_hex[1]))

    data = [0x00, 0x00, 0x00, 0x00, 0x60, 0x00, speed_hex[0], speed_hex[1]]
    return send_msg(SPEED, start, data)


def send_odometer(forza_data):
    data = [0x37, 0x00, 0x64, 0x26, 0xC0, 0x7A, 0x37, 0x1C]
    return send_msg(ODOMETER, start, data)

def send_engine_temp(forza_data):
    '''
    Bytes 0 & 1 are the range for the engine gauge
    0x9_ 0x9_ is the first half of the gauge
    0xc_ 0xc_ is the second half of the gauge
    0xb_ 0xb_ triggers an overheat warning
    '''
    data = [0x9E, 0x99, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00]
    return send_msg(ENGINE_TEMP, start, data)



THREADS = [
    (SPEED_ONE, [send_rpm, send_door_status, send_speed]),
    (SPEED_TWO, [send_warnings_1]),
    (SPEED_THREE, [send_misc_1, send_misc_10, send_launch_control, send_engine_temp]),
    (SPEED_SIX, [send_seatbelt_icon, send_misc_2]),
]


# setup the thread loop
def _thread(t, forza_data):
        for m in t[1]:
            m(forza_data)
            print(" - " + '{0:.2f}'.format(t[0]) + ' - ' + m.__name__)
        #time.sleep(t[0])


def create_threads(result):
    for speed in THREADS:
        if (speed[1] !=None):
            Process(target=_thread, args=(speed, result)).run()

def main():
    while(True):
        create_threads(forza.fetch_forza_data())


if __name__ == "__main__":
    main()