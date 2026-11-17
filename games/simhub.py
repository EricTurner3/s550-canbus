'''
    SimHub - Game Interface Script
    14 Nov 2026

    Any game SimHub reads, through SimHub's own web API (the same server as its web dashboards)
        http://localhost:8888/api/getgamedata -> NewData is SimHub's normalized game data (DataCorePlugin.GameData.*)

    REQUIRES: SimHub running, Settings > General > Web Server enabled (port 8888)
    Temperatures and tire pressures come in the units picked in SimHub's settings (TemperatureUnit / TyrePressureUnit),
    converted back here. Fields a game doesn't support are 0 (or -1 for the lights), the s550_data defaults are kept
'''
import sys
sys.path.append('../')
import time
import s550_data as d
import requests as r

URL = 'http://localhost:8888/api/getgamedata'
POLL_PERIOD = 0.02          # s, 50 Hz. SimHub answers in ~5 ms

# g meter. SimHub's motion values, the force the driver feels. Flip a sign if the dot moves the wrong way
ACCEL_SCALE = 9.81          # SimHub gives g, x 9.81 -> m/s^2
LAT_SIGN = 1
LONG_SIGN = -1              # ATS: AccelerationSurge goes negative pulling away
# compass (0x466) from OrientationYaw, degrees. Change these if N on the APIM isn't north in the game
COMPASS_SIGN = 1
COMPASS_OFFSET = 0
# a reported tire under this shows Tire Pressure Low with that tire highlighted (0x3B4). 0 turns it off
TIRE_LOW_PSI = 20
# boost / vacuum and AFR for games that don't send them (no game sends AFR, ATS has no turbo), from throttle and RPM
# like the GT's naturally aspirated engine: ~-20 inHg (-10 psi) closed throttle, ~0 wide open. SIM_BOOST_PSI adds
# boost on top at full throttle and redline, for a turbo feel. AFR 14.7 cruising, richer to ~12.5 past 60% throttle
SIM_VACUUM_PSI = -10.0
SIM_BOOST_PSI = 0.0
SIM_AFR_WOT = 12.5
# cruise set speed, shown as sent in the cluster's unit. CruiseControlSpeedKmh for a cluster set to km/h
CRUISE_SPEED = 'CruiseControlSpeedMph'
# the game's turn signal lamp flashes, SimHub is sampled between flashes. Held this long after the last on (s),
# the cluster flashes it on its own (icon 2)
SIGNAL_HOLD = 0.6

session = r.Session() # keeps the connection open, a new one per poll is slower
signal_on = {'left': 0.0, 'right': 0.0}

def celsius(value, unit):
    return (value - 32) * 5 / 9 if unit == 'Fahrenheit' else value

def temperature(nd, name):
    '''
        The game's temperature in Celsius, None when the game doesn't send it (0 c, 32 in Fahrenheit)
    '''
    value = nd.get(name) or 0
    c = celsius(value, nd.get('TemperatureUnit'))
    return None if abs(c) < 0.01 else c

def psi(value, unit):
    unit = (unit or '').lower()
    if unit == 'bar':
        return value * 14.504
    if unit == 'kpa':
        return value / 6.895
    return value

def signal(side, on, now):
    if on == 1:
        signal_on[side] = now
    return 2 if now - signal_on[side] < SIGNAL_HOLD else 0

