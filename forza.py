import socket
import struct

# https://github.com/nikidziuba/Forza_horizon_data_out_python

UDP_IP = "0.0.0.0" #This sets server ip to the RPi ip
UDP_PORT = 30500 #You can freely edit this



#reading data and assigning names to data types in data_types dict
data_types = {}
with open('data_format.txt', 'r') as f:
    lines = f.read().split('\n')
    for line in lines:
        data_types[line.split()[1]] = line.split()[0]


#assigning sizes in bytes to each variable type
jumps={
    's32': 4, #Signed 32bit int, 4 bytes of size
    'u32': 4, #Unsigned 32bit int
    'f32': 4, #Floating point 32bit
    'u16': 2, #Unsigned 16bit int
    'u8': 1, #Unsigned 8bit int
    's8': 1, #Signed 8bit int
    'hzn': 12 #Unknown, 12 bytes of.. something
}




def get_data(data):
    return_dict={}

    #additional var
    passed_data = data
    
    for i in data_types:
        d_type = data_types[i]#checks data type (s32, u32 etc.)
        jump=jumps[d_type]#gets size of data
        current = passed_data[:jump]#gets data

        decoded = 0
        #complicated decoding for each type of data
        if d_type == 's32':
            decoded = int.from_bytes(current, byteorder='little', signed = True)
        elif d_type == 'u32':
            decoded = int.from_bytes(current, byteorder='little', signed=False)
        elif d_type == 'f32':
            decoded = struct.unpack('f', current)[0]
        elif d_type == 'u16':
            decoded = struct.unpack('H', current)[0]
        elif d_type == 'u8':
            decoded = struct.unpack('B', current)[0]
        elif d_type == 's8':
            decoded = struct.unpack('b', current)[0]
        
        #adds decoded data to the dict
        return_dict[i] = decoded
        
        
        #removes already read bytes from the variable
        passed_data = passed_data[jump:]
    
    
    
    #returns the dict
    return return_dict


#setting up an udp server
sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP

sock.bind((UDP_IP, UDP_PORT))


def fetch_forza_data():
    data, addr = sock.recvfrom(1500) # buffer size is 1500 bytes, this line reads data from the socket
    ##received data is now in the retuturned_data dict, key names are in data_format.txt
    returned_data = get_data(data)
    print(str(returned_data['CurrentEngineRpm']) + '/' + str(returned_data['EngineMaxRpm']))
    return returned_data

if __name__ == "__main__":
        while True:
            fetch_forza_data()

