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
from picamera import array

import pigpio

from recalibrate import *

sys.path.append('../Common')
from Constants import *
from MessageSocket import *
from TelecineMotor import *

## Todo More object oriented and avoid globals !

initSettings = ("sensor_mode",)
controlSettings = ("awb_mode","awb_gains","shutter_speed","brightness","contrast","saturation", "framerate","exposure_mode","iso", "exposure_compensation", "zoom","meter_mode")
addedSettings = ("bracket_steps","use_video_port", "bracket_dark_coefficient", "bracket_light_coefficient","capture_method", "shutter_speed_wait", "shutter_auto_wait","pause_pin","pause_level","auto_pause","resize","doResize")
motorSettings = ("speed","pulley_ratio","steps_per_rev","ena_pin","dir_pin","pulse_pin","trigger_pin","capture_speed","play_speed","ena_level","dir_level","trigger_level", "after_trigger")
readOnlySettings = ("analog_gain", "digital_gain")
commandSock = None
imageSock = None
listenSock = None
camera = None
queue = None
captureEvent = None
restartEvent = None
motor = None
pi = None
triggerEvent= None
exitFlag = False

sendImageThread = None
captureImageThread = None

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
        self.pause_pin=25
        self.pause_level=1
        self.auto_pause = False
        self.capturing = False
        self.pausing = False
        self.doROI = False
        self.doResize = False
        self.resize = None
        self.roi = None
        self.maxFps = 0
        pi.set_mode(self.pause_pin, pigpio.INPUT)

        if self.pause_level == 0 :
            pi.set_pull_up_down(self.pause_pin, pigpio.PUD_UP)
        else :
            pi.set_pull_up_down(self.pause_pin, pigpio.PUD_DOWN)
        pi.set_glitch_filter(self.pause_pin, 300000)
        self.triggerCallback = pi.callback(self.pause_pin, pigpio.EITHER_EDGE, self.pause)
        
    def pause(self, gpio,level,  tick ) :
        if self.auto_pause :
            if self.pause_level == level :
                restartEvent.clear()
            else :
                restartEvent.set()

#BASIC repeat: frame capture and send
#ON_FRAME repeat: frame capture and send motor advance until trigger
#ON-TRIGGER Motor Advance  Repeat: Wait Trigger Capture Send   
#Warning very sensitive code !!
    def putHeader(self,bracket) :
        header = {'type':HEADER_IMAGE}
        header['count'] = self.frameCounter
        header['bracket'] = bracket
        header['shutter'] = self.exposure_speed
        header['gains'] = self.awb_gains
        header['analog_gain']=self.analog_gain
        header['digital_gain']=self.digital_gain
        queue.put(header)
        
    def captureGenerator(self):
        stream = BytesIO()
        for foo in range(self.shutter_auto_wait) : 
            yield stream
            stream.seek(0)
            stream.truncate(0)
        if self.capture_method == CAPTURE_BASIC :
            pass
        elif self.capture_method == CAPTURE_ON_FRAME :
            motor.direction = MOTOR_FORWARD     
        elif self.capture_method == CAPTURE_ON_TRIGGER :
            motor.direction = MOTOR_FORWARD     
            motor.advance()
        header = {'type':HEADER_IMAGE}

        while captureEvent.isSet():
            if not restartEvent.isSet() :
                msgheader = {'type':HEADER_MESSAGE, 'msg': 'Pausing capture'}
                queue.put(msgheader)
                if self.capture_method == CAPTURE_ON_TRIGGER :
                    motor.stop()
                restartEvent.wait()
                msgheader = {'type':HEADER_MESSAGE, 'msg': 'Resuming capture'}
                if self.capture_method == CAPTURE_ON_TRIGGER :
                    motor.advance()
                queue.put(msgheader)
            if self.capture_method == CAPTURE_ON_TRIGGER :
                triggerEvent.wait()
            elif self.capture_method == CAPTURE_ON_FRAME :
                motor.advanceUntilTrigger()
#bypass old frames if not in preview
            if not self.capture_method == CAPTURE_BASIC :
                for foo in range(self.shutter_auto_wait) : 
                    yield stream
                    stream.seek(0)
                    stream.truncate(0)
#Wait if queue is full          
            if queue.qsize() > 20 :
                if self.capture_method == CAPTURE_ON_TRIGGER :
                    motor.stop()
                msgheader = {'type':HEADER_MESSAGE, 'msg': 'Capture paused'}
                queue.put(msgheader)
                print('Warning queue > 20\n', flush=True)
                while queue.qsize() > 1 :
                      time.sleep(1)
                msgheader = {'type':HEADER_MESSAGE, 'msg': 'Capture resumed'}
                queue.put(msgheader)
                if self.capture_method == CAPTURE_ON_TRIGGER :
                    motor.advance()
            self.frameCounter = self.frameCounter + 1 

