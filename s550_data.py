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
        
        # raw values, typically numbers used in gauges
        self.value_speed = 0.0              # miles per hour
        self.value_rpm = 0.0
        self.value_rpm_max = 8000           # modify if game car has higher/lower RPM than cluster
        self.value_odometer = 0             # kilometers
        self.value_boost = 0.0              # currently unmapped
        self.value_fuel = 0.0               # currently unmapped
        self.oil_temp = 0.0                 # celsius
        self.engine_temp = 0.0              # celsius
