import socket
import logging
from struct import *
import sys
import time
import numpy as np
from fractions import Fraction
import os

from PyQt5.QtWidgets import QDialog, QApplication, QSpinBox, QFileDialog
from PyQt5.QtGui import QImage, QPainter,QPixmap
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, Qt

from TelecineDialogUI import Ui_TelecineDialog
from ImageThread import ImageThread

sys.path.append('../Common')
from Constants import *
from MessageSocket import *

localSettings = ('ip_pi', 'root_directory','hflip', 'vflip', 'mode', 'tape', 'clip')

#Generic methods to set/get object attributes from a dictionary
def getSettings(object, keys):
    settings = {}
    for k in keys :
        value = getattr(object, k)
        settings[k] = value
    return settings

def setSettings(object, settings) :
    for k in settings : 
        setattr(object, k, settings[k])        


class TelecineDialog(QDialog, Ui_TelecineDialog):

    def __init__(self):
        super(TelecineDialog, self).__init__()
        self.setupUi(self)
        self.sock = None
        self.connected = False
        self.paused = False
        self.saveTofile = False
        self.directory = ''
        self.imageThread = None
        self.connectButton.setStyleSheet("background-color: red")
        self.ip_pi = ''
        self.hflip = False
        self.vflip = False
        self.tape = 1
        self.clip = 1
        self.mode = 2
        self.resolution = None
        self.cameraVersion = ''
        self.root_directory = None
        self.captureStopButton.setEnabled(False)
        self.capturePauseButton.setEnabled(False)
        self.cameraControlGroupBox.setEnabled(False)
        self.frameProcessingGroupBox.setEnabled(False)
        self.motorControlGroupBox.setEnabled(False)
        self.cameraSettingsGroupBox.setEnabled(False)
        self.motorSettingsGroupBox.setEnabled(False)
        self.motorOnGroupBox.setEnabled(False)
        self.cameraGroupBox.setEnabled(False)
        self.closeCameraButton.setEnabled(False)
        self.motorStopButton.setEnabled(False)
        self.motorOffButton.setEnabled(False)
        self.onTriggerButton.setEnabled(True)
        self.autoPauseCheckBox.setEnabled(False)
        self.lensAnalyseButton.setEnabled(False)
        self.calibrateLocalButton.setEnabled(False)
        self.imageDialog = None
        self.plotDialog = None
        self.whiteBalanceButton.setEnabled(False)

        
#Lamp
    def setLamp(self):
        if self.lampCheckBox.isChecked() :
            self.sock.sendObject((SET_LAMP, LAMP_ON))
        else :
            self.sock.sendObject((SET_LAMP, LAMP_OFF))
        
