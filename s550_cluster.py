import can
import time
from multiprocessing.pool import ThreadPool as Pool
from pynput import keyboard
import sys

can_adapter_channel = 'COM3'
retry_period = 3 # seconds

pool_size = 8
# start time for timestamps
start = time.time()
# different messages have different polling intervals
# this can be determined by taking one of the converted logs and doing a pivot on id, count(id). Sort by count(id). Notice the groupings of messages
# the higher the speed, the more common it is / the more times that ID is visible in CAN traffic

# this will easily speed up or slow down the traffic while still keeping the speeds at the same interval
# < 1 speeds up; > 1 slows down
modifier =  .1
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
BUTTONS = 0x81
TIRE_PRESSURE = 0x3B5 # thanks to v-ivanyshyn's work
STEERING = 0x76
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
MISC_11 = 0x77
MISC_12 = 0x82 # thanks to v-ivanyshyn's work
MISC_13 = 0x230
# these 5 are odd ones. The first byte is always the digits that come after the 0x5--
# the rest of the bytes are 00 FF FF FF FF FF FF.
x5xx_SERIES_1 = 0x581
x5xx_SERIES_2 = 0x596
x5xx_SERIES_3 = 0x59E
x5xx_SERIES_4 = 0x5B3
x5xx_SERIES_5 = 0x5B5
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


def send_seatbelt_icon(clusterdata):
    '''
        Byte 0 - 
            0x0_ - Airbag Indicator Off
            0x4_ - Airbag Indicator On
            0x8_ - Airbag Indicator Flashing
        Byte 1 - Seatbelt: 
            0xAF both seltbeats undone
            0x5F pass / driver seatbelts on
            0x6F driver only seatbelt on
            0x9F pass only seatbelt on
    '''
    if(clusterdata.icon_seatbelt == 0):
        seatbelt = 0x5F
    else:
        seatbelt = 0xAF
    data = [0x10, seatbelt, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00]
    return send_msg(SEATBELT, start, data)

