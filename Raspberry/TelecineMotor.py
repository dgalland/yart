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
      
    def __init__(self, pi, queue):

        self.steps_per_rev = 800 #Marche mieux an 800
        self.ena_pin = 17
        self.dir_pin = 18
        self.pulse_pin = 23
        self.trigger_pin = 24
        self.pulley_ratio = 1  #  Motor/Frame
        self.ena_level = 0
        self.dir_level = 0
#        self.pulse_level = 1
        self.trigger_level = 0
        self.frameCounter = 0
        self.triggerCallback = None
        self.speed = 0
        self.capture_speed = 0
        self.play_speed = 0
        self.triggered = False
        self.triggerEvent = None
        self.direction = MOTOR_FORWARD
        self.pi = pi
        self.queue = queue

    def on(self) :
        self.frameCounter = 0
        if self.ena_pin != 0 :
            self.pi.write(self.ena_pin, self.ena_level)
        self.pi.set_mode(self.dir_pin, pigpio.OUTPUT)
        self.pi.set_mode(self.pulse_pin, pigpio.OUTPUT)
        self.pi.set_mode(self.ena_pin, pigpio.OUTPUT)
        self.pi.set_mode(self.trigger_pin, pigpio.INPUT)
        self.pi.write(self.dir_pin, self.dir_level)
#        self.pi.write(self.pulse_pin, 1 - self.pulse_level)
        if self.triggerCallback != None :
            self.triggerCallback.cancel()
        if self.trigger_pin != 0 :
            if self.trigger_level == 0 :
                self.triggerCallback = self.pi.callback(self.trigger_pin, pigpio.FALLING_EDGE, self.trigger)
                self.pi.set_pull_up_down(self.trigger_pin, pigpio.PUD_UP)
            else :
                self.triggerCallback = self.pi.callback(self.trigger_pin, pigpio.RISING_EDGE, self.trigger)
                self.pi.set_pull_up_down(self.trigger_pin, pigpio.PUD_DOWN)
#            self.pi.set_glitch_filter(self.trigger_pin, 1)
        
    def off(self) :
        if self.ena_pin != 0 :
            self.pi.write(self.ena_pin, 1 - self.ena_level)
        if self.triggerCallback != None :
            self.triggerCallback.cancel()
        self.triggerCallback = None

    def trigger(self, gpio,level,  tick ) :
        if self.direction == MOTOR_FORWARD :
            self.frameCounter = self.frameCounter +1
        else :
            self.frameCounter = self.frameCounter - 1
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
        self.pi.write(self.dir_pin, 0 if self.direction == self.dir_level else 1)  #self.direction = 0 forward
        self.pi.wave_clear()
        chain = []
        x = self.steps_per_rev  & 255
        y = self.steps_per_rev  >> 8
        for s in range(2,int(self.speed),2) :
            chain += [255, 0, self.wave(s), 255, 1, x, y] #One rev for each
        chain += [255, 0, self.wave(self.speed), 255, 3]  #Loop forever
        self.pi.wave_chain(chain)  # Transmit chain.
##        self.pi.wave_chain(chain)  # Transmit ramping chain
##        self.pi.wave_send_repeat(self.wave(self.speed))

#Advance count rev, return when finished (no ramping)
    def advanceCounted(self, count=1):
        self.triggered = False
        self.pi.write(self.dir_pin, 0 if self.direction == self.dir_level else 1)  #self.direction = 0 forward
        self.pi.wave_clear()
        chain = []
        start = int(self.steps_per_rev/2)
        x = start  & 255
        y = start  >> 8  
        chain += [255, 0, self.wave(self.speed/2), 255, 1, x, y] #half rev at speed/2
        x = (count*self.steps_per_rev-start)  & 255
        y = (count*self.steps_per_rev-start)  >> 8  #to to pulley_ratio !
        chain += [255, 0, self.wave(self.speed), 255, 1, x, y] 
        self.pi.wave_chain(chain)  # Transmit chain.
        time.sleep(self.pi.wave_get_micros()*count*self.steps_per_rev/1000000.)      
     
    def advanceUntilTrigger(self):
        if self.trigger_pin != 0 :
            self.triggered = True
            self.pi.write(self.dir_pin, 0 if self.direction == self.dir_level else 1)  #self.direction = 0 forward
            self.pi.wave_clear()
#            chain = [255, 0, self.wave(self.speed), 255, 3]  #Loop forever but triggered without ramping
            chain = []
            x = (int(self.steps_per_rev/8))  & 255   
            y = (int(self.steps_per_rev/8))  >> 8  
            chain += [255, 0, self.wave(self.speed/2), 255, 1, x, y] #speed/2 for 1/8 rev
            chain += [255, 0, self.wave(self.speed), 255, 3]  #Loop forever but triggered

            self.pi.wave_chain(chain)  # Transmit chain.
            self.triggerEvent.wait()
        else :
            self.advanceCounted()

           
    def close(self):
        self.stop()
        self.off()
        
    def stop(self) :
        self.pi.wave_clear()
        self.pi.wave_tx_stop()

##if __name__ == '__main__':
##    motor = None
##    pi = None
##    queue = Queue()    
##    try:
##        pi = pigpio.pi()
##
##        if not pi.connected:
##            print('Not connected')
##            exit()
##        motor = TelecineMotor(pi, queue)
##        motor.speed = 8
##        motor.direction = 0
##        motor.triggerEvent = Event()
##        motor.triggerEvent.clear()
##        
##        for i in range(10) :
##            motor.advanceUntilTrigger()
##            time.sleep(1)
####        startTime = time.time()
####        motor.captureSpeed = 1
####        motor.advanceWithDelayOnTrigger(1)
####        time.sleep(100)
####
##        motor.speed = 5
##        for i in range(10) :
##            motor.advanceUntilTrigger()  #0 forward 1 backward
##            time.sleep(1)
##
##    finally:
##        print('finally')
##        if motor != None :
##            motor.stop()
##            motor.close()
##        if pi != None:
##            pi.stop()
