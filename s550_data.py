'''
    S550 Data Format
    10 May 2023
    
    This script provides the default schema in order to send to the s550.py file
    This can be inherited to 
'''

class s550_ipc:

    def __init__(self, game):
        self.game = game

        self.engine_on = 1                  # 1 on; 0 off. Disables backlight when off
        # icons have 3 states
        # 0 - off
        # 1 - on
        # 2 - on, flashing (some)
        self.icon_launch_control = 0
        self.icon_abs = 0                   
        self.icon_traction_control = 0
        self.icon_airbag = 0 
        self.icon_seatbelt = 0              # no flashing
        self.icon_parking_brake = 0          # no flashing
        self.icon_left_signal = 0           # either 0 or 2
        self.icon_right_signal = 0          # either 0 or 2
        self.icon_high_beams = 0            # no flashing
        self.icon_check_engine = 0          # 0 off, 1 solid, 2 flashing

        # raw values, typically numbers used in gauges
        self.value_speed = 0.0              # miles per hour
        self.value_rpm = 0.0
        self.value_rpm_max = 8000           # modify if game car has higher/lower RPM than cluster
        self.value_odometer = 0             # kilometers
        self.value_boost = 0.0              # psi, negative is vacuum. Gauge is 30 inHg (-14.7 psi) to 20 psi
        self.value_afr = 14.7               # air fuel ratio
        self.value_fuel = 0.0               # currently unmapped
        # warm engine defaults, for games that don't send these (Forza). ATS sends oil and coolant
        self.oil_temp = 100.0               # celsius (212f), gauge 36c - 158c
        self.engine_temp = 110.0            # celsius (230f), the needle sits mid gauge from 106c - 132c
        self.cylinder_head_temp = 99.0      # celsius (210f), gauge is 140f - 340f (60c - 171c)
        self.intake_temp = 22.0             # celsius (72f), gauge is 0f - 240f (-18c - 116c)
        self.accel_lateral = 0.0            # m/s^2 felt by the driver, positive moves the g meter dot right (left turn)
        self.accel_longitudinal = 0.0       # m/s^2, positive speeding up (dot to accel), negative braking. +-1.5g fills it
        self.accel_vertical = 9.7           # m/s^2, gravity at rest
        # psi. Forza's data out has no tire pressures, set these to match the car
        self.tire_pressure_fl = 35.0
        self.tire_pressure_fr = 35.0
        self.tire_pressure_rr = 35.0
        self.tire_pressure_rl = 35.0

        # 8 Nov 2026 - warning messages, True shows it. See database.md for the frames
        # tire low (0x3B4): any of these shows the Tire Pressure Low window with that tire highlighted, several can be on
        self.warning_tire_low_fl = False
        self.warning_tire_low_fr = False
        self.warning_tire_low_rr = False
        self.warning_tire_low_rl = False
        self.warning_tire_sensor_fault = False      # Tire Pressure Sensor Fault, lamp flashing. Tire low wins
        # transmission (0x431): one message at a time, the first True in this order wins
        self.warning_trans_overheat = False         # Transmission Overheat, Stop
        self.warning_trans_too_hot = False          # Transmission Too Hot, Press Brake
        self.warning_trans_malfunction = False      # Transmission Malfunction
        self.warning_trans_service = False          # Transmission Service Required
        self.warning_trans_adapt_mode = False       # Transmission Adapt Mode
        self.warning_trans_indicator_lockup = False # Transmission Indicator Mode Lockup
        self.warning_trans_warming_up = False       # Transmission Warming Up
        # occupant sensor (0x42C)
        self.warning_occupant_sensor_pass = False   # Occupant Sensor Blocked, passenger icon
        # key / start (0x38D): one message at a time, the first True in this order wins
        self.warning_key_starting_fault = False     # Starting System Fault
        self.warning_key_not_detected = False       # No Key Detected
        self.warning_key_press_brake = False        # Press Brake to Start
        self.warning_key_press_clutch = False       # Press Clutch to Start
        self.warning_key_run_power_active = False   # Run Power Active
