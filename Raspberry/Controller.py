import socket
from struct import *
import copy
import time
import sys
from threading import Thread, Event
from queue import Queue
from io import BytesIO
from fractions import Fraction 

import numpy as np
from picamera import PiCamera
import pigpio

from recalibrate import *

sys.path.append('../Common')
from Constants import *
from MessageSocket import *
from TelecineMotor import *

## Todo More object oriented and avoid globals !

initSettings = ("sensor_mode",)
controlSettings = ("awb_mode","awb_gains","shutter_speed","analog_gain","digital_gain","brightness","contrast","saturation", "framerate","exposure_mode","iso", "exposure_compensation")
addedSettings = ("bracket_steps","use_video_port", "bracket_dark_coefficient", "bracket_light_coefficient","capture_method", "shutter_speed_wait", "shutter_auto_wait")
motorSettings = ("speed","pulley_ratio","steps_per_rev","ena_pin","dir_pin","pulse_pin","trigger_pin","capture_speed","play_speed")

commandSock = None
imageSock = None
listenSock = None
camera = None
queue = None
captureEvent = None
motor = None
pi = None
triggerEvent= None
exitFlag = False

def getSetting(object, key):
    setting = getattr(object, key)
    if key == 'framerate' :
        setting = Fraction(setting[0],setting[1])
    elif key == 'resolution' or key == 'MAX_RESOLUTION' :
        setting = (setting[0],setting[1])
    return setting

def getSettings(object, keys):
    settings = {}
    for k in keys :
        value = getattr(object, k)
        if k == 'framerate' :
           value = Fraction(value[0],value[1])
        settings[k] = value
    return settings

def setSettings(object, settings) :
    for k in settings : 
        setattr(object, k, settings[k])
        
       
class TelecineCamera(PiCamera) :
    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bracket_steps = 1
        self.shutter_speed_wait = 4
        self.shutter_auto_wait = 8
        self.use_video_port = True
        self.bracket_dark_coefficient = 1.
        self.bracket_light_coefficient = 1.
        self.capture_method =CAPTURE_ON_FRAME


#BASIC repeat: frame capture and send
#ON_FRAME repeat: frame capture and send motor advance until trigger
#ON-TRIGGER Motor Advance  Repeat: Wait Trigger Capture Send   
#Warning very sensitive code !!
        
    def captureGenerator(self):
        stream = BytesIO()
        header = {'type':HEADER_IMAGE}
        for foo in range(self.shutter_auto_wait) : 
            yield stream
            stream.seek(0)
            stream.truncate(0)
        if self.capture_method == CAPTURE_BASIC :
            pass
        elif self.capture_method == CAPTURE_ON_FRAME :
            motor.direction = MOTOR_FORWARD     
        elif self.capture_method == CAPTURE_ON_TRIGGER :
            if self.bracket_steps != 1 : #Reduce motor speed
                frames = 3*self.shutter_auto_wait + self.shutter_speed_wait
                motor.speed = self.framerate / frames
                print('Capture on trigger with bracket reducing motor speed to', motor.speed)
            motor.direction = MOTOR_FORWARD     
            motor.advance()
        while captureEvent.isSet():
            if self.capture_method == CAPTURE_ON_TRIGGER :
                triggerEvent.wait()
            elif self.capture_method == CAPTURE_ON_FRAME :
                motor.advanceUntilTrigger()
            self.awb_mode = 'auto'
            if self.bracket_steps != 1 :
                for foo in range(self.shutter_auto_wait) : 
                    yield stream
                    stream.seek(0)
                    stream.truncate(0)
#Wait if queue is full          
            if queue.qsize() > 50 :
                if self.capture_method == CAPTURE_ON_TRIGGER :
                    motor.stop()
                print('Warning queue > 50')
                while queue.qsize() > 1 :
                      time.sleep(1)
                if self.capture_method == CAPTURE_ON_TRIGGER :
                    motor.advance()
            header['count'] = self.frameCounter
            self.frameCounter = self.frameCounter + 1 
            autoExposureSpeed = self.exposure_speed 
            if self.bracket_steps == 1 :
                header['bracket'] = 0
                header['shutter'] = autoExposureSpeed
                yield stream
                stream.seek(0)
                queue.put(copy.deepcopy(header))
                queue.put(stream.getvalue())
                stream.truncate(0)
            else :
