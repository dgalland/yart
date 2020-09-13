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

        self.steps_per_rev = 200 #Marche mieux an 800
        self.ena_pin = 17
        self.dir_pin = 18
        self.pulse_pin = 23
        self.trigger_pin = 24
        self.pulley_ratio = 1  #  Motor/Frame ratio ex 2 2 motor rev for 1 frame
        self.ena_level = 0
        self.dir_level = 0
#        self.pulse_level = 1
        self.trigger_level = 0
        self.frameCounter = 0
        self.triggerCallback = None
        self.speed = 0                    #Motor speed rev/s
        self.capture_speed = 0
        self.play_speed = 0
        self.triggered = False
        self.triggerEvent = None
        self.direction = MOTOR_FORWARD
        self.pi = pi
        self.queue = queue
        self.tick=0
        self.after_trigger = True
        self.triggerCount = 0

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
        self.triggerCount = self.triggerCount + 1
        delay = (self.pulley_ratio/self.speed)*1000000.  #normal delay for one turn micro seconds
        diff = tick - self.tick
        self.tick = tick
        if self.tick != 0 and diff < int(delay/2.) :
            return
        if self.direction == MOTOR_FORWARD :
            self.frameCounter = self.frameCounter +1
        else :
            self.frameCounter = self.frameCounter - 1
        if self.triggered and self.pi.wave_tx_busy() :
            if self.after_trigger :
#Continue for 1/16 of rev after the trigger                
                pulses = int(self.steps_per_rev*self.pulley_ratio)  #Motor pulses for one turn
                end = int(pulses / 16) 
                x = end  & 255
                y = end  >> 8
                chain=[]
                chain += [255, 0, self.wave(self.speed/2), 255, 1, x, y] #half rev at speed/2
                self.pi.wave_chain(chain)
            else :                
                self.pi.wave_tx_stop()
        self.triggerEvent.set()
        self.triggerEvent.clear()
            
    def wave(self, speed) :
#        freq = int(self.steps_per_rev*speed/self.pulley_ratio) #en HZ
        freq = int(self.steps_per_rev*speed) #en HZ
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

#Advance count rev, return when finished (no ramping)
    def advanceCounted(self, count=1):
        self.triggered = False
        self.pi.write(self.dir_pin, 0 if self.direction == self.dir_level else 1)  #self.direction = 0 forward
        self.pi.wave_clear()
        chain = []
        pulses = int(count*self.steps_per_rev*self.pulley_ratio)  #Motor pulses count
        start = int((pulses/count) / 2) 
        x = start  & 255
        y = start  >> 8  
        chain += [255, 0, self.wave(self.speed/2), 255, 1, x, y] #half rev at speed/2
        x = (pulses - start)  & 255
        y = (pulses -start)  >> 8  
        chain += [255, 0, self.wave(self.speed), 255, 1, x, y] 
        self.pi.wave_chain(chain)  # Transmit chain.
        time.sleep(self.pi.wave_get_micros()*count*self.steps_per_rev/1000000.)      

    def calibrate(self) :
        oldRatio = self.pulley_ratio
        rev = 20
        self.pulley_ratio = 1.
        self.triggerCount = 0
        self.advanceCounted(rev)
        time.sleep(1)
        ratio = 0
        if not self.triggerCount == 0 :
            ratio = rev/self.triggerCount
        msgheader = {'type':HEADER_MESSAGE, 'msg': '%d triggers detected for %d motor rev ratio seems %f' % (self.triggerCount, rev, ratio)}
        self.queue.put(msgheader)
        self.pulley_ratio = oldRatio

    def advanceUntilTrigger(self):
        if self.trigger_pin != 0 :
            self.pi.write(self.dir_pin, 0 if self.direction == self.dir_level else 1)  #self.direction = 0 forward
            self.pi.wave_clear()
            pulses = int(self.steps_per_rev*self.pulley_ratio)  #Motor pulses for one turn
            start = int(pulses / 16) 
            chain = []
            x = start  & 255   
            y = start  >> 8  
            chain += [255, 0, self.wave(self.speed/2), 255, 1, x, y] #speed/2 for 1/16rev
            chain += [255, 0, self.wave(self.speed), 255, 3]  #Loop forever but triggered
            self.pi.wave_chain(chain)  # Transmit chain.
            self.tick = self.pi.get_current_tick()  #tick at motor start
            delay = self.pulley_ratio/self.speed  #normal delay for one turn in seconds
            self.triggered = True
            isSet = self.triggerEvent.wait(2*delay) #No more than two turns
            if not isSet :
                self.pi.wave_tx_stop()
                msgheader = {'type':HEADER_MESSAGE, 'msg': 'Warning: trigger not detected'}
                self.queue.put(msgheader)
                print(" Trigger not detected", flush=True)
            self.triggered = False
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