#No bracket
            if self.bracket_steps == 1 :
                yield stream
                stream.seek(0)
                self.putHeader(0)
                queue.put(stream.getvalue())
                stream.truncate(0)
            else :
#Do braket
#First shot image #3 Normal (auto) 
#Second shot image #2 light auto*light coeff
#Third shot image #1 dark auto*dark coeff
##                coef = (self.bracket_light_coefficient, self.bracket_dark_coefficient,0) #normal clair sombre
##                autoExposureSpeed = self.exposure_speed              #First shoot
##                for i in range(self.bracket_steps) :
##                    exposureSpeed =  int(autoExposureSpeed * coef[i]) #Exposure for next shot last is 0 (auto)
##                    self.shutter_speed = exposureSpeed
##                    yield stream                        
##                    stream.seek(0)
##                    self.putHeader(self.bracket_steps - i) #First is 3 Last  is 1
##                    queue.put(stream.getvalue())
##                    stream.truncate(0)
##                    for foo in range(self.shutter_speed_wait) :
##                        yield stream
##                        stream.seek(0)
##                        stream.truncate(0)

#Normal
                autoExposureSpeed = self.exposure_speed              #First shoot
                self.shutter_speed = int(autoExposureSpeed*self.bracket_light_coefficient)
                self.exposure_mode='off' #lock the gains
                yield stream                        
                stream.seek(0)
                self.putHeader(3) #First is 3 Last  is 1
                queue.put(stream.getvalue())
                stream.truncate(0)
#Overexposed
                for foo in range(self.shutter_speed_wait) :
                    yield stream
                    stream.seek(0)
                    stream.truncate(0)
                self.shutter_speed = int(autoExposureSpeed*self.bracket_dark_coefficient)
                yield stream                        
                stream.seek(0)
                self.putHeader(2) #First is 3 Last  is 1
                queue.put(stream.getvalue())
                stream.truncate(0)
#Underexposed
                for foo in range(self.shutter_speed_wait) :
                    yield stream
                    stream.seek(0)
                    stream.truncate(0)
                self.shutter_speed = autoExposureSpeed  #return to normal
                yield stream                        
                stream.seek(0)
                self.putHeader(1) #First is 3 Last  is 1
                queue.put(stream.getvalue())
                stream.truncate(0)
                for foo in range(self.shutter_speed_wait) :
                    yield stream
                    stream.seek(0)
                    stream.truncate(0)
                self.exposure_mode='auto' #Return to auto
                self.shutter_speed = 0
        if self.capture_method == CAPTURE_ON_TRIGGER :
            motor.stop()

    def captureSequence(self) :
        self.capturing = True
        self.frameCounter = 0
        if self.capture_method == CAPTURE_ON_TRIGGER :
            self.calcMaxFps(50)
        startTime = time.time()
        resize = self.resolution
        if self.doResize == True :
            resize = (self.resize[0], self.resize[1])
        self.capture_sequence(self.captureGenerator(), format="jpeg", use_video_port=self.use_video_port, resize=resize)
        stopTime = time.time()
        fps = float(self.frameCounter/(stopTime-startTime))
        spf = 1./fps
        msg = "Capture terminated    Count %i    fps %f spf %f"%(self.frameCounter , fps, spf)
        header = {'type':HEADER_MESSAGE, 'msg':msg}
        queue.put(header)
        while queue.qsize() > 1 :
            time.sleep(1)
        self.capturing=False