#First shot image #3 Normal (auto) 
#Second shot image #2 light auto*light coeff
#Third shot image #1 dark auto*dark coeff
                coef = (self.bracket_light_coefficient, self.bracket_dark_coefficient,0) #normal clair sombre
                exposureSpeed = autoExposureSpeed              #First shoot
                for i in range(self.bracket_steps) :
                    header['bracket'] = self.bracket_steps - i  #First is 3 Last  is 1
                    header['shutter'] = exposureSpeed
                    queue.put(copy.deepcopy(header))
                    exposureSpeed =  int(autoExposureSpeed * coef[i]) #Exposure for next shot last is 0 (auto)
                    self.shutter_speed = exposureSpeed
                    self.awb_mode = 'off'
                    yield stream                        
                    stream.seek(0)
                    queue.put(stream.getvalue())
                    stream.truncate(0)
                    for foo in range(self.shutter_speed_wait) :
                        yield stream
                        stream.seek(0)
                        stream.truncate(0)
        if self.capture_method == CAPTURE_ON_TRIGGER :
            motor.stop()
                    

    def captureSequence(self) :
        self.frameCounter = 0
        startTime = time.time()
        self.capture_sequence(self.captureGenerator(), format="jpeg", use_video_port=self.use_video_port)
        stopTime = time.time()
        fps = float(self.frameCounter/(stopTime-startTime))
        msg = "Capture terminated    Count %i    fps %f \n"%(self.frameCounter , fps)
        header = {'type':HEADER_MESSAGE, 'msg':msg}
        queue.put(header)
        
    def captureAndLuma(self, exposure) :
        stream = BytesIO()
        self.shutter_speed = int(exposure)
        time.sleep(0.5)
        camera.capture(stream, format="jpeg", quality=90, use_video_port=self.use_video_port)
        stream.seek(0)
        image = stream.getvalue()
        jpeg = np.frombuffer(image, np.uint8,count = len(image)) 
        rgb = cv2.imdecode(jpeg, 1)   #Jpeg decode
        luma = rgb.mean()
        return luma
    
    def calibrateBetween(self, lumas, exposures, i, j) :
        if j-i > 2 :
            k = int((i+j)/2)
            luma = lumas[k]  #but à atteindre
            e1 = exposures[i]
            e2 = exposures[j-1]
            print('For luma:', luma, ' Between:', i, ' ', e1, ' and ', j, ' ', e2)
            inter = (e2-e1)/100 + 1
            while e2-e1 > inter :
                e = (e1 + e2)/2.
                l = self.captureAndLuma(e)
                if l > luma :
                    e2 = e
                else :
                    e1 = e
            exposures[k] = e2
            self.calibrateBetween(lumas, exposures, i, k+1)
            self.calibrateBetween(lumas, exposures, k, j)
            
            
    def calibrateHDR(self, frames) :
        stream = BytesIO()
        lumas = [luma for luma in range(0,255,10)]
        exposures = [0]*len(lumas)
        exposures[0] = 1
        exposures[-1] = 1000000./self.framerate
        self.calibrateBetween(lumas, exposures, 0, len(lumas))
        print(exposures)
        for i,e in enumerate(exposures) :
            self.shutter_speed = int(e)
            time.sleep(0.5)
            camera.capture(stream, format="jpeg", quality=90, use_video_port=self.use_video_port)
            stream.seek(0)
            image = stream.getvalue()
            header = {'type':HEADER_HDR, 'count':0, 'bracket':len(lumas)-i, 'shutter':self.exposure_speed}
#            header = {'type':HEADER_IMAGE, 'count':0, 'bracket':0, 'shutter':self.exposure_speed}
            queue.put(copy.deepcopy(header))
            queue.put(image)
            stream.truncate(0)

        
    def captureImage(self) :
        stream = BytesIO()
        print(self.use_video_port)
        camera.capture(stream, format="jpeg", quality=90, use_video_port=self.use_video_port)
        stream.seek(0)
        image = stream.getvalue()
        header = {'type':HEADER_IMAGE, 'count':motor.frameCounter, 'bracket':0, 'shutter':self.exposure_speed}
        queue.put(header)
        queue.put(image)
#end Camera class
        
class CaptureImageThread(Thread):
    def __init__(self,):
        Thread.__init__(self, daemon=True)

    def run(self) :
        print('CaptureThread started')
        while exitFlag == False:
            captureEvent.wait()
            camera.captureSequence()
        print('CaptureThread terminated')

class SendImageThread(Thread):
    def __init__(self,):
        Thread.__init__(self, daemon=True)

    def run(self) :
        print('SendImageThread started')
        try :
            while True:
                object = queue.get()
                if isinstance(object, dict) :      #Header object
                    imageSock.sendObject(object)
                    if object['type'] == HEADER_STOP :
                        break;
                else :
                    imageSock.sendMsg(object)
        finally :
            if imageSock != None:
                imageSock.close()
        print('SendImageThread terminated')
           
def openCamera(mode, resolution, useCalibration) :
    cam = None
    if useCalibration :
        try :
            lst = np.load("calibrate.npz")
            cam = TelecineCamera(sensor_mode = mode, lens_shading_table = lst['lens_shading_table'])
        except Exception as ex:
            pass
    if cam == None :
        cam = TelecineCamera(sensor_mode = mode)
    if resolution != None :
        cam.resolution = resolution
    print(cam.framerate)
    print(cam.resolution)
    npz = np.load("telecine.npz")
    try:
        setSettings(cam, npz['control'][()])
    except :
        pass
    try :
        setSettings(cam, npz['added'][()])
    except :
        pass
#Start capture Thread
    exitFlag = False
    captureImageThread = CaptureImageThread()
    captureImageThread.start()
    return cam

#To properly close the camera we shoud terminate the capture thread
def closeCamera() :
    exitFlag = True 
    camera.close()

def calibrateCamera() :
    if camera != None :
        closeCamera
    lens_shading_table = generate_lens_shading_table_closed_loop(n_iterations=5)
    np.savez('calibrate.npz',   lens_shading_table = lens_shading_table)

   
def saveSettings() :
    if camera != None and motor != None :
        np.savez('telecine.npz', init = getSettings(camera, initSettings) , \
             control=getSettings(camera, controlSettings), \
             added=getSettings(camera, addedSettings), \
             motor=getSettings(motor, motorSettings))
            
try:
    pi = pigpio.pi()
    if not pi.connected:
        print('Not connected')
        exit()
    
    queue = Queue() #sending queue
    triggerEvent = Event()
    motor = TelecineMotor(pi, queue)
    motor.triggerEvent = triggerEvent
    try :
        npz = np.load("telecine.npz")
        setSettings(motor, npz['motor'][()])
    except :
        pass

    time.sleep(0.1)
    listenSock = socket.socket()
    listenSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    listenSock.bind(('0.0.0.0', 8000))
    listenSock.listen(0)
    commandSock = MessageSocket(listenSock.accept()[0])
    print("Command sock connected")
    listenSock.listen(0)
    imageSock = MessageSocket(listenSock.accept()[0])
    print("Image sock connected")

# Send image Thread
    sendImageThread = SendImageThread()
    sendImageThread.start()

#Capture image Thread
    captureEvent = Event()
    
    while True:
        request = commandSock.receiveObject()
        if request == None :
            break
        command = request[0]
        print('Command:', command)
        if command == TAKE_IMAGE :
            camera.captureImage()
        elif command == GET_CAMERA_SETTINGS:
            settings = getSettings(camera, initSettings+controlSettings+addedSettings)
            commandSock.sendObject(settings)
        elif command == GET_CAMERA_SETTING:
            setting = getSetting(camera, request[1])
            commandSock.sendObject(setting)
        elif command == GET_MOTOR_SETTINGS:
            settings = getSettings(motor, motorSettings)
            commandSock.sendObject(settings)
        elif command == SET_CAMERA_SETTINGS:
            setSettings(camera, request[1])
        elif command == SET_MOTOR_SETTINGS:
            setSettings(motor, request[1])
        elif command == SAVE_SETTINGS :
            saveSettings()
        elif command == START_CAPTURE:
            captureEvent.set()
        elif command == STOP_CAPTURE:
            captureEvent.clear()
        elif command == TERMINATE:
            break
        elif command == MOTOR_ADVANCE :
            motor.direction = request[1]
            motor.advance()  #0 forward 1 backward
        elif command == MOTOR_ADVANCE_ONE :
            motor.direction = request[1]
            motor.advanceCounted()
        elif command == MOTOR_STOP :
            motor.stop()
            motor.advanceUntilTrigger()
        elif command == CALIBRATE_HDR :
            camera.calibrateHDR(request[1])
        elif command == OPEN_CAMERA :
            camera = openCamera(request[1],request[2], request[3])
        elif command == CLOSE_CAMERA :
             closeCamera()
        elif command == CALIBRATE_CAMERA :
            calibrateCamera()
            commandSock.sendObject('Calibrate done')
        else :
            pass            
       
finally:
    saveSettings()
    exitFlag = True
    if captureEvent != None :
        captureEvent.clear() #stop capture
    if queue != None :
        queue.put({'type':HEADER_STOP}) #Stop sending thread
    if motor != None :
        motor.close()
    if pi != None:
        pi.stop()
    if camera != None :
        closeCamera()
    if commandSock != None:
        commandSock.close()
    if listenSock != None:
        listenSock.close()
