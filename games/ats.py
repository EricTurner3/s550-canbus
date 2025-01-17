'''
    American Truck Simulator / Euro Truck Simulator 2 - Game Interface Script
    10 May 2023
    
    This file properly formats data from ATS/ETS2 to be mapped into the cluster

    REQUIRES: https://github.com/Funbit/ets2-telemetry-server
'''
import sys
sys.path.append('../')
import s550_data as d
import requests as r
import json

def data():
    formatted_data = d.s550_ipc('ats')
    data_out = json.loads(r.get("http://127.0.0.1:25555/api/ets2/telemetry").text)['truck']

    # map the forza values to expected cluster
    formatted_data.icon_parking_brake = int(data_out['parkBrakeOn'])
    formatted_data.engine_on = int(data_out['engineOn'])
    formatted_data.icon_high_beams = int(data_out['lightsBeamHighOn'])
    formatted_data.icon_left_signal = int(data_out['blinkerLeftActive'])
    formatted_data.icon_right_signal = int(data_out['blinkerRightActive'])

    formatted_data.value_speed = data_out['speed'] / 1.75
    formatted_data.value_rpm = data_out['engineRpm']
    formatted_data.value_rpm_max = data_out['engineRpmMax']
    formatted_data.oil_temp = data_out['oilTemperature']
    formatted_data.engine_temp = data_out['waterTemperature']
    return formatted_data