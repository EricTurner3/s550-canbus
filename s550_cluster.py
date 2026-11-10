import can
import atexit
import time
import heapq
import threading
from collections import Counter
from pynput import keyboard
import sys
import s550_data
import games.fh5
import games.ats

can_adapter_channel = 'COM3'
retry_period = 3 # seconds

# print every frame sent. Console printing is slow on Windows and will throttle the bus, leave off unless debugging
verbose = False

# start time for timestamps
start = time.time()
# different messages have different polling intervals
# this can be determined by taking one of the converted logs and doing a pivot on id, count(id). Sort by count(id). Notice the groupings of messages
# the higher the speed, the more common it is / the more times that ID is visible in CAN traffic
# 6 Nov 2026 - periods below are measured from the GT350 logs in /can (count of each ID / log duration)

# this will easily speed up or slow down the traffic while still keeping the speeds at the same interval
# < 1 speeds up; > 1 slows down
modifier = 1
SPEED_ONE = 0.01 * modifier     # 100 Hz - 0x204, 0x167, 0x217, 0x85, 0x91, 0x92 (accelerometer)
SPEED_TWO = 0.02 * modifier     # 50 Hz  - 0x202, 0x200, 0x415, 0x77, 0x76 (steering / g meter), 0x82, 0x230
SPEED_THREE = 0.1 * modifier    # 10 Hz  - 0x4C, 0x83, 0x178, 0x416, 0x430
SPEED_FOUR = 0.4 * modifier     # 2.5 Hz - 0x3B3, 0x3B2
SPEED_FIVE = 1.0 * modifier     # 1 Hz   - 0x81, 0x3C3, 0x431, 0x5xx series

#CAN IDs
RPM = 0x204
SPEED = 0x202
DOOR_STATUS = 0x3B3
TRACK_APPS = 0x3B2 # same layout as 0x3B3, from another project's 2016 Mustang. Not in our logs
SEATBELT = 0x4C
ODOMETER = 0x430
BUTTONS = 0x81
TIRE_PRESSURE = 0x3B5 # thanks to v-ivanyshyn's work
CLIMATE_CONTROL = 0x326
CLIMATE_FAN = 0x35E
STEERING = 0x76
MISC_1 = 0x3C3
MISC_2 = 0x416
MISC_3 = 0x217
MISC_4 = 0x85
MISC_5 = 0x91
ACCELEROMETER = 0x92
MISC_7 = 0x200
MISC_8 = 0x167
MISC_9 = 0x415
MISC_10 = 0x130
MISC_11 = 0x77
MISC_12 = 0x82 # thanks to v-ivanyshyn's work
MISC_13 = 0x230
STEERING_PINION = 0x7E # Ford DBC SteeringPinion_Data, same layout as 0x85. Not in any 2015 - 2017 capture
STEERING_ANGLE_2 = 0x3A8 # second copy of the 0x85 angle, v-ivanyshyn's GT log only
APIM_1 = 0x044 # https://github.com/EtoTen/stm32_can_sim/blob/main/src/main.cpp
APIM_2 = 0x048
APIM_3 = 0x109
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
ENGINE_STATUS = 0x421 # from v-ivanyshyn's GT log, the GT350 never sent these three
INTAKE_TEMP = 0x42D
ENGINE_GAUGES = 0x43E
# 8 Nov 2026 - found with ipc_dtc_test.py / interactive_brute_force.py, see database.md
TPMS_STATUS = 0x3B4
TRANS_WARNINGS = 0x431
OCCUPANT = 0x42C # sending it at all also stops the cluster's U0100 (lost comm with the PCM)
KEY_MESSAGES = 0x38D
BLIND_SPOT_L = 0x3A6 # Ford DBC Side_Detect_L / _R, stop U0232 / U0233 and the blind spot / cross traffic warnings
BLIND_SPOT_R = 0x3A7