#Motor Control
    def motorOn(self) :
        self.sock.sendObject((MOTOR_ON,))
        self.motorControlGroupBox.setEnabled(True)
        self.motorSettingsGroupBox.setEnabled(False)
        self.motorOnButton.setEnabled(False)
        self.motorOffButton.setEnabled(True)
        self.motorCalibrateButton.setEnabled(True)

    def motorOff(self) :
        self.sock.sendObject((MOTOR_OFF,))
        self.motorControlGroupBox.setEnabled(False)
        self.motorSettingsGroupBox.setEnabled(True)
        self.motorOnButton.setEnabled(True)
        self.motorOffButton.setEnabled(False)
        self.motorCalibrateButton.setEnabled(False)

    def forwardOne(self):
        self.setMotorSettings({'speed':self.motorSpeedBox.value()})
        self.sock.sendObject((MOTOR_ADVANCE_ONE,MOTOR_FORWARD))
    def backwardOne(self) :
        self.setMotorSettings({'speed':self.motorSpeedBox.value()})
        self.sock.sendObject((MOTOR_ADVANCE_ONE,MOTOR_BACKWARD))
    def forward(self):
        self.setMotorSettings({'speed':self.motorSpeedBox.value()})
        self.sock.sendObject((MOTOR_ADVANCE, MOTOR_FORWARD))
        self.motorStopButton.setEnabled(True)
        self.forwardOneButton.setEnabled(False)
        self.backwardOneButton.setEnabled(False)
        self.forwardButton.setEnabled(False)
        self.backwardButton.setEnabled(False)
        self.motorOnTriggerButton.setEnabled(False)
    def backward(self):
        self.setMotorSettings({'speed':self.motorSpeedBox.value()})
        self.sock.sendObject((MOTOR_ADVANCE, MOTOR_BACKWARD))
        self.motorStopButton.setEnabled(True)
        self.forwardOneButton.setEnabled(False)
        self.backwardOneButton.setEnabled(False)
        self.forwardButton.setEnabled(False)
        self.backwardButton.setEnabled(False)
        self.motorOnTriggerButton.setEnabled(False)
    def motorStop(self):
        self.sock.sendObject((MOTOR_STOP,))
        self.motorStopButton.setEnabled(False)
        self.forwardOneButton.setEnabled(True)
        self.backwardOneButton.setEnabled(True)
        self.forwardButton.setEnabled(True)
        self.backwardButton.setEnabled(True)
        self.motorOnTriggerButton.setEnabled(True)

    def motorOnTrigger(self):
        self.setMotorSettings({'speed':self.motorSpeedBox.value()})
        self.sock.sendObject((MOTOR_ON_TRIGGER,))

    def motorCalibrate(self):
        self.setMotorSettings({'speed':self.motorSpeedBox.value()})
        self.sock.sendObject((CALIBRATE_MOTOR,))

    def setMotorSettings(self, settings) :
        self.sock.sendObject((SET_MOTOR_SETTINGS, settings))
        
    def setMotorInitSettings(self) :
        self.sock.sendObject((SET_MOTOR_SETTINGS, {\
            'steps_per_rev':self.stepsPerRevBox.value(),\
            'pulley_ratio':self.pulleyRatioBox.value(),\
            'ena_pin':int(self.enaEdit.text()),\
            'dir_pin':int(self.dirEdit.text()),\
            'pulse_pin':int(self.pulseEdit.text()),\
            'trigger_pin':int(self.triggerEdit.text()),\
            'dir_level': 1 if self.dirLevelCheckBox.isChecked() else 0 ,\
            'ena_level': 1 if self.enaLevelCheckBox.isChecked() else 0, \
            'trigger_level': 1 if self.triggerLevelCheckBox.isChecked() else 0, \
            'after_trigger': 1 if self.afterTriggerCheckBox.isChecked() else 0 \
            }))



#Get and display motor settings
    def getMotorSettings(self) :
        self.sock.sendObject((GET_MOTOR_SETTINGS,))
        settings = self.sock.receiveObject()
        self.stepsPerRevBox.setValue(settings['steps_per_rev'])
        self.pulleyRatioBox.setValue(settings['pulley_ratio'])
        self.enaEdit.setText(str(settings['ena_pin']))
        self.dirEdit.setText(str(settings['dir_pin']))
        self.pulseEdit.setText(str(settings['pulse_pin']))
        self.triggerEdit.setText(str(settings['trigger_pin']))
        self.enaLevelCheckBox.setChecked(settings['ena_level'] == 1)
        self.dirLevelCheckBox.setChecked(settings['dir_level'] == 1)
#        self.pulseLevelCheckBox.setChecked(settings['pulse_level'] == 1)
        self.triggerLevelCheckBox.setChecked(settings['trigger_level'] == 1)
        self.afterTriggerCheckBox.setChecked(settings['after_trigger'] == 1)
        return settings

        
