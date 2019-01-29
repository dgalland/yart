import socket
from struct import *
import copy
import time
import sys
import pigpio
from threading import Thread, Event
from queue import Queue

sys.path.append('../Common')
from Constants import *


class TelecineMotor() :
    steps_per_rev = 800 #Marche mieux an 800
    ena_pin = 17
    dir_pin = 18
    pulse_pin = 23
    trigger_pin = 24
    pulley_ratio = 1  #  Motor/Frame
    frameCounter = 0
    triggerCallback = None
    speed = 0
    capture_speed = 0
    play_speed = 0
    triggered = False
    triggerEvent = None
    direction = MOTOR_FORWARD
      
    def __init__(self, pi, queue):
        self.pi = pi
        self.pi.set_mode(self.dir_pin, pigpio.OUTPUT)
        self.pi.set_mode(self.pulse_pin, pigpio.OUTPUT)
        self.pi.set_mode(self.ena_pin, pigpio.OUTPUT)
        self.pi.set_mode(self.trigger_pin, pigpio.INPUT)
        self.pi.write(self.dir_pin, 0)
        self.pi.write(self.pulse_pin, 0)
        self.pi.write(self.ena_pin, 1) #repos
        self.triggerCallback = self.pi.callback(self.trigger_pin, pigpio.FALLING_EDGE, self.trigger)
        self.queue = queue
        

    def trigger(self, gpio,level,  tick ) :
        if self.direction == MOTOR_FORWARD :
            self.frameCounter = self.frameCounter +1
        else :
            self.frameCounter = self.frameCounter - 1
#Provoque des ennuis            
#        self.queue.put({'type':HEADER_COUNT,'count': self.frameCounter}) 
        if self.triggered and self.pi.wave_tx_busy() :
            self.pi.wave_tx_stop()
        self.triggerEvent.set()
        self.triggerEvent.clear()
            
    def wave(self, speed) :
        freq = int(self.steps_per_rev*speed/self.pulley_ratio) #en HZ
        wf = []
        micros = int(500000/freq)
        wf.append(pigpio.pulse(1 << self.pulse_pin, 0, micros))  # pulse on micros
        wf.append(pigpio.pulse(0, 1 << self.pulse_pin, micros))  # pulse off
        self.pi.wave_add_generic(wf)
        return self.pi.wave_create() #return wave id and
          

#Advance at speed with some ramping to obtain the desired speed
#return immediately    
    def advance(self):
        self.triggered = False
        self.pi.write(self.ena_pin, 0)  #Power on
        self.pi.write(self.dir_pin, self.direction)
        self.pi.wave_clear()
        chain = []
        x = self.steps_per_rev  & 255
        y = self.steps_per_rev  >> 8
        for s in range(2,int(self.speed),2) :
            print(s)
            chain += [255, 0, self.wave(s), 255, 1, x, y] #One rev for each
        chain += [255, 0, self.wave(self.speed), 255, 3]  #Loop forever
        self.pi.wave_chain(chain)  # Transmit chain.
#Unused    
    def advanceWithDelay(self, delay):    #with a delay between rev delay in millis No ramping
        self.triggered = False
        self.pi.write(self.ena_pin, 0)  #Power on
        self.pi.write(self.dir_pin, self.direction)
        self.pi.wave_clear()
        delayMicros = delay*1000 
        delayCount = int(delay*1000/50000)
        delayMicros = delayMicros % 50000
        x = (self.steps_per_rev)  & 255
        y = (self.steps_per_rev)  >> 8
        chain = [255,0]
        chain += [255, 0, self.wave(self.speed), 255, 1, x, y]  #One rev
        for i in range (delayCount) :                        
            chain += [255, 2, 50000 & 255, 50000 >> 8]
        chain += [255, 2, delayMicros & 255, delayMicros >> 8]
        chain += [255,3]    
        self.pi.wave_chain(chain)  # Transmit chain.

#Advance count rev, return when finished (no ramping)
    def advanceCounted(self, count=1):
        self.triggered = False
        self.pi.write(self.ena_pin, 0)  #Power on
        self.pi.write(self.dir_pin, self.direction)
        self.pi.wave_clear()
        wid = self.wave(self.speed)
        x = (count*self.steps_per_rev)  & 255
        y = (count*self.steps_per_rev)  >> 8  #to to pulley_ratio !
        chain = [255, 0, wid, 255, 1, x, y] 
        self.pi.wave_chain(chain)  # Transmit chain.
        time.sleep(self.pi.wave_get_micros()*count*self.steps_per_rev/1000000.)      
     
    def advanceUntilTrigger(self):
        self.triggered = True
        self.pi.write(self.ena_pin, 0)  #Power on
        self.pi.write(self.dir_pin, self.direction)
        self.pi.wave_clear()
        chain = [255, 0, self.wave(self.speed), 255, 3]  #Loop forever but triggered
        self.pi.wave_chain(chain)  # Transmit chain.
        self.triggerEvent.wait()

#Not used while not really better        
    def advanceUntilTriggerWithRamping(self):  
        self.triggered = True
        self.pi.write(self.ena_pin, 0)  #Power on
        self.pi.write(self.dir_pin, self.direction)
        self.pi.wave_clear()
        steps = self.steps_per_rev/self.pulley_ratio
        d = int(steps/10)
        a = - 4*self.speed/(steps*steps)
        b = - 2*a * steps/2
        chain = []
        lasty = 0
        for x in range(0, int(steps-d), d) :
            xx = x + steps/10
            y = a*xx*xx + b*xx
            print (x, ' ', y)
            lasty = y
            chain += [255,0, self.wave(int(y)), 255, 1, d&255, d >> 8]
        chain += [255, 0, self.wave(int(y)), 255, 3]  #Loop forever but triggered
        print(chain)
        self.pi.wave_chain(chain)  # Transmit chain.
        self.triggerEvent.wait()
            
    def close(self):
        self.pi.write(self.ena_pin, 1)  #Power off
        self.triggerCallback.cancel()
        self.stop()
        
    def stop(self) :
        self.triggerFlag = False
        self.pi.wave_tx_stop()

if __name__ == '__main__':
    motor = None
    pi = None
    queue = Queue()    
    try:
        pi = pigpio.pi()

        if not pi.connected:
            print('Not connected')
            exit()
        motor = TelecineMotor(pi, queue)
        motor.speed = 8
        motor.direction = 0
        motor.triggerEvent = Event()
        motor.triggerEvent.clear()
        
        for i in range(10) :
            motor.advanceUntilTriggerWithRamping()
            time.sleep(1)
##        startTime = time.time()
##        motor.captureSpeed = 1
##        motor.advanceWithDelayOnTrigger(1)
##        time.sleep(100)
##
        motor.speed = 5
        for i in range(10) :
            motor.advanceUntilTrigger()  #0 forward 1 backward
            time.sleep(1)

    finally:
        print('finally')
        if motor != None :
            motor.stop()
            motor.close()
        if pi != None:
            pi.stop()
