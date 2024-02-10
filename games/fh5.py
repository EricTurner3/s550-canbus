'''
    Forza Horizon 5 - Game Interface Script
    10 May 2023
    
    This file properly formats data from FH5 to be mapped into the cluster
'''
import sys
sys.path.append('../')
import s550_data as d
import games.supporting_files.forza as forza

def data():
    formatted_data = d.s550_ipc('fh5')
    fh5_data_out = forza.fetch_forza_data()

    # map the forza values to expected cluster
    if (fh5_data_out['HandBrake'] > 0):
        formatted_data.icon_parking_brake = 1
    else:
        formatted_data.icon_parking_brake = 0

    tire_slip_threshold = 10
    if (fh5_data_out['TireSlipRatioFrontLeft'] >= tire_slip_threshold or \
        fh5_data_out['TireSlipRatioFrontRight'] >= tire_slip_threshold or \
        fh5_data_out['TireSlipRatioRearLeft'] >= tire_slip_threshold or \
        fh5_data_out['TireSlipRatioRearRight'] >= tire_slip_threshold):
        formatted_data.icon_traction_control = 2
    else:
        formatted_data.icon_traction_control = 0

    formatted_data.value_speed = fh5_data_out['Speed'] * 2
    formatted_data.value_rpm = fh5_data_out['CurrentEngineRpm']
    formatted_data.value_rpm_max = fh5_data_out['EngineMaxRpm']
    formatted_data.value_boost = fh5_data_out['Boost']
    formatted_data.value_odometer = fh5_data_out['DistanceTraveled']
    return formatted_data