#Camera control
    def openCamera(self):
        self.mode = int(self.modeBox.value())  #0 automatic
        hres = 0
        vres = 0
        try :
            hres = int(self.hresLineEdit.text())
            vres = int(self.vresLineEdit.text())
        except:
            pass
        requestedResolution = None
        if hres!= 0 and vres!= 0 :
            requestedResolution = (hres, vres)
        self.hflip = self.hflipCheckBox.isChecked()
        self.vflip = self.vflipCheckBox.isChecked()
        calibrationMode = CALIBRATION_NONE
        if self.calibrateFlatButton.isChecked() :
            calibrationMode = CALIBRATION_FLAT
        elif self.calibrateTableButton.isChecked() :
            calibrationMode = CALIBRATION_TABLE
        self.sock.sendObject((OPEN_CAMERA, self.mode, requestedResolution, \
                             calibrationMode, self.hflip, self.vflip))
        maxResolution = self.getCameraSetting('MAX_RESOLUTION')
        if maxResolution[0] == 4056 :
            self.cameraVersion = 3  #HQ
        elif maxResolution[0] == 3280 :
            self.cameraVersion = 2
        else :
            self.cameraVersion = 1
        if hres== 0 and vres==0 and self.mode != 0 :
            if self.cameraVersion == 2 :
                res=V2_RESOLUTIONS[self.mode-1]
            elif self.cameraVersion == 1 :
                res=V1_RESOLUTIONS[self.mode-1]
            else :
                res=V3_RESOLUTIONS[self.mode-1]
            self.sock.sendObject((SET_CAMERA_SETTINGS, {'resolution':res}))
        self.cameraVersionLabel.setText('Picamera V' + str(self.cameraVersion))
        self.resolution = self.getCameraSetting('resolution')
        self.hresLineEdit.setText(str(self.resolution[0]))
        self.vresLineEdit.setText(str(self.resolution[1]))
        self.cameraControlGroupBox.setEnabled(True)
        self.frameProcessingGroupBox.setEnabled(True)
        self.cameraSettingsGroupBox.setEnabled(True)
        self.closeCameraButton.setEnabled(True)
        self.openCameraButton.setEnabled(False)
        self.calibrateButton.setEnabled(False)
        self.getCameraSettings()
        self.lensAnalyseButton.setEnabled(True)
        self.calibrateLocalButton.setEnabled(True)
        self.whiteBalanceButton.setEnabled(True)



    def closeCamera(self) :
        self.sock.sendObject((CLOSE_CAMERA,))
        self.cameraControlGroupBox.setEnabled(False)
        self.frameProcessingGroupBox.setEnabled(False)
        self.cameraSettingsGroupBox.setEnabled(False)
        self.closeCameraButton.setEnabled(False)
        self.openCameraButton.setEnabled(True)
        self.calibrateButton.setEnabled(True)
        self.lensAnalyseButton.setEnabled(False)
        self.calibrateLocalButton.setEnabled(False)
        self.whiteBalanceButton.setEnabled(False)

#Calibrate remote    
    def calibrate(self) :
        self.displayMessage("Calibrating please wait")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.sock.sendObject((CALIBRATE_CAMERA,self.hflipCheckBox.isChecked(), self.vflipCheckBox.isChecked()))
        done = self.sock.receiveObject()
        QApplication.restoreOverrideCursor()
        self.displayMessage("done")

#Calibrate Local        
    def calibrateLocal (self):
        self.displayMessage("Calibrating local please wait")
        self.setResize()
        self.sock.sendObject((TAKE_BGR,HEADER_CALIBRATE,1) )  #Calibrate on 1 image

    def doCalibrateLocal (self):
        self.imageThread.doCalibrate = self.calibrateLocalCheckBox.isChecked()
        
    def setWhiteBalance(self)  :      
        self.sock.sendObject((WHITE_BALANCE,))
        gains = self.sock.receiveObject()
        self.redGainBox.setValue(int(float(gains[0])*100.))
        self.blueGainBox.setValue(int(float(gains[1])*100.))

    def setEqualize(self) :
        self.claheCheckBox.setChecked(False)
        self.imageThread.clahe = False
        self.imageThread.equalize = self.equalizeCheckBox.isChecked()

    def setWB(self) :
        self.imageThread.wb = self.wbCheckBox.isChecked()

    def setClahe(self) :
        self.equalizeCheckBox.setChecked(False)
        self.imageThread.equalize = False
        self.imageThread.clahe = self.claheCheckBox.isChecked()
        self.imageThread.clipLimit = self.clipLimitBox.value()

#Modif possible durant capture
    def ROIwChanged(self) :
        width = self.ROIwBox.value()
        height = self.ROIhBox.value()
        ratio = self.resolution[0]/self.resolution[1]
        if self.keepRatioCheckBox.isChecked() :
            height = width/ratio
            self.ROIhBox.setValue(height)
        if self.centerCheckBox.isChecked() :
            x = int((self.resolution[0] - width)/2 )
            y = int((self.resolution[1] - height)/2 )
            self.ROIxBox.setValue(x) 
            self.ROIyBox.setValue(y)

    def ROIhChanged(self) :
        width = self.ROIwBox.value()
        height = self.ROIhBox.value()
        ratio = self.resolution[0]/self.resolution[1]
        if self.keepRatioCheckBox.isChecked() :
            width = height*ratio
            self.ROIwBox.setValue(width)
        if self.centerCheckBox.isChecked() :
            x = int((self.resolution[0] - width)/2 )
            y = int((self.resolution[1] - height)/2 )
            self.ROIxBox.setValue(x) 
            self.ROIyBox.setValue(y)

           
    def setROI(self) :
        roi = (self.ROIxBox.value()/self.resolution[0],self.ROIyBox.value()/self.resolution[1],self.ROIwBox.value()/self.resolution[0],self.ROIhBox.value()/self.resolution[1])
        self.sock.sendObject((SET_CAMERA_SETTINGS, {'zoom' : roi}))

    def resetROI(self):
        self.keepRatioCheckBox.setChecked(False)
        self.centerCheckBox.setChecked(False)
        self.ROIxBox.setValue(0.) 
        self.ROIyBox.setValue(0.)
        self.ROIwBox.setValue(self.resolution[0])
        self.ROIhBox.setValue(self.resolution[1])
        self.setROI()
    
    def setResize(self) :
        doResize = self.resizeCheckBox.isChecked()
        if doResize:
            resize = (int(self.resizewBox.value()),int(self.resizehBox.value()))
            self.sock.sendObject((SET_CAMERA_SETTINGS, {'doResize':doResize, 'resize' : resize}))
        else :
            self.sock.sendObject((SET_CAMERA_SETTINGS, {'doResize':doResize}))
        
