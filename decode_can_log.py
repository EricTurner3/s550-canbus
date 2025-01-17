import base64
import csv
import sys

# 4 Feb 2024
# script re-worked so output will work with my fork of v-ivanyshyn's parse_can_logs
# https://github.com/EricTurner3/parse_can_logs

data = []

with open(sys.argv[1], newline='') as f:
    reader = csv.reader(f)
    row_num = 1
    for row in reader:

        if row_num == 1: 
            row[2:10] = ""
            pass # skip the header row on decoding
        else: 
            row[0] = int(float(row[0])) #convert str timestamp to float
            bytes = row[6]
            #convert the b64 to hex
            row[2::] = base64.b64decode(bytes).hex(' ').upper().split(" ")
        
        data.append(row)
        row_num = row_num +1

with open('log.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(data)