# Stock slcan firmware on Windows
def open_bus(attempts=10, wait=1.0):
    '''
        8 Nov 2026 - Windows can hold the COM port for a few seconds after the last script exits ("Access is denied"),
        so keep trying instead of crashing out
    '''
    for attempt in range(1, attempts + 1):
        try:
            return can.ThreadSafeBus(interface='slcan', channel=can_adapter_channel, bitrate=500000)
        except can.CanInitializationError as e:
            if attempt == attempts:
                raise
            print('* {} busy ({}), retrying {}/{}'.format(can_adapter_channel, e, attempt, attempts - 1))
            time.sleep(wait)

bus = open_bus()
# close the port on exit so the next run can open it right away
atexit.register(bus.shutdown)


# frames sent / failed since the last status line
sent_count = Counter()
fail_count = Counter()

def send_msg(id, ts, data):
    try:
        msg = can.Message(timestamp = time.time() - ts, arbitration_id=id,
                    data=data,
                    is_extended_id=False)
        bus.send(msg)
        sent_count[id] += 1
        if (verbose):
            print(msg)
    except can.CanError:
        fail_count[id] += 1
        print("   {} - Message NOT sent".format(str(hex(id))))

def clamp(value, low, high):
    # game values can go past what the bytes hold (or what the gauge shows), keep them in range
    return max(low, min(high, int(round(value))))


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
        traction_control = 0x00 # off

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

# steering angle, 0.1 deg per bit, 0x7D00 = center. 0x7CFF is the parked GT350 (run_*.csv)
STEERING_ANGLE = 0x7CFF
pinion_counters = {}

def pinion_frame(id):
    '''
        0x85 / 0x7E SteeringPinion_Data, checked against every frame in the GT350 logs and v-ivanyshyn's GT log
            Bytes 0 & 1 - steering angle (STEERING_ANGLE)
            Byte 2 bit 7 - steering power request, 1 running
            Byte 4 - checksum, 0xFF - (b0 + b1 + counter + b6 + b7)
            Byte 5 - bits 7 - 4 counter, +1 every frame
            Bytes 6 & 7 - learned steering center, same scale as the angle. FF FE until the car has driven a bit,
                          0x7CEA on the GT350, 0x7C7F on v-ivanyshyn's GT
        Each ID keeps its own counter
    '''
    cnt = pinion_counters[id] = (pinion_counters.get(id, -1) + 1) & 0x0F
    data = [STEERING_ANGLE >> 8, STEERING_ANGLE & 0xFF, 0x80, 0x00, 0x00, cnt << 4, 0x7C, 0xEA]
    data[4] = (0xFF - (data[0] + data[1] + cnt + data[6] + data[7])) & 0xFF
    return data

def send_misc_4(clusterdata):
    return send_msg(MISC_4, start, pinion_frame(MISC_4))

def send_steering_pinion(clusterdata):
    return send_msg(STEERING_PINION, start, pinion_frame(STEERING_PINION))

def send_steering_angle_2(clusterdata):
    '''
        0x3A8, bytes 2 & 3 = the 0x85 angle - 21873 (center ~0x278F), no counter or checksum, the rest 00. 20 ms
    '''
    raw = STEERING_ANGLE - 21873
    return send_msg(STEERING_ANGLE_2, start, [0x00, 0x00, raw >> 8, raw & 0xFF, 0x00, 0x00, 0x00, 0x00])

def send_misc_5(clusterdata):
    data = [0x7E, 0xE3, 0x7F, 0x39, 0x3D, 0x93, 0xF0, 0x00]
    return send_msg(MISC_5, start, data)

accelerometer_counter = 0

def send_accelerometer(clusterdata):
    '''
        0x92, accelerometer. Checked against every GT350 log and v-ivanyshyn's GT log. Doesn't move the Track Apps
        g meter dot on the bench, that's 0x76 (send_steering)
        Three 13 bit values, raw = (m/s^2 + 40) * 100, top 3 bits 0b011 (0x6_) when valid
            Bytes 0 & 1 - lateral
            Bytes 2 & 3 - longitudinal, positive speeding up
            Bytes 4 & 5 - vertical, ~9.7 at rest
        Byte 7 - counter, +5 every frame
        Byte 6 - checksum, all 8 bytes add up to 0x16
        100 Hz in the GT350
    '''
    global accelerometer_counter
    accelerometer_counter = (accelerometer_counter + 5) & 0xFF
    data = []
    for value in (clusterdata.accel_lateral, clusterdata.accel_longitudinal, clusterdata.accel_vertical):
        raw = clamp((value + 40) * 100, 0, 0x1FFF)
        data += [0x60 | raw >> 8, raw & 0xFF]
    data += [0x00, accelerometer_counter]
    data[6] = (0x16 - sum(data)) & 0xFF
    return send_msg(ACCELEROMETER, start, data)

