import base64
import csv
import sys

data = []

with open(sys.argv[1], newline='') as f:
    reader = csv.reader(f)
    for row in reader:
        #convert the b64 to hex
        row[6] = base64.b64decode(row[6]).hex(' ').upper()
        data.append(row)

with open('converted.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(data)