def send_misc_1(clusterdata):
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
        Byte 3  - Parking Brake On Warning / Brake Fluid Level Low warning
        Byte 6  
            0x00 -> ? 
            0x80 -> ?
    '''
    if(clusterdata.icon_high_beams == 0):
        high_beams = 0x4C # off 
    else:
        high_beams = 0x4E # on
    if(clusterdata.icon_parking_brake == 0):
        parking_brake_light = 0x00 # off
    else:
        parking_brake_light = 0x10 # on
    
    data =  [high_beams, 0x48, parking_brake_light, 0x01, 0x00, 0x00, 0x00, 0x00]
    return send_msg(MISC_1, start, data)

def send_misc_2(clusterdata):
    '''
        ABS, Traction Control Off, Traction Control Loss Icons, Airbag
        
        Byte 1 - 
            0x2_ - Check Brake System warning
            0x4_  - AdvanceTrac System Warning
        Byte 5 has to do with a solid traction control or a flashing icon
            0x00 - Off
            0x02 - Solid
            0x0F - Flashing
            0x80 - TC Off Indicator
            0x18 - ATC Off Indicator
        Byte 6 -
            0x0_ - ABS light off
            0x4_ - ABS Solid
            0x8_ - ABS Flash Slow
            0xD_ - ABS Flash Fast
    '''
    if(clusterdata.icon_traction_control == 2):
        traction_control = 0x0F # flashing
    elif(clusterdata.icon_traction_control == 1):
        traction_control = 0x02 # solid on
    else:
        traction_control = 0x80 # off

    if(clusterdata.icon_abs == 2):
        abs_icon = 0xD0 # flashing
    elif(clusterdata.icon_abs == 1):
        abs_icon = 0x40 # solid on
    else:
        abs_icon = 0x00 # off

    
    data =  [00, 00, 00, 00, 00, traction_control, abs_icon, 00]
    return send_msg(MISC_2, start, data)

def send_misc_3(clusterdata):
    data = [0x1A, 0x58, 0x1A, 0x58, 0x1A, 0x84, 0x1A, 0x74]
    return send_msg(MISC_3, start, data)

def send_misc_4(clusterdata):
    data = [0x7C, 0xFF, 0x80, 0x00, 0x7A, 0x40, 0x7C, 0xEA]
    return send_msg(MISC_4, start, data)

def send_misc_5(clusterdata):
    data = [0x7E, 0xE3, 0x7F, 0x39, 0x3D, 0x93, 0xF0, 0x00]
    return send_msg(MISC_5, start, data)

def send_misc_6(clusterdata):
    data = [0x6F, 0xBA, 0x6F, 0x92, 0x73, 0x62, 0x94, 0x93]
    return send_msg(MISC_6, start, data)

def send_misc_7(clusterdata):
    data = [0x00, 0x00, 0x80, 0x47, 0x80, 0x47, 0x00, 0x00]
    return send_msg(MISC_7, start, data)

def send_misc_8(clusterdata):
    '''
    Byte 1 & 2
        Frist Byte is 0x7F, can increase to 0x80
        First Bit: 3, 4, F
    
    Byte 5 & 6: ??? Gauge related? Seems to have increased and decreased when driving
        First Byte is 0x19 - 0x1A
        First Bit: 1
        Second Bit : 9, A
        Third Bit: 0 - F
    '''
    data = [0x72, 0x7F, 0x4B, 0x00, 0x00, 0x1A, 0xED, 0x00]
    return send_msg(MISC_8, start, data)

def send_misc_9(clusterdata):
    '''
    
    '''
    data = [00, 0x00, 0xD0, 0xFA, 0x0F, 0xFE, 0x0F, 0xFE]
    return send_msg(MISC_9, start, data)

def send_misc_10(clusterdata):
    '''
    
    '''
    data = [0x82, 0x00, 0x14, 0x40, 0x7B, 0x00, 0x64, 0xFF]
    return send_msg(MISC_10, start, data)

def send_misc_11(clusterdata):
    '''
        Byte 6 - Hill Start Assist Not Available Warning
            0x_c - displays warning
            0x_6 - shuts warning up
    '''
    data = [0x00, 0x00, 0x07, 0xFF, 0x7F, 0xF7, 0xE6, 0x02]
    return send_msg(MISC_11, start, data)

# 4 Feb 2024
def send_misc_12(clusterdata):
    '''
        Byte 2 & 3 - Fuel Consumption ?? 
        Byte 6 - Steering Mode
            0x40 - Normal
            0x44 - Sport
            0x48 - Comfort
    '''
    data = [0x5C, 0x00, 0x14, 0x98, 0xAF, 0x00, 0x44, 0xFF]
    return send_msg(MISC_12, start, data)

def send_misc_13(clusterdata):
    '''
        Byte 0 & 1 ??
    '''
    data = [0xF0, 0x1C, 0x00, 0x00, 0x4B, 0x00, 0x00, 0x00]
    return send_msg(MISC_12, start, data)

def send_0x5__series(clusterdata):
    # not sure what these do but since they seem to be hard coded, gonna send them
    send_msg(x5xx_SERIES_1, start, [0x81, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    print('')
    send_msg(x5xx_SERIES_2, start, [0x96, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    print('')
    send_msg(x5xx_SERIES_3, start, [0x9E, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    print('')
    send_msg(x5xx_SERIES_4, start, [0xB3, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    print('')
    return send_msg(x5xx_SERIES_5, start, [0xB5, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])

def send_warnings_1(clusterdata):
    '''
        Several Warning messages such as fuel service inlet, change oil soon, oil change required
    '''
    data = [0x00, 0x00, 0x00, 0x00, 0x96, 0x00, 0x02, 0xC8]
    return send_msg(WARNINGS_1, start, data)

def send_launch_control(clusterdata):
    '''
    Byte 0 
        0x2_ - LC Icon
        0x8_ - RPM Icon, LC Fault
        0xa_ - LC Flashing Icon
    '''
    if(clusterdata.icon_launch_control == 2):
        launch_control = 0xA0 # flashing
    elif(clusterdata.icon_launch_control == 1):
        launch_control = 0x20 # solid on
    else:
        launch_control = 0x00 # off
    data = [launch_control, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
    return send_msg(LC, start, data)

def send_door_status(clusterdata):
    '''
        Byte 0 & 1 have to do with if the IPC is on
                40 48 is running, doors closed, lights off
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
    if(clusterdata.icon_parking_brake == 0):
        parking_brake_light = 0x00 # off
    else:
        parking_brake_light = 0xC0 # on

    if(clusterdata.engine_on == 1):
        lights = 0x0A
    else:
        lights = 0x00
    data = [0x40, 0x48, 0x02, lights, 0x18, 0x05, parking_brake_light, 0x02]
    return send_msg(DOOR_STATUS, start, data)

def send_rpm(clusterdata):
    '''
    Gauge goes from 0 to 4000. Seems to be 1/2 of the actual RPM
    If RPM is 5000, the int that is passed should be 2500
    '''
    gauge_max = 4000

    try:
        rpm = (gauge_max * int(clusterdata.value_rpm))/clusterdata.value_rpm_max
    except:
        rpm = 0 # if the game is paused, these values will be 0 and cause a ZeroDivisionError

    rpm_hex = bytearray(int(rpm).to_bytes(2, 'big'))

    #data = [0xC1, 0x5F, 0x7D, rpm_hex[0], rpm_hex[1], 0x00, 0x00, 0x00]
    data = [0xC0, 0x69, 0x7D, rpm_hex[0], rpm_hex[1], 0x00, 0x00, 0x00]
    return send_msg(RPM, start, data)