def data():
    time.sleep(POLL_PERIOD)
    formatted_data = d.s550_ipc('simhub')
    game = session.get(URL, timeout=1).json()
    nd = game.get('NewData')
    if not nd or game.get('GamePaused'):
        return formatted_data # no game / paused, the defaults (parked, warm engine)

    now = time.time()
    formatted_data.value_speed = nd.get('SpeedMph') or 0.0
    formatted_data.value_rpm = nd.get('Rpms') or 0.0
    formatted_data.value_rpm_max = nd.get('MaxRpm') or nd.get('CarSettings_MaxRPM') or formatted_data.value_rpm_max
    throttle = max(0.0, min(1.0, (nd.get('Throttle') or 0.0) / 100)) # SimHub 0 - 100
    load = max(0.0, min(1.0, formatted_data.value_rpm / formatted_data.value_rpm_max))
    if nd.get('MaxTurboBar') or nd.get('TurboBar'):
        formatted_data.value_boost = nd['TurboBar'] * 14.504
    else:
        formatted_data.value_boost = SIM_VACUUM_PSI * (1 - throttle) + SIM_BOOST_PSI * throttle * load
    formatted_data.value_afr = 14.7 - (14.7 - SIM_AFR_WOT) * max(0.0, throttle - 0.6) / 0.4

    # -1 is "not supported by this game"
    formatted_data.engine_on = 0 if nd.get('EngineIgnitionOn') == 0 else 1
    if nd.get('EngineIgnitionOn') == 1 and nd.get('EngineStarted') == 0:
        formatted_data.icon_check_engine = 1 # key on, engine off, like the car's bulb check
    formatted_data.icon_parking_brake = int(nd.get('ParkingBrakeActive') == 1 or (nd.get('Handbrake') or 0) > 0)
    # Gear is a string, N / 0 neutral, R reverse, 1+ the gear. Games don't send P, the parking brake stands in for it
    gear = str(nd.get('Gear') or 'N').upper()
    if nd.get('ParkingBrakeActive') == 1 or gear == 'P':
        formatted_data.value_gear = -2
    elif gear == 'R':
        formatted_data.value_gear = -1
    else:
        formatted_data.value_gear = int(gear) if gear.isdigit() else 0
    formatted_data.icon_high_beams = int(nd.get('HighBeamActive') == 1)
    formatted_data.icon_low_beams = int(nd.get('LowBeamActive') == 1 or nd.get('HeadlightsActive') == 1)
    formatted_data.icon_cruise_control = int(nd.get('CruiseControlActive') == 1)  # 1 green, active
    if formatted_data.icon_cruise_control:
        # games clear the set speed when cruise goes off, so the grey standby state (icon 2) never comes up
        formatted_data.value_cruise_speed = round(nd.get(CRUISE_SPEED) or 0)
    formatted_data.icon_abs = 2 if nd.get('ABSActive') == 1 else 0
    formatted_data.icon_traction_control = 2 if nd.get('TCActive') == 1 else 0
    formatted_data.icon_left_signal = signal('left', nd.get('TurnIndicatorLeft'), now)
    formatted_data.icon_right_signal = signal('right', nd.get('TurnIndicatorRight'), now)

    coolant = temperature(nd, 'WaterTemperature')
    if coolant is not None:
        formatted_data.engine_temp = coolant
        formatted_data.cylinder_head_temp = coolant - 11 # no game sends it, follows coolant (99c at 110c)
    oil = temperature(nd, 'OilTemperature')
    if oil is not None:
        formatted_data.oil_temp = oil
    air = temperature(nd, 'AirTemperature')
    if air is not None:
        formatted_data.outside_temp = air
        formatted_data.intake_temp = air

    formatted_data.compass_heading = (COMPASS_SIGN * (nd.get('OrientationYaw') or 0.0) + COMPASS_OFFSET) % 360
    formatted_data.accel_lateral = LAT_SIGN * (nd.get('AccelerationSway') or 0.0) * ACCEL_SCALE
    formatted_data.accel_longitudinal = LONG_SIGN * (nd.get('AccelerationSurge') or 0.0) * ACCEL_SCALE

    unit = nd.get('TyrePressureUnit')
    for tire, name in (('fl', 'FrontLeft'), ('fr', 'FrontRight'), ('rr', 'RearRight'), ('rl', 'RearLeft')):
        reported = psi(nd.get('TyrePressure' + name) or 0.0, unit)
        if reported:
            setattr(formatted_data, 'tire_pressure_' + tire, reported)
            setattr(formatted_data, 'warning_tire_low_' + tire, reported < TIRE_LOW_PSI)
    return formatted_data