#Try to evaluate the maximum framerate        
    def dummyGenerator(self, count):
        startTime = time.time()
        stream = BytesIO()
        for i in range (count) :
            yield stream
            stream.seek(0)
            image = stream.getvalue()
            stream.truncate(0)
        stopTime = time.time()
        fps = float(count/(stopTime-startTime))
        self.framerate = fps
        spf = 1./fps
        msg = "Maximum framerate    Count %i    fps %f spf %f" % (count , fps, spf)
        header = {'type':HEADER_MESSAGE, 'msg':msg}
        queue.put(header)
        
    
    def doMaxFps(self, count) :
        resize = self.resolution
        if self.doResize == True :
            resize = (self.resize[0], self.resize[1])
        self.capture_sequence(self.dummyGenerator(count), format="jpeg", use_video_port=True,resize=resize)
    
    def doMaxSpeed(self) :
        doMaxFps()
        if self.bracket_steps != 1 : #Reduce motor speed
            frames = self.shutter_auto_wait + 4.*self.shutter_speed_wait + 1 #un peu de marge
        else :
            frames = self.shutter_auto_wait + 1
        projectorSpeed = self.framerate/ frames  #rev per seconds
        motor.speed = motor.pulley_ratio * projectorSpeed
        print(self.maxFps)
        print(frames)
        print(projectorSpeed)
        msg = "Calculated motor speed %f"%(motor.speed)
        headermsg = {'type':HEADER_MESSAGE, 'msg':msg}
        queue.put(headermsg)
    
        
    def printSettings() :
        print("exposure_mode", self.exposure_mode)
        print("exposure_speed", self.exposure_speed)
        print("shutter_speed", self.shutter_speed)
        print("analog_gain", self.analog_gain)
        print("digital_gain", self.digital_gain)
        print("iso", self.iso)
        print("resolution", self.resolution)
        print("zoom", self.zoom)
        
    def captureImage(self) :
        while self.capturing :
            time.sleep(1)
        resize = self.resolution
        if self.doResize == True :
            resize = (self.resize[0], self.resize[1])
        stream = BytesIO()
        camera.capture(stream, format="jpeg", quality=90, use_video_port=self.use_video_port, resize=resize)
        stream.seek(0)
        image = stream.getvalue()
        header = {'type':HEADER_IMAGE, 'count':motor.frameCounter, 'bracket':0, 'shutter':self.exposure_speed,'gains':self.awb_gains,'analog_gain':self.analog_gain,'digital_gain':self.digital_gain}
        queue.put(header)
        queue.put(image)

    def captureBgr(self, type, count) :
        for i in range(count) :
            header = {'type':type, 'shutter':self.exposure_speed, 'gains':self.awb_gains, 'count':count, 'num':i}
            queue.put(header)
            image = self.get_bgr_image()
            queue.put(image)


    def get_rgb_image(self):
        resize = self.resolution
        if self.doResize == True :
            resize = (self.resize[0], self.resize[1])
        print("Resize:", resize, " Doresize", self.doResize)
        with picamera.array.PiRGBArray(camera,  size=resize) as output:
            camera.capture(output, format='rgb', resize=resize, use_video_port=True)
            return output.array

    def get_bgr_image(self):
        resize = self.resolution
        if self.doResize == True :
            resize = (self.resize[0], self.resize[1])
        print("Resize:", resize, " Doresize", self.doResize)
        with picamera.array.PiRGBArray(self,  size=resize) as output:
            self.capture(output, format='bgr', resize=resize, use_video_port=True)
            return output.array
        
    def get_bgr_mean(self, num) :
        bgr_image  = self.get_bgr_image().astype(dtype=np.float)
        for j in range(num-1):
            bgr_image = bgr_image + self.get_bgr_image()
        bgr_image = bgr_image / num
        return bgr_image

    def whiteBalance(self) :
        rgb_image  = self.get_rgb_image()
        rgb_image  = self.get_rgb_image()
        print(np.max(rgb_image))
        channel_means = np.mean(np.mean(rgb_image, axis=0, dtype=np.float), axis=0)
        print(channel_means[0])
        print(channel_means[1])
        print(channel_means[2])
        old_gains = camera.awb_gains
        return (channel_means[1]/channel_means[0] * old_gains[0], channel_means[1]/channel_means[2]*old_gains[1])

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
                elif isinstance(object, np.ndarray) :
                    imageSock.sendArray(object)
                else :
                    imageSock.sendMsg(object) #Image buffer
            while queue.qsize() > 1 :
                object = queue.get()
                imageSock.sendObject(object)
        finally :
            if imageSock != None:
                imageSock.close()
        print('SendImageThread terminated')
           
def openCamera(mode, resolution, calibrationMode, hflip,vflip) :
    cam = None
    if calibrationMode ==  CALIBRATION_TABLE:
        try :
            lst = np.load("calibrate_test.npz", allow_pickle=True)
            cam = TelecineCamera(sensor_mode = mode, lens_shading_table = lst['lens_shading_table'])
        except Exception as ex:
            try :
                lst = np.load("calibrate.npz", allow_pickle=True)
                cam = TelecineCamera(sensor_mode = mode, lens_shading_table = lst['lens_shading_table'])
            except Exception as ex:
                print(ex)
                pass

    if cam == None :
        cam = TelecineCamera(sensor_mode = mode)
    if resolution != None :
        cam.resolution = resolution
    try:
        npz = np.load("camera.npz", allow_pickle=True)
        setSettings(cam, npz['control'][()])
        try :
            setSettings(cam, npz['added'][()])
        except :
            pass
    except :
        pass
    
    cam.sharpness=10
    cam.hflip = hflip
    cam.vflip = vflip
    if calibrationMode == CALIBRATION_FLAT :
        lens_shading_table = np.zeros(cam._lens_shading_table_shape(), dtype=np.uint8) + 32
        cam.lens_shading_table = lens_shading_table
#        cam.sharpness=10
#Start capture Thread
    exitFlag = False
    captureImageThread = CaptureImageThread()
    captureImageThread.start()
    return cam

#To properly close the camera we shoud terminate the capture thread
def closeCamera() :
    global camera
    exitFlag = True
    saveCameraSettings()
    camera.close()
    camera = None

def calibrateCamera(hflip, vflip) :
    if camera != None :
        closeCamera
##    header = {'type':HEADER_MESSAGE, 'msg':'Calibrating please wait'}
##    queue.put(header)
    lens_shading_table = generate_lens_shading_table_closed_loop(n_iterations=5, hflip=hflip, vflip=vflip)
    np.savez('calibrate.npz',   lens_shading_table = lens_shading_table)
##    header = {'type':HEADER_MESSAGE, 'msg':'Calibrate done'}
##    queue.put(header)


    
   
def saveCameraSettings() :
    if camera != None :
        np.savez('camera.npz', init = getSettings(camera, initSettings) , \
             control=getSettings(camera, controlSettings), \
             added=getSettings(camera, addedSettings))

def saveMotorSettings() :
    if motor != None :        
        np.savez('motor.npz', motor=getSettings(motor, motorSettings))
try:
    pi = pigpio.pi()
    if not pi.connected:
        print('Launch pigpio daemon !')
        exit()
    
    queue = Queue() #sending queue
    triggerEvent = Event()
    motor = TelecineMotor(pi, queue)
    motor.triggerEvent = triggerEvent
    try :
        npz = np.load("motor.npz", allow_pickle=True)
        setSettings(motor, npz['motor'][()])
    except Exception as e :
        print(e)

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
    restartEvent = Event()
    restartEvent.set()
    while True:
        request = commandSock.receiveObject()
        if request == None :
            break
        command = request[0]
        print('%s'%commands[command],flush=True)
        if command == TAKE_IMAGE :
            camera.captureImage()
        elif command == TAKE_BGR:
            camera.captureBgr(request[1], request[2])
        elif command == GET_CAMERA_SETTINGS:
            settings = getSettings(camera, initSettings+controlSettings+addedSettings+readOnlySettings)
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
        elif command == SET_MOTOR_SETTING:
            setSettings(motor, request[1]) #Just for speed no need to change pigpio
            motor.updateSettings()
        elif command == SAVE_SETTINGS :
            saveCameraSettings()
            saveMotorSettings()
        elif command == START_CAPTURE:
            motor.direction = MOTOR_FORWARD
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
        elif command == OPEN_CAMERA :
            camera = openCamera(request[1],request[2], request[3], request[4], request[5]) #mode, resolution, calibrationMode, hflip, vflip
        elif command == CLOSE_CAMERA :
             closeCamera()
        elif command == CALIBRATE_CAMERA :
            calibrateCamera(request[1],request[2])  #hflip vflip
            commandSock.sendObject('Calibrate done')
        elif command == MOTOR_ON_TRIGGER :
            motor.direction = MOTOR_FORWARD
            motor.advanceUntilTrigger()
        elif command == MOTOR_ON :
            motor.on()
        elif command == MOTOR_OFF :
            saveMotorSettings()
            motor.off()
        elif command == CALIBRATE_MOTOR :
            motor.calibrate()
        elif command == MAX_FPS :
            camera.doMaxFps(100)
        elif command == MAX_SPEED :
            camera.doMaxSpeed()
        elif command == WHITE_BALANCE :
            gains = camera.whiteBalance()
            commandSock.sendObject(gains)
        elif command == PAUSE_CAPTURE :
            if restartEvent.isSet() :
                restartEvent.clear()   #pause
            else :
                restartEvent.set()     #Restart
        else :
            pass            
       
finally:
    if captureImageThread != None :
        exitFlag = True  #Stop Capture Thread
        if restartEvent != None :
            if not restartEvent.isSet() :
                retstartEvent.set()  #Restart capture generator if puased
        if captureEvent != None :
            captureEvent.clear() #stop capture generator
        captureImageThread.join()
    if sendImageThread != None:
        queue.put({'type':HEADER_STOP}) #Stop sending thread
        sendImageThread.join()
    if motor != None :
        saveMotorSettings()
        motor.close()
    if pi != None:
        pi.stop()
    if camera != None :
        closeCamera()
    if commandSock != None:
        commandSock.close()
    if listenSock != None:
        listenSock.close()
