# Ford CAN Database
Vehicles Tested: 2015 Mustang GT Premium / 2016 Ford Mustang GT350


**Notes**:
* All byte references start at 0, so the range is 0-7

# 0x4C - Airbag / Seatbelt Indicators
Sample Message: `10 AF FF 00 00 00 00 00`
```
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
```

# 0x81 - Steering Wheel Buttons
Sample Message: `00 00 00 00 00 00 00 00`
```
Byte 1
    0x02 - left arrow
    0x04 - right arrow
    0x08 - up arrow
    0x01 - down arrow
    0x10 - OK button
```

# 0x82 - Misc
Sample Message: `82 00 14 40 7E 00 64 FF`
```
Byte 2 & 3 - Fuel Consumption ?? 
Byte 6 - Steering Mode
    0x40 - Normal
    0x44 - Sport
    0x48 - Comfort
```

# 0x83 - Clockspring
Sample Message: `00 E0 80 00 00 00 00 00`
```
Byte 0 & 4 change based on the high beams status
    00 & 00 - off
    40 & 08 - flash high beams
    00 & 10 - high beam switch activated 
    80 & 00 - high beams on

Byte 0 also changes if the turn signal lever is depressed, though this does not appear to trigger the actual turn signal indicators on the cluster
    00 - off
    10 - left signal
        50 - left signal & flash high beams (add first digits)
    20 - right signal
```

# 0x156 - Coolant & Oil Temp Gauge
Sample Message: `9E 99 00 00 03 00 00 00`
```
Byte 0 is for the Engine/Coolant Temp Gauge (seen on analog cluster under RPM)
    Temp is in Celsius, int(byte0) - 60 = Temp, thus A0 would be 106c or 320f
    Gauge doesn't start to move until around 0x80
    Gauge seems to have a safe zone and 'freezes' from around 0xA6 (106c) to 0xC0 (132c) where it then rapidly ramps up and can trigger overheat warning
Byte 1 is for the Oil Temp Gauge (seen under center screen, Gauge Mode > Oil Temp)
    Temp is in Celsius, int(byte0) - 60 = Temp
    Gauge starts to move at 0x60  (36c) and caps out around 0xDA (158c)
Byte 4 toggles the engine overheat message and maxes engine temp guage  (doesn't seem to be necessary as a high byte 0 will also trigger the warning)
    0x03 - normal
    0x08 - overheat
```

# 0x178 - Launch Control / ABS Indicators
Sample Message: `00 00 02 00 0E 88 C6 86`
```
Byte 0 
    0x2_ - LC Icon
    0x8_ - RPM Icon, LC Fault
    0xA_ - LC Flashing Icon
```

# 0x179 - Warning Suppression
Sample Message: `00 00 00 00 96 00 02 C8`
```
Several Warning messages such as fuel service inlet, change oil soon, oil change required.

I have not dove into what each exact bit does, but this line shuts the above warnings off.
```

# 0x202 - Speed Guage
Sample Message: `00 FA 10 00 60 00 00 00`
```
Byte 4 must have a first digit of 6 or the gauge does not work
Bytes 6 & 7 are the speed gauge
    Unsure the reasons why but speed in MPH * 175 nets the proper gauge value
```

# 0x204 - RPM Guage
Sample Message: `C0 00 7D 01 4B 00 00 00`
```
Bytes 3 & 4 - RPM
    Gauge goes from 0 to 4000. Seems to be 1/2 of the actual RPM
    If RPM is 5000, the int that is passed should be 2500 (09 C4)
```

# 0x3B3 - IPC On, Door Status, Parking Brake Indicator
Sample Message: `40 88 00 12 10 00 80 02`

This one message deals with a large amount of data, and the bytes can be added to maintain multiple functions. I have some understanding of what it does but not entirely.

If this message is not sent, the cluster will not even boot up when power is supplied.
```
Byte 0 - Headlamp On/Off
    40 - Off
    44 - On
Byte 1 - Light Mode
    48 - DRL
    88 - Night
    4A - Hazard
Byte 0 & 1 also have to do with if the IPC is on, other notes:
    40 48 is running, doors closed, lights off
    41 48 is running, trunk ajar
Byte 3  has to do with backlight
    0x00 is backlight off
    0x0a is backlight on (mycolor)
    0x10 is backlight on (white)
Byte 6 is Parking Brake On (0x80/0xC0) or Off (0x00)
Byte 7 deals with the doors
    First digit 0, 1, 2, 3 is Closed, Passenger Ajar, Driver Ajar, Both Ajar respectively.
    Second Digit is 2 for closed or A for Hood Ajar
    02 - All Closed, 32 - Driver/Pass Door Open, 2A - Driver + Hood Doors Open
```
# 0x3B5 - Tire Pressure
Sample Message: `00 CE 00 CE 00 CE 00 CE`

Credit [here](https://github.com/v-ivanyshyn/parse_can_logs/blob/master/Ford%20CAN%20IDs%20Summary.md)
```
Byte 1 - Front Left Tire Pressure
Byte 3 - Front Right Tire Pressure
Byte 5 - Rear Right Tire Pressure
Byte 7 - Rear Left Tire Pressure
```


# 0x3C3 - Misc 1
Sample Message: `40 00 10 00 00 00 80 00`
```
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
```

# 0x416 - Misc 2
Sample Message: `50 00 FE 00 01 00 00 00`
```
ABS, Traction Control Off, Traction Control Loss Icons, Airbag
        
Byte 1 - 
    0x2_ - Check Brake System warning
    0x4_  - AdvanceTrac System Warning
Byte 5 has to do with a solid traction control or a flashing icon
    0x00 - Indicator Off
    0x02 - Indicator Solid
    0x0F - Indicator Flashing
    0x80 - TC Off Indicator
    0x18 - ATC Off Indicator
Byte 6 -
    0x0_ - ABS light off
    0x4_ - ABS Solid
    0x8_ - ABS Flash Slow
    0xD_ - ABS Flash Fast
```

# 0x430 - Odometer
Sample Message: `37 01 B9 AA C0 5E 37 5C`

Note this does not appear to allow arbitrary updates, if the mileage is not close to what is programmed in the cluster then it just shows -------
```
Byte 1, 2, 3 show odometer in kilometers
```

# 0x431 - Transmission Warnings
Sample Message: `05 1D 40 EB B7 83 46 00`


```
Controls warning messages for 
- Transmission Adaptive Mode
- Transmission IndicatMode
- Transmission Warming Up
- Transmission Adjusted
```