def send_speed(clusterdata):
    '''
    Byte 4 must have a first digit of 6 or the gauge does not work
    Bytes 6 & 7 are the speed gauge 
    '''
    speed = clusterdata.value_speed
    gauge_pos = int(speed) * 175
    speed_hex = bytearray((gauge_pos).to_bytes(2, 'big'))
    #print("    speed: {}  HEX: {}; 1: {} 2:{}".format(speed, speed_hex, speed_hex[0], speed_hex[1]))

    data = [0x00, 0x00, 0x00, 0x00, 0x60, 0x00, speed_hex[0], speed_hex[1]]
    return send_msg(SPEED, start, data)


def send_odometer(clusterdata):
    odometer = bytearray((clusterdata.value_odometer).to_bytes(3, 'big'))
    data = [0x37, odometer[0], odometer[1], odometer[2], 0xC0, 0x7A, 0x37, 0x1C]
    return send_msg(ODOMETER, start, data)

def send_engine_temp(clusterdata):
    '''
    Bytes 0 & 1 are the range for the engine gauge
    0x9_ 0x9_ is the first half of the gauge
    0xc_ 0xc_ is the second half of the gauge
    0xb_ 0xb_ triggers an overheat warning
    '''
    data = [0x9E, 0x99, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00]
    return send_msg(ENGINE_TEMP, start, data)

# 4 Feb 2024
def send_tire_pressure(clusterdata):
    '''
        In kPa 
        Byte 1 - Front Left Tire Pressure
        Byte 3 - Front Right Tire Pressure
        Byte 5 - Rear Right Tire Pressure
        Byte 7 - Rear Left Tire Pressure
    '''

    tire_pressure_dummy = 0xCE # 30 PSI  / 206 kPa

    data = [0x00, tire_pressure_dummy, 0x00, tire_pressure_dummy, 0x00, tire_pressure_dummy, 0x00, tire_pressure_dummy]
    return send_msg(TIRE_PRESSURE, start, data)

# 4 Feb 2024
def send_steering(clusterdata):
    '''
        Byte 0 & 1 control steering angle, -0.1 - 1.0 +  1600
    '''

    data = [0x3E, 0x83, 0xC0, 0x00, 0x00, 0x00, 0x00, 0x00]
    return send_msg(STEERING, start, data)

def MENU_NAV(direction):
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
    else:
        data[0] = 0x00
    
    return send_msg(BUTTONS, start, data) 

def on_press(key):
    try:
        k = key.char  # single-char keys
    except:
        k = key.name  # other keys
    if k in ['up', 'down', 'left', 'right', 'enter']:  # keys of interest
        # self.keys.append(k)  # store it in global-like variable
        #print('Key pressed: ' + k)
        MENU_NAV(k)
        print(" - " + 'KEY PRESSED: {} '.format(k) + ' - MENU_NAV')
        #return k  # stop listener; remove this if want more keys

def keys():
    listener = keyboard.Listener(on_press=on_press)
    listener.start()  # start to listen on a separate thread
    #listener.join()

THREADS = [
    (SPEED_ONE, [send_rpm, send_door_status, send_speed]),
    (SPEED_TWO, [send_warnings_1]),
    (SPEED_THREE, [send_misc_1, send_misc_10, send_launch_control, send_engine_temp, send_tire_pressure]),
    (SPEED_SIX, [send_seatbelt_icon, send_misc_2, send_misc_12, send_steering, send_misc_13]),
    (SPEED_SEVEN, [MENU_NAV, send_0x5__series])
]

def load_game(game):
    supported_games = ['fh5', 'ats']
    if(game in supported_games):
        #print('Loading {}'.format(game))
        if game == 'fh5':
            import games.fh5
            return games.fh5.data()
        elif game == 'ats':
            import games.ats
            time.sleep(0.1) # trying to poll the API endpoint too much causes it to fail
            return games.ats.data()
    else:
        pass

# setup the thread loop
def _thread(t, game):
    while True:
        for m in t[1]:
            m(load_game(game))
            print(" - " + '{0:.2f}'.format(t[0]) + ' - ' + m.__name__)
        #time.sleep(t[0])


def activate(game=None):
    if(game==None):
        try:
            game = sys.argv[1]
        except:
            game = 'fh5' # default to fh5 if no param is passed
    print('* Loading game: {}'.format(game))
    pool = Pool()
    print('* Starting thread for keyboard navigation')
    pool.apply_async(keys) # send whatever key is pressed to send to the cluster
    # create a thread for each speed
    for speed in THREADS:
        print('* Starting thread for speed: {}, functions: {}'.format(speed[0], [m.__name__ for m in speed[1]]))
        pool.apply_async(_thread, args=(speed,game), error_callback=print)
    pool.close()
    pool.join()



if __name__ == "__main__":
    activate()