#Capture
#CAPTURE_BASIC play with ot without motor
#CAPTURE_ON_FRAME capture frame and advance motor
#CAPTURE_ON_TRIGGER lauchn motor and capture on trigger        
    def captureStart(self):
        brackets = 1
        frameRate = self.framerateBox.value()
        if self.bracketCheckBox.isChecked() :
            brackets = 3
        self.imageThread.brakckets = brackets

        method = None
        if self.onFrameButton.isChecked() :
            method = CAPTURE_ON_FRAME
        elif self.onTriggerButton.isChecked() :
            method = CAPTURE_ON_TRIGGER
        else :
            method = CAPTURE_BASIC
            frameRate = self.playFramerateBox.value()
        if method != CAPTURE_BASIC :
            self.motorControlGroupBox.setEnabled(False)
            self.sock.sendObject((SET_MOTOR_SETTINGS, {'speed':self.captureMotorSpeedBox.value()}))

        self.setMerge() #Merge options
        self.setSave() #Save options
        self.setReduce()

        self.captureStopButton.setEnabled(True)
        self.captureStartButton.setEnabled(False)
        self.capturePauseButton.setEnabled(True)
        self.takeImageButton.setEnabled(False)
        self.autoPauseCheckBox.setEnabled(True)
        self.autoPauseCheckBox.setChecked(False)
        self.initGroupBox.setEnabled(False)
        self.lensAnalyseButton.setEnabled(False)
        self.calibrateLocalButton.setEnabled(False)

        self.setResize()
        
        self.sock.sendObject((SET_CAMERA_SETTINGS, {\
                                                    'framerate':frameRate,\
                                                    'bracket_steps':brackets, \
                                                    'bracket_dark_coefficient':self.darkCoefficientBox.value(),\
                                                    'bracket_light_coefficient':self.lightCoefficientBox.value(),\
                                                    'shutter_speed_wait':self.shutterSpeedWaitBox.value(),\
                                                    'shutter_auto_wait':self.shutterAutoWaitBox.value(),\
#                                                    'use_video_port' : self.videoPortButton.isChecked(),\
                                                    'use_video_port' : True,\
                                                    'capture_method' : method,\
                                                    'pause_pin':int(self.pauseEdit.text()),\
                                                    'pause_level': 1 if self.pauseLevelCheckBox.isChecked() else 0
        }))
        self.sock.sendObject((START_CAPTURE,))

    def setMerge(self) :
        merge = None
        if self.mergeNoneRadioButton.isChecked() :
            merge = MERGE_NONE
        elif self.mergeMertensRadioButton.isChecked() :
            merge = MERGE_MERTENS
        else :
            merge = MERGE_DEBEVEC
        self.imageThread.merge = merge
#        self.imageThread.linearize = self.linearizeCheckBox.isChecked()

    def setSave(self) :
        self.imageThread.saveToFile(self.saveCheckBox.isChecked(), self.directory)



        
#Stopping capture        
    def captureStop(self) :
        self.captureStopButton.setEnabled(False)
        self.captureStartButton.setEnabled(True)
        self.takeImageButton.setEnabled(True)
        self.capturePauseButton.setEnabled(False)
        self.motorControlGroupBox.setEnabled(True)
        self.autoPauseCheckBox.setEnabled(False)
        self.lensAnalyseButton.setEnabled(True)
        self.calibrateLocalButton.setEnabled(True)

        self.initGroupBox.setEnabled(True)
        self.sock.sendObject((STOP_CAPTURE,))
        
#Pausing capture        
    def capturePause(self) :
        self.sock.sendObject((PAUSE_CAPTURE,))
        if self.paused :
            self.capturePauseButton.setText('Pause')
            self.captureStopButton.setEnabled(True)
        else :
            self.capturePauseButton.setText('Restart')
            self.captureStopButton.setEnabled(False)
        self.paused = not self.paused


    def setAutoPause(self):
        self.sock.sendObject((SET_CAMERA_SETTINGS, {'auto_pause': self.autoPauseCheckBox.isChecked()}))

#Take one image
    def takeImage(self):
        self.setReduce()
        self.setResize()
        self.setSave()
        self.sock.sendObject((SET_CAMERA_SETTINGS, {'use_video_port' : True}))
        self.sock.sendObject((TAKE_IMAGE,))

#Get all camera settings
    def getCameraSettings(self) :
        self.sock.sendObject((GET_CAMERA_SETTINGS,))
        settings = self.sock.receiveObject()
        self.redGainBox.setValue(int(float(settings['awb_gains'][0])*100.))
        self.blueGainBox.setValue(int(float(settings['awb_gains'][1])*100.))
        self.awbModeBox.setCurrentIndex(self.awbModeBox.findText(settings['awb_mode']))
        shutterSpeed = int(settings['shutter_speed'])
        self.shutterSpeedBox.setValue(shutterSpeed)
        self.autoExposureCheckBox.setChecked(shutterSpeed == 0)
        self.framerateBox.setValue(int(settings['framerate']))
        exposureSpeed = self.getCameraSetting('exposure_speed')
        self.exposureSpeedLabel.setText(str(exposureSpeed))
        self.analogGainLabel.setText(str(float(settings['analog_gain'])))
        self.digitalGainLabel.setText(str(float(settings['digital_gain'])))
        self.exposureModeBox.setCurrentIndex(self.exposureModeBox.findText(settings['exposure_mode']))
        self.meterModeBox.setCurrentIndex(self.meterModeBox.findText(settings['meter_mode']))
        self.brightnessBox.setValue(settings['brightness'])
        self.contrastBox.setValue(settings['contrast'])
        self.contrastBox.setValue(settings['saturation'])
        self.isoBox.setValue(settings['iso'])
        self.exposureCompensationBox.setValue(settings['exposure_compensation'])
        self.bracketCheckBox.setChecked(settings['bracket_steps'] != 1)
        self.lightCoefficientBox.setValue(settings['bracket_light_coefficient'])
        self.darkCoefficientBox.setValue(settings['bracket_dark_coefficient'])
#        self.videoPortButton.setChecked(settings['use_video_port'])
        self.onFrameButton.setChecked(settings['capture_method'] == CAPTURE_ON_FRAME)
        self.shutterSpeedWaitBox.setValue(settings['shutter_speed_wait'])
        self.shutterAutoWaitBox.setValue(settings['shutter_auto_wait'])
        self.pauseEdit.setText(str(settings['pause_pin']))
        self.pauseLevelCheckBox.setChecked(settings['pause_level'] == 1)
        self.autoPauseCheckBox.setChecked(settings['auto_pause'])
        roi = settings['zoom']
        if roi == None :
            roi = (0.,0.,1.,1.)
        
        self.ROIxBox.setValue(roi[0]*self.resolution[0])
        self.ROIyBox.setValue(roi[1]*self.resolution[1])
        self.ROIwBox.setValue(roi[2]*self.resolution[0])
        self.ROIhBox.setValue(roi[3]*self.resolution[1])
        
        resize = settings['resize']
        if resize == None :
            resize = self.resolution
        self.resizewBox.setValue(resize[0])
        self.resizehBox.setValue(resize[1])
        
        self.resizeCheckBox.setChecked(settings['doResize'])
        return settings

#Get one camera setting
    def getCameraSetting(self, key):
        self.sock.sendObject((GET_CAMERA_SETTING, key))
        return self.sock.receiveObject()
        
    def saveSettings(self):
        self.sock.sendObject((SAVE_SETTINGS,))

    def setColors(self) :
        blue = self.blueGainBox.value()
        red = self.redGainBox.value()
        gains = (red/100., blue/100.)
        mode = str(self.awbModeBox.currentText())
        settings = {'awb_gains': gains, 'awb_mode':mode}
        self.sock.sendObject((SET_CAMERA_SETTINGS, settings))
    
    def setShutterSpeed(self):
        self.sock.sendObject((SET_CAMERA_SETTINGS, {'shutter_speed':self.shutterSpeedBox.value(), 'exposure_compensation':self.exposureCompensationBox.value()}))
                 

    def setIso(self):
         self.sock.sendObject((SET_CAMERA_SETTINGS, {'iso':self.isoBox.value()}))

    def setFrameRate(self):
         self.sock.sendObject((SET_CAMERA_SETTINGS, {'framerate':self.framerateBox.value()}))
        
    def setSharpness(self) :
        self.imageThread.sharpness = self.sharpnessCheckBox.isChecked()

    def setHistos(self) :
        self.imageThread.histos = self.histosCheckBox.isChecked()

    def setReduce(self) :
        self.imageThread.reduceFactor = self.reduceFactorBox.value()
        
        
    def setAutoExposure(self):
        if self.autoExposureCheckBox.isChecked() :
            self.sock.sendObject((SET_CAMERA_SETTINGS, {'shutter_speed':0}))
            self.shutterSpeedBox.setValue(0)
        else :
            exposureSpeed = self.getCameraSetting('exposure_speed')
            self.exposureSpeedLabel.setText(str(exposureSpeed))  # ms display
            self.sock.sendObject((SET_CAMERA_SETTINGS, {'shutter_speed':exposureSpeed}))
            self.shutterSpeedBox.setValue(exposureSpeed)
            
    def setAutoGetSettings(self):
        if self.autoGetSettingsCheckBox.isChecked() :
            self.timer = QTimer()
            self.timer.timeout.connect(self.getSettings)
            self.timer.start(5000)
        else :
            self.timer.stop()
            
    def setCorrections(self):
        self.sock.sendObject((SET_CAMERA_SETTINGS, {'brightness':self.brightnessBox.value(), 'contrast':self.contrastBox.value(),'saturation':self.saturationBox.value()}))

    def setGains(self):
        exposure_mode = str(self.exposureModeBox.currentText())
        meter_mode = str(self.meterModeBox.currentText())
        settings = {'exposure_mode':exposure_mode,'meter_mode':meter_mode,}
        self.sock.sendObject((SET_CAMERA_SETTINGS, settings))

    def lensAnalyse(self):
        self.sock.sendObject((TAKE_BGR,HEADER_ANALYZE, 1) )

    def setDirectory(self) :
        if self.root_directory != None :
            self.tape = self.tapeBox.value()
            self.clip = self.clipBox.value()
            self.directory = self.root_directory  + "/%#02d_%#02d" % (self.tape, self.clip)
            self.directoryDisplay.setText(self.directory)
            if not os.path.exists(self.directory):
                os.makedirs(self.directory)
        
    def chooseDirectory(self) :
        self.root_directory = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        self.directoryDisplay.setText(self.root_directory)

    def displayMessage(self, text) :
        self.messageTextEdit.insertPlainText(text+"\n");
        sb = self.messageTextEdit.verticalScrollBar();
        sb.setValue(sb.maximum());

#         c = messageTextEdit.textCursor();
#         c.movePosition(QTextCursor::End);
#         messageTextEdit->setTextCursor(c);        
        
        
        
    def displayHeader(self, header) :
        typ = header['type']
        if typ == HEADER_IMAGE :
            gains = header['gains']
            self.analogGainLabel.setText(str(float(header['analog_gain'])))
            self.digitalGainLabel.setText(str(float(header['digital_gain'])))
            self.redGainBox.setValue(int(float(gains[0])*100.))
            self.blueGainBox.setValue(int(float(gains[1])*100.))
            shutter = header['shutter']
            self.exposureSpeedLabel.setText(str(shutter))  # ms display
        elif typ == HEADER_MESSAGE :
            self.displayMessage(str(header['msg']))

    def displayImage(self, image) :
        if self.imageDialog == None :
            self.imageDialog = ImageDialog(self)
        self.imageDialog.show()
        self.imageDialog.displayImage(image)
            
    def displayPlot(self, image) :
        if self.plotDialog == None :
            self.plotDialog = PlotDialog(self)
        self.plotDialog.show()
        self.plotDialog.displayImage(image)
        
    def connectDisconnect(self) :
        if self.connected :
            self.disconnect()
            self.connectButton.setStyleSheet("background-color: red")
            self.connected = False
            self.connectButton.setText('Connect')
        else :
            self.connect()
            self.connectButton.setStyleSheet("background-color: green")
            self.connected = True
            self.connectButton.setText('Disconnect')

    
    def connect(self) :
        socke = socket.socket()
        self.ip_pi = self.ipLineEdit.text()
        socke.connect((self.ip_pi, 8000))
        self.sock = MessageSocket(socke)
        self.imageThread = ImageThread(self.ip_pi)
        self.imageThread.headerSignal.connect(self.displayHeader)
        self.imageThread.imageSignal.connect(self.displayImage)
        self.imageThread.plotSignal.connect(self.displayPlot)
        self.imageThread.start()
        self.getMotorSettings()
        self.cameraGroupBox.setEnabled(True)
        self.openCameraButton.setEnabled(True)
        self.calibrateButton.setEnabled(True)
        self.motorOnGroupBox.setEnabled(True)

#        self.motorControlGroupBox.setEnabled(True)
        self.motorSettingsGroupBox.setEnabled(True)
        self.connected = True



    def disconnect(self) :
        if self.connected :
            self.sock.sendObject((TERMINATE,))
            self.sock.shutdown()
            self.sock.close()
            self.cameraGroupBox.setEnabled(False)
            self.cameraControlGroupBox.setEnabled(False)
            self.frameProcessingGroupBox.setEnabled(False)
            self.motorControlGroupBox.setEnabled(False)
            self.cameraSettingsGroupBox.setEnabled(False)
            self.motorSettingsGroupBox.setEnabled(False)

    def saveLocalSettings(self) :
        np.savez('local.npz', local = getSettings(self, localSettings))

    def setLocalSettings(self) :
        try:
            npz = np.load("local.npz", allow_pickle=True)
            setSettings(self, npz['local'][()])
            self.ipLineEdit.setText(self.ip_pi)
            self.directoryDisplay.setText(self.root_directory)
            self.hflipCheckBox.setChecked(self.hflip)
            self.vflipCheckBox.setChecked(self.vflip)
            self.modeBox.setValue(self.mode)
            self.tapeBox.setValue(self.tape)
            self.clipBox.setValue(self.clip)
            self.setDirectory()
        except Exception as e:
            self.displayMessage(str(e))
            print(e)
        
class ImageDialog(QDialog) :
    def __init__(self, parent):
        super(ImageDialog, self).__init__(parent)
        self.setWindowTitle("Pi Film Capture:")
        self.mQImage = None
        
    def displayImage(self, image):
        height, width, byteValue=image.shape
        byteValue=byteValue*width
        image = image[...,::-1].copy()
        self.mQImage = QImage(image, width, height, byteValue, QImage.Format_RGB888)
        self.setFixedSize(width, height)
        self.update()

    def paintEvent(self, QPaintEvent):
        painter = QPainter()
        painter.begin(self)
        if self.mQImage != None:
            painter.drawImage(0, 0, self.mQImage)
        painter.end()
    
class PlotDialog(QDialog) :
    def __init__(self, parent):
        super(PlotDialog, self).__init__(parent)
        self.setWindowTitle("Plot")
        self.mQImage = None
        
    def displayImage(self, image):
        height, width, byteValue=image.shape
        byteValue=byteValue*width
        self.mQImage = QImage(image, width, height, byteValue, QImage.Format_RGB888)
        self.setFixedSize(width, height)
        self.update()

    def paintEvent(self, QPaintEvent):
        painter = QPainter()
        painter.begin(self)
        if self.mQImage != None:
            painter.drawImage(0, 0, self.mQImage)
        painter.end()

commandDialog = None
#For getting exception while in QT        
def my_excepthook(type, value, tback):
    commandDialog.displayMessage(str(value))
    print(type)
    print(value)
    print(tback)
    sys.__excepthook__(type, value, tback) 

#Local commandDialog settings
 
    
    
if __name__ == '__main__':
    try:
       # Create the Qt Application
        app = QApplication(sys.argv)
        commandDialog =  TelecineDialog()
        commandDialog.setLocalSettings()
        commandDialog.show()
        sys.excepthook = my_excepthook           
        sys.exit(app.exec_())


    finally:
        print('finally')
        if commandDialog != None :
            commandDialog.saveLocalSettings()
            commandDialog.disconnect()