def send_misc_7(clusterdata):
    data = [0x00, 0x00, 0x80, 0x47, 0x80, 0x47, 0x00, 0x00]
    return send_msg(MISC_7, start, data)

def send_misc_8(clusterdata):
    '''
    CAN ID: 0x167
    Byte 0 & 1
        Frist Byte is 0x7F, can increase to 0x80
        First Bit: 3, 4, F
    
    Byte 5 & 6: 5 Feb 24, Possibly the MAF sensor which can be used for boost/vacuum
    ??? Gauge related? Seems to have increased and decreased when driving
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
        EPAS_INFO from the power steering module, see database.md (8 Nov 2026, Ford DBC layout)
        Byte 0 - Steering column torque, 0x80 = 0 Nm (GT350 driving 0x83)
        Byte 2 & 3 - Motor current (was thought to be fuel consumption), byte 4 module voltage (0xAF ~14.7 V)
        Byte 6 - bits 7 - 5 module state (2 assisting), bits 3 - 2 Steering Mode
            0x40 - Normal
            0x44 - Sport
            0x48 - Comfort
    '''
    data = [0x83, 0x00, 0x14, 0x34, 0xAF, 0x00, 0x44, 0xFF]
    return send_msg(MISC_12, start, data)

def send_misc_13(clusterdata):
    '''
        Byte 0 & 1 ??
    '''
    data = [0xF0, 0x1C, 0x00, 0x00, 0x4B, 0x00, 0x00, 0x00]
    return send_msg(MISC_13, start, data)

# 10 Feb 2024 - trying to get the APIM to boot, might require this
def send_climate(clusterdata):
    data = [0x81, 0x95, 0x02, 0x4A, 0x01, 0xAA, 0x00, 0x00]
    return send_msg(CLIMATE_CONTROL, start, data)

def send_climate_fan(clusterdata):
    data = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x30, 0x00]
    return send_msg(CLIMATE_FAN, start, data)

def send_apim_1(clusterdata):
    data = [0x88, 0xC0, 0x0C, 0x10, 0x04, 0x00, 0x02, 0x00]
    return send_msg(APIM_1, start, data)

def send_apim_2(clusterdata):
    data = [0x00, 0x00, 0x00, 0x00, 0x07, 0x00, 0xE0, 0x00]
    return send_msg(APIM_2, start, data)

def send_apim_3(clusterdata):
    data = [0x00, 0x03, 0x01, 0x00, 0x00, 0x00, 0x00, 0x28]
    return send_msg(APIM_3, start, data)

def send_0x5__series(clusterdata):
    # not sure what these do but since they seem to be hard coded, gonna send them
    send_msg(x5xx_SERIES_1, start, [0x81, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    send_msg(x5xx_SERIES_2, start, [0x96, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    send_msg(x5xx_SERIES_3, start, [0x9E, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    send_msg(x5xx_SERIES_4, start, [0xB3, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    return send_msg(x5xx_SERIES_5, start, [0xB5, 00, 0xFF,0xFF, 0xFF, 0xFF, 0xFF, 0xFF])

ODOMETER_COUNTS_PER_MILE = 8767 # 0x179 byte 5, measured from v-ivanyshyn's GT log
odometer_counts = 0.0
odometer_time = None

def send_warnings_1(clusterdata):
    '''
        Several Warning messages such as fuel service inlet, change oil soon, oil change required
        7 Nov 2026 - Byte 5 is a rolling distance counter (8 bit, ~8767 per mile). The odometer counts up from it
        and the cluster saves it, so game miles are added for good. Advanced here from the speed shown on the cluster
        Bytes 6 & 7 are a second counter (wraps at 3000) that runs at idle and with load, likely fuel used. Left static
    '''
    global odometer_counts, odometer_time
    now = time.perf_counter()
    if odometer_time is not None:
        odometer_counts += clusterdata.value_speed * (now - odometer_time) / 3600 * ODOMETER_COUNTS_PER_MILE
    odometer_time = now
    data = [0x00, 0x00, 0x00, 0x00, 0x96, int(odometer_counts) % 256, 0x02, 0xC8]
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
    # byte 4 0x10 like the car logs, the turn signals are sent on 0x3B2 (send_track_apps)
    data = [0x40, 0x48, 0x02, lights, 0x10, 0x05, parking_brake_light, 0x02]
    return send_msg(DOOR_STATUS, start, data)

def send_track_apps(clusterdata):
    '''
        Same layout as 0x3B3. Sent alongside 0x3B3, it makes Track Apps show on a 2015 FR33 cluster. From another
        project's firmware (mustang.c, built on a 2016 Mustang), byte 4 bit 0x10 is Track Apps there
        Byte 0 0x4_ as in 0x3B3, 0x41 shows Trunk Ajar. The cluster stays on from 0x3B3 whatever byte 0 is
        Byte 4 bit 0x08 - right turn signal (confirmed). Byte 6 bit 0x40 - left turn signal (from mustang.c)
        icon_left_signal / icon_right_signal 2 flashes, on and off for one send each (0.4s)
    '''
    lit = int((time.time() - start) / SPEED_FOUR) % 2 == 0
    right = 0x08 if clusterdata.icon_right_signal == 1 or (clusterdata.icon_right_signal == 2 and lit) else 0x00
    left = 0x40 if clusterdata.icon_left_signal == 1 or (clusterdata.icon_left_signal == 2 and lit) else 0x00
    data = [0x40, 0x00, 0x00, 0x12, 0x10 | right, 0x00, left, 0x02]
    return send_msg(TRACK_APPS, start, data)

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
    Byte 4 must have a first digit of C or the gauge does not work
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

# 16 Jan 2025
def send_engine_temp(clusterdata):
    '''
    Byte 0 is for the Engine/Coolant Temp Gauge (seen on analog cluster under RPM)
        Temp is in Celsius, int(byte0) - 60 = Temp, thus A0 would be 100c or 212f
        Gauge doesn't start to move until around 0x80
        Gauge seems to have a safe zone and 'freezes' from around 0xA6 (106c) to 0xC0 (132c) where it then rapidly ramps up and can trigger overheat warning
    Byte 1 is for the Oil Temp Gauge (seen under center screen, Gauge Mode > Oil Temp)
        Temp is in Celsius, int(byte0) - 60 = Temp
        Gauge starts to move at 0x60  (36c) and caps out around 0xDA (158c)
    Byte 4 toggles the engine overheat message and maxes engine temp guage  (doesn't seem to be necessary as a high byte 0 will also trigger the warning)
        0x03 - normal
        0x08 - overheat
    '''
    oil_temp = clamp(clusterdata.oil_temp + 60, 0x00, 0xFF)
    engine_temp = clamp(clusterdata.engine_temp + 60, 0x00, 0xFF)
    data = [engine_temp, oil_temp, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00]
    return send_msg(ENGINE_TEMP, start, data)

# 7 Nov 2026
def send_engine_status(clusterdata):
    '''
    Oil Pressure Status, Check Engine Light, Engine Shutdown Messages
    The GT has an oil pressure switch, Gauge Mode > Oil Pressure shows Normal while this is sent and Low (with a warning) without it
    Byte 0 - Check Engine Light
        0x04 - Solid
        0x08 - Flashing
    Byte 1 - Engine shutdown messages
        0x01 - "Engine shutoff in 30s"
        0x02 - "Engine has shut off for fuel economy"
    Bytes 2 & 6 change in the GT log, no visible effect
    '''
    if(clusterdata.icon_check_engine == 2):
        check_engine = 0x08 # flashing
    elif(clusterdata.icon_check_engine == 1):
        check_engine = 0x04 # solid on
    else:
        check_engine = 0x00 # off
    data = [check_engine, 0x00, 0x50, 0x00, 0x00, 0x00, 0x4D, 0x00]
    return send_msg(ENGINE_STATUS, start, data)

# 7 Nov 2026
def send_intake_temp(clusterdata):
    '''
    Bytes 1 & 2 - Inlet Air Temp (Gauge Mode)
        10 bit (byte 1 & 0x03), raw * 0.25 - 128 = Celsius
        Radial gauge is 0f - 240f, the text readout shows negatives
    '''
    intake_temp = clamp((clusterdata.intake_temp + 128) * 4, 0x000, 0x3FF)
    data = [0x00, intake_temp >> 8, intake_temp & 0xFF, 0x00, 0x00, 0x00, 0xF0, 0x00]
    return send_msg(INTAKE_TEMP, start, data)

# 7 Nov 2026
def send_engine_gauges(clusterdata):
    '''
    Without this ID the AFR, Boost / Vacuum, Cylinder Head Temp and Inlet Air Temp gauges are blank
    Byte 1 - 0x93, 14.7 stoichiometric AFR
    Byte 3 - Air Fuel Ratio, raw / 10
    Byte 4 - Cylinder Head Temp, raw - 60 = Celsius. Gauge is 140f - 340f
    Bytes 5 & 6 - Boost / Vacuum, 13 bit (raw >> 3), value * 0.1 - 206.9 = kPa. Negative is vacuum
        Gauge is 30 inHg vacuum to 20 psi boost
    '''
    afr = clamp(clusterdata.value_afr * 10, 0x00, 0xFF)
    cylinder_head_temp = clamp(clusterdata.cylinder_head_temp + 60, 0x00, 0xFF)
    boost_kpa = clusterdata.value_boost * 6.895
    boost = clamp((boost_kpa + 206.9) * 10, 0x0000, 0x1FFF) << 3
    data = [0x00, 0x93, 0x10, afr, cylinder_head_temp, boost >> 8, boost & 0xFF, 0x00]
    return send_msg(ENGINE_GAUGES, start, data)

# 4 Feb 2024
def send_tire_pressure(clusterdata):
    '''
        16 bit kPa per tire (0x00CE = 206 kPa = 30 psi on the cluster)
        Bytes 0 & 1 - Front Left Tire Pressure
        Bytes 2 & 3 - Front Right Tire Pressure
        Bytes 4 & 5 - Rear Right Tire Pressure
        Bytes 6 & 7 - Rear Left Tire Pressure
    '''
    data = []
    for psi in (clusterdata.tire_pressure_fl, clusterdata.tire_pressure_fr,
                clusterdata.tire_pressure_rr, clusterdata.tire_pressure_rl):
        kpa = clamp(psi * 6.895, 0, 0xFFFF)
        data += [kpa >> 8, kpa & 0xFF]
    return send_msg(TIRE_PRESSURE, start, data)

# 4 Feb 2024
def send_steering(clusterdata):
    '''
        Byte 0 & 1 control steering angle, -0.1 - 1.0 +  1600. 0x3E80 is the most common value in the logs
        Bytes 2 - 4, Track Apps g meter. From another project's firmware (mustang.c, send_accelerometer), in g, +-1.5:
            Byte 2       - 16 + x * 8
            Bytes 3 & 4  - 1024 + y * 512
        Confirmed: x = lateral (+ right, 0x1C full right), y = longitudinal (+ accel, 0x0700 full accel / 0x0100 full brake)
        Every 2015 - 2017 log has C0 00 80 here, which is far off that scale
        (the old fixed frame 3E 83 C0 00 00 pinned the dot in the top left corner)
    '''
    x = max(-1.5, min(1.5, clusterdata.accel_lateral / 9.81))
    y = max(-1.5, min(1.5, clusterdata.accel_longitudinal / 9.81))
    g_y = 1024 + int(y * 512)
    data = [0x3E, 0x80, 16 + int(x * 8), g_y >> 8, g_y & 0xFF, 0x00, 0x00, 0x00]
    return send_msg(STEERING, start, data)

# 8 Nov 2026
def send_tpms_status(clusterdata):
    '''
    Byte 0 - bits 7 - 4 system status, bits 3 - 2 lamp
        0x40 - no message, lamp off (freeze frame). Without 0x3B4 the lamp and a fault show
        0x34 - Tire Pressure Low window, lamp solid. Needed for the tire statuses to show
        0x28 - Tire Pressure Sensor Fault, lamp flashing (system 2 and lamp 2 were found separately)
    Bytes 1 & 2 - one status nibble per tire, LF b1 high, RF b1 low, RR b2 high, LR b2 low
        1 - ok, 2 (or 4) - highlights that tire. Several tires at once untested
    Byte 3 - inner rears (duallys), FF not fitted. Bytes 4 & 5 - 20 20 in the logs
    '''
    low = [clusterdata.warning_tire_low_fl, clusterdata.warning_tire_low_fr,
           clusterdata.warning_tire_low_rr, clusterdata.warning_tire_low_rl]
    fl, fr, rr, rl = (0x2 if tire else 0x1 for tire in low)
    if any(low):
        status = 0x34
    elif clusterdata.warning_tire_sensor_fault:
        status = 0x28
    else:
        status = 0x40
    data = [status, fl << 4 | fr, rr << 4 | rl, 0xFF, 0x20, 0x20, 0x00, 0x00]
    return send_msg(TPMS_STATUS, start, data)

# 8 Nov 2026 - each message's full frame as tested (one bit flipped from a logged frame), byte 3 looks like a
# message number. The first True in this order is sent
TRANS_FRAMES = [
    ('warning_trans_overheat',         [0x05, 0x1D, 0x40, 0xEB, 0x97, 0x83, 0x46, 0x00]),
    ('warning_trans_too_hot',          [0x05, 0x1D, 0x40, 0xEB, 0x37, 0x83, 0x46, 0x00]),
    ('warning_trans_malfunction',      [0x05, 0x1B, 0x40, 0x0C, 0x0F, 0x83, 0x42, 0x00]),
    ('warning_trans_service',          [0x05, 0x1B, 0x40, 0x14, 0x0F, 0x83, 0x42, 0x00]),
    ('warning_trans_adapt_mode',       [0x05, 0x1D, 0x40, 0xE3, 0xB7, 0x83, 0x46, 0x00]),
    ('warning_trans_indicator_lockup', [0x05, 0x1D, 0x40, 0xEF, 0xB7, 0x83, 0x46, 0x00]),
    ('warning_trans_warming_up',       [0x05, 0x1D, 0x40, 0xEB, 0xB7, 0x83, 0x46, 0x00]),
]
TRANS_NONE = [0x05, 0x1B, 0x40, 0x04, 0x0F, 0x83, 0x42, 0x00] # warm, longerdrive.csv

def send_trans_warnings(clusterdata):
    data = next((frame for name, frame in TRANS_FRAMES if getattr(clusterdata, name)), TRANS_NONE)
    return send_msg(TRANS_WARNINGS, start, data)

# 8 Nov 2026
def send_occupant(clusterdata):
    '''
    Byte 0 - bit 3 (0x08) Occupant Sensor Blocked with the passenger icon. 0x80 - 0x87 show nothing
        Every GT350 / freeze frame / GT log value has it set (8C), don't replay those
        Bits 7 - 5 cruise status per a 2018 GWM bench, untested here
    Bytes 1 - 5 - no visible effect, 9C 60 from the GT350 logs
    '''
    occupant = 0x88 if clusterdata.warning_occupant_sensor_pass else 0x80
    data = [occupant, 0x00, 0x00, 0x00, 0x9C, 0x60, 0x00, 0x00]
    return send_msg(OCCUPANT, start, data)

# 8 Nov 2026 - byte 4 high nibble (Ford DBC immoMsgTxt_D_Rq). The first True in this order is sent
KEY_MESSAGE_VALUES = [
    ('warning_key_starting_fault', 0x70),
    ('warning_key_not_detected', 0x30),
    ('warning_key_press_brake', 0x10),
    ('warning_key_press_clutch', 0xC0),
    ('warning_key_run_power_active', 0x60),
]

def send_key_messages(clusterdata):
    '''
    Byte 0 - 0x20, 2 admin keys in both logs
    Byte 4 - key / start message, 0x00 none. Also 0x80 Key Program Successful, 0x90 Key Program Failure,
        0xA0 Max Number of Keys, 0xB0 Not Enough Keys Learned
    Sending 0x38D at all shows Track Apps in the menu
    '''
    message = next((value for name, value in KEY_MESSAGE_VALUES if getattr(clusterdata, name)), 0x00)
    data = [0x20, 0x00, 0x00, 0x00, message, 0x00, 0x00, 0x00]
    return send_msg(KEY_MESSAGES, start, data)

# 8 Nov 2026
def send_blind_spot(clusterdata):
    '''
    Side detect left / right (Ford DBC), byte 1 bits 7 - 5 blind spot on (2), byte 2 bits 2 - 0 cross traffic on (2),
    sensors clear. Turns Blind Spot and Cross Traffic Alert on in Driver Assist (can't be turned off while sent)
    '''
    data = [0x00, 0x40, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00]
    send_msg(BLIND_SPOT_L, start, data)
    return send_msg(BLIND_SPOT_R, start, data)

# dummy data (interactive_brute_force.py --dummydata, ipc_dtc_test.py dummy): chassis messages from database.md with
# steady values, all speed signals built from value_speed so they agree (mismatched wheel speeds trip Hill Start Assist)
def send_wheel_speeds(clusterdata):
    '''
        0x217, four 13 bit wheel speeds (FL, FR, RL, RR), raw ~= MPH * 144, low 2 bits always 0
    '''
    raw = clamp(clusterdata.value_speed * 144, 0, 0x1FFF) & ~0x3
    return send_msg(0x217, start, [raw >> 8, raw & 0xFF] * 4)

def send_vehicle_speed_77(clusterdata):
    '''
        0x77, bytes 0 & 1 speed (14 bit, MPH * 175), bytes 2 & 3 lateral centered at 0x0800
        byte 6 0xE6 keeps Hill Start Assist Not Available off
    '''
    raw = clamp(clusterdata.value_speed * 175, 0, 0x3FFF)
    return send_msg(0x77, start, [raw >> 8, raw & 0xFF, 0x08, 0x00, 0x7F, 0xF7, 0xE6, 0x02])

def send_vehicle_speed_415(clusterdata):
    '''
        0x415, bytes 0 & 1 speed (14 bit, MPH * 175), bytes 4 - 7 yaw / lateral centered (GT log at rest 07 FD 07 FD)
    '''
    raw = clamp(clusterdata.value_speed * 175, 0, 0x3FFF)
    return send_msg(0x415, start, [raw >> 8, raw & 0xFF, 0xD0, 0xFA, 0x07, 0xFD, 0x07, 0xFD])

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

# every function in a group is sent once per period. IDs not seen in the GT350 logs (APIM, climate, 0x156, 0x179, 0x3B5) are at a best guess
SCHEDULE = [
    (SPEED_ONE, [send_rpm, send_misc_8, send_accelerometer]),
    (SPEED_TWO, [send_speed, send_steering]),
    (SPEED_THREE, [send_warnings_1, send_seatbelt_icon, send_misc_2, send_launch_control, send_engine_temp,
                   send_climate, send_climate_fan, send_apim_1, send_apim_2, send_apim_3,
                   send_engine_gauges, send_engine_status, send_occupant, send_blind_spot]),
    (SPEED_FOUR, [send_door_status, send_track_apps, send_intake_temp]),
    (SPEED_FIVE, [send_misc_1, send_tire_pressure, MENU_NAV, send_0x5__series,
                  send_tpms_status, send_trans_warnings, send_key_messages])
]

# added to SCHEDULE by --dummydata / dummy. The rest are this file's unscheduled senders
DUMMY_SCHEDULE = [
    (SPEED_ONE, [send_wheel_speeds, send_misc_4, send_misc_5]), # 0x217, 0x85 steering angle, 0x91 yaw
    (SPEED_TWO, [send_vehicle_speed_77, send_vehicle_speed_415, send_misc_7, send_misc_12,
                 send_misc_13]), # 0x200 torque, 0x82 steering mode, 0x230 gear
]

# power steering frames that go with 0x82 (interactive_brute_force.py --pscm, on by itself for 0x82 tests).
# 0x85 is in DUMMY_SCHEDULE too, the brute force skips it here when --dummydata is on
PSCM_SCHEDULE = [
    (SPEED_ONE, [send_misc_4, send_steering_pinion]), # 0x85, 0x7E
    (SPEED_TWO, [send_steering_angle_2]), # 0x3A8
]

def load_game(game):
    supported_games = ['fh5', 'ats']
    if(game in supported_games):
        #print('Loading {}'.format(game))
        if game == 'fh5':
            return games.fh5.data()
        elif game == 'ats':
            time.sleep(0.1) # trying to poll the API endpoint too much causes it to fail
            return games.ats.data()
    else:
        pass

# latest values from the game. Starts as the defaults so the cluster boots before the game sends anything
clusterdata = None
clusterdata_time = 0.0

# 6 Nov 2026 - poll the game on its own thread so a slow / blocking read (fh5 UDP, ats HTTP) never delays the bus
def _game_loop(game):
    global clusterdata, clusterdata_time
    while True:
        try:
            data = load_game(game)
            if data is None:
                time.sleep(retry_period) # unsupported game, keep sending the defaults
                continue
            clusterdata = data # swapping the reference is atomic, the scheduler always sees a complete object
            clusterdata_time = time.time()
        except Exception as e:
            print('* Game data error ({}), retrying in {}s'.format(e, retry_period))
            time.sleep(retry_period)

# 6 Nov 2026 - one thread sends everything on its own deadline, like an ECU would.
# Threads per speed don't help here: the GIL and the bus send lock mean they only wait on each other
def _scheduler():
    now = time.perf_counter()
    queue = []
    for period, funcs in SCHEDULE:
        for n, m in enumerate(funcs):
            # spread a group's messages across its period instead of sending them in one burst
            heapq.heappush(queue, (now + period * n / len(funcs), id(m), period, m))

    while True:
        deadline, key, period, m = queue[0]
        wait = deadline - time.perf_counter()
        if wait > 0:
            time.sleep(wait)
        m(clusterdata)
        # if we fell more than a period behind (adapter stalled), skip ahead instead of bursting to catch up
        next_deadline = deadline + period
        now = time.perf_counter()
        if next_deadline < now - period:
            next_deadline = now + period
        heapq.heapreplace(queue, (next_deadline, key, period, m))

def _status():
    while True:
        time.sleep(1)
        sent = sum(sent_count.values())
        failed = sum(fail_count.values())
        sent_count.clear()
        fail_count.clear()
        age = time.time() - clusterdata_time if clusterdata_time else float('inf')
        print('* {} frames/s, {} failed, game data age {:.2f}s'.format(sent, failed, age))


def activate(game=None):
    global clusterdata
    if(game==None):
        try:
            game = sys.argv[1]
        except:
            game = 'fh5' # default to fh5 if no param is passed

    print('* Loading game: {}'.format(game))
    clusterdata = s550_data.s550_ipc(game)

    print('* Starting thread for keyboard navigation')
    keys() # send whatever key is pressed to send to the cluster, runs on pynput's own thread

    print('* Starting thread for game data')
    threading.Thread(target=_game_loop, args=(game,), daemon=True).start()

    for speed in SCHEDULE:
        print('* Scheduling speed: {}, functions: {}'.format(speed[0], [m.__name__ for m in speed[1]]))
    threading.Thread(target=_status, daemon=True).start()
    _scheduler()



if __name__ == "__main__":
    activate()