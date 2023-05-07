import serial.tools.list_ports
ports = serial.tools.list_ports.comports()

# run this to determine which port the USB-TO-CAN sensor is attached to
for port, desc, hwid in sorted(ports):
        print("{}: {} [{}]".format(port, desc, hwid))