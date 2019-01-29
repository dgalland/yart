import socket
from struct import *
import numpy as np
from ast import literal_eval
from fractions import Fraction 
## A message oriented socket class
## Features on the socket :
## send a receive a messge ie a counted bytes buf
## On top of a message send a recive a Python string
## On top of a string send a receive a Python object

class MessageSocket() :
    socket = None
    
    def __init__(self, sock):
        self.socket = sock

    def close(self):
        self.socket.close()
    
    def shutdown(self) :
        self.socket.shutdown(socket.SHUT_RDWR)
    
#Read len bytes on the socket
    def read(self, len):
        buf = bytearray(len)
        view = memoryview(buf)
        while len :
            n = self.socket.recv_into(view, len)
            if n == 0 :
                return None
            view = view[n:]
            len -= n
        return buf


#Send len and bytes
    def sendMsg(self,buf):
        try :
            self.socket.sendall(pack('<i',len(buf)))
            self.socket.sendall(buf)
        except :
            print('Exception sending')

#Receive len and bytes
    def receiveMsg(self):    
        buf = self.read(calcsize('<i'))
        if buf != None :
            len = unpack('<i',buf)[0]
            buf = self.read(len)
        return buf

#Send a string
    def sendString(self,s):
        self.sendMsg(s.encode())

#Receive a string
    def receiveString(self):
        return self.receiveMsg().decode()

##Send a receive a python object
## For sending the object is converted to its string representation
## At receive the string is decoded to an object

#Send an object
    def sendObject(self,obj):
        self.sendString(str((obj,'')))

#Receive an object
    def receiveObject(self):
        s = self.receiveString()
        return eval(s)[0]

#Not actually used
#Send a numpy array
    def sendArray(self,array):
        self.sendObject(array.shape)
        self.socket.sendall(array.tobyes())

#Receive a numpy array        
    def receiveArray():
        shape = self.receiveObject()
        size = 1
        for d in shape :
            size = size * d
        buf = self.read(size)
        return np.frombuffer(buf, np.uint8).reshape( shape)
