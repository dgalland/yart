import numpy as np
import cv2
import sys
import matplotlib.pyplot as plt
from PyQt5.QtCore import QThread, pyqtSignal
sys.path.append('../Common')
from Constants import *
from MessageSocket import *

#Receive and process header and images
#Non concluding experiments
#   linearize = true : Revert gamma corection of Jpeg before merging
#   crf = True : Precalculate the camera response forDebevec merge
#It seems that the Debevec merge without the camera response (ie a linear response) gives the best result
#it seems also that Durand's Tonemap gives the best result
#Note: sharpness is useful for focusing
#Focus your lens to have the maximum sharpness  
 
class ImageThread (QThread):
    histoSignal = pyqtSignal([object,])   #Signal to the GUI display histo
    headerSignal = pyqtSignal([object,])  #Signal to the GUI display header
    sharpnessSignal = pyqtSignal([object,])  #Signal to the GUI display sharpness
    merge = MERGE_NONE
    sharpness = False
    saveToFile = False
    histos = False
    images = []
    shutters = []
    def __init__(self, ip_pi):
        QThread.__init__(self)
        self.threadID = 1
        self.name = "ImgThread"
        self.window = None
        self.saveOn = False
        self.mergeMertens = cv2.createMergeMertens(0.,0.,1.)
        self.mergeDebevec = cv2.createMergeDebevec()
        self.toneMap = cv2.createTonemapReinhard()
        self.claheProc = cv2.createCLAHE(clipLimit=1, tileGridSize=(8,8))
        self.clipLimit = 1.
        self.reduceFactor = 1;
        self.equalize = False
        self.clahe = False
        self.ip_pi = ip_pi
        self.hflip = False
        self.vflip = False
    def calcHistogram(self, image) :
        histos = []
        for i in range(3):
            histo = cv2.calcHist([image],[i],None,[256],[0,256])
            histos.append(histo)
        self.displayHistogramOverImage(histos, image)
        
    def displayHistogramOverImage(self, histos, image) :
        figure = plt.figure()
        axe = figure.add_subplot(111)
        colors = ('b','g','r')
        for i,col in enumerate(colors):
            axe.plot(histos[i],color = col)
        axe.set_xlim([0,256])
        axe.get_yaxis().set_visible(False)
        figure.tight_layout()
        figure.canvas.draw()
        w, h  = figure.canvas.get_width_height()
        buf = np.fromstring ( figure.canvas.tostring_rgb(), dtype=np.uint8 ).reshape(h,w,3)
        ww = int(image.shape[0]/4)
        hh = int(h*ww/w)
        resized = cv2.resize(buf, dsize=(ww,hh), interpolation=cv2.INTER_CUBIC)
        image[:hh,:ww] = resized
            
    def processImage(self, header, jpeg):
#        print(header)
        bracket = header['bracket']
        count = header['count']
        jpeg = np.frombuffer(jpeg, np.uint8,count = len(jpeg)) 
        image = cv2.imdecode(jpeg, 1)   #Jpeg decoded
        if self.merge != MERGE_NONE and bracket != 0 : #Merge
            self.images.append(image)
            self.shutters.append(header['shutter'])
            if bracket != 1 :
                return
            else :
                if self.merge == MERGE_MERTENS:
                    image = self.mergeMertens.process(self.images)
                else :
                    image = self.mergeDebevec.process(self.images, np.asarray(self.shutters,dtype=np.float32)/1000000.)
                    image = self.toneMap.process(image)
                image = np.clip(image*255, 0, 255).astype('uint8')
                if self.equalize :
                    H, S, V = cv2.split(cv2.cvtColor(image, cv2.COLOR_BGR2HSV))
                    low, high = np.percentile(V, (1, 99))
                    eq_V = np.interp(V, (low,high), (V.min(), V.max())).astype(np.uint8)
                    image = cv2.cvtColor(cv2.merge([H, S, eq_V]), cv2.COLOR_HSV2BGR)
                if self.clahe :
                    H, S, V = cv2.split(cv2.cvtColor(image, cv2.COLOR_BGR2HSV))
                    self.claheProc.setClipLimit(self.clipLimit)
                    eq_V = self.claheProc.apply(V)
                    image = cv2.cvtColor(cv2.merge([H, S, eq_V]), cv2.COLOR_HSV2BGR)
                if self.saveOn :
                    cv2.imwrite(self.directory + "/image_%#05d.jpg" % count, image)
                self.images.clear()
                self.shutters.clear()
        else :
            if self.saveOn :
                file = open(self.directory + "/image_%#05d_%#02d.jpg" % (header['count'], header['bracket']),'wb')
                file.write(jpeg)
                file.close()
#                if True :
#                    b,g,r = cv2.split(image)
#                    cv2.imwrite(self.directory + "/image_%#05d_%#02d_b.jpg" % (header['count'], header['bracket']),b)
#                    cv2.imwrite(self.directory + "/image_%#05d_%#02d_g.jpg" % (header['count'], header['bracket']),g)
#                    cv2.imwrite(self.directory + "/image_%#05d_%#02d_r.jpg" % (header['count'], header['bracket']),r)
            if self.sharpness :
                sharpness = cv2.Laplacian(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
                cv2.putText(image, str(sharpness), (200,200), cv2.FONT_HERSHEY_SIMPLEX,3,(255,255,255),2)
        if self.histos :            
            self.calcHistogram(image)
        if self.reduceFactor != 1 :
            newShape = (int(image.shape[1]/self.reduceFactor),int(image.shape[0]/self.reduceFactor))
            image = cv2.resize(image, dsize=newShape, interpolation=cv2.INTER_CUBIC)            
        cv2.imshow("PiCamera", image)
        cv2.waitKey(1)

    def lensAnalyze(self, header) :
        image = self.imageSock.receiveArray()  #bgr
        print('Max:', np.max(image[:,:,0]),'Min:', np.min(image[:,:,0]),'Mean:', np.mean(image[:,:,0])) 
        print('Max:', np.max(image[:,:,1]),'Min:', np.min(image[:,:,1]),'Mean:', np.mean(image[:,:,1])) 
        print('Max:', np.max(image[:,:,2]),'Min:', np.min(image[:,:,2]),'Mean:', np.mean(image[:,:,2])) 
#        np.savez('image.npz',   image = image)
#        cv2.imwrite('image.jpg', image)
#        cv2.imshow("PiCamera", image)
#        cv2.waitKey(1)
        
        x = image.shape[0]/image.shape[1]
        diag = np.empty((image.shape[1],3))
        print(diag.shape)
        for i in range(image.shape[1]) :  #3280
            j = int(i * x)
            diag[i,:] = image[j,i,:]
            
        colors = ('b','g','r')
        figure = plt.figure(figsize=(10,3))
        axe = figure.add_subplot(1,3,1)
        axe.title.set_text('Horizontal')
        for i,col in enumerate(colors):
            axe.plot(image[image.shape[0]//2,:,i],color = col)  #Horizontal
        axe = figure.add_subplot(1,3,2)
        axe.title.set_text('Vertical')
        for i,col in enumerate(colors):
            axe.plot(image[:,image.shape[1]//2,i],color = col)  #Vertical
        axe = figure.add_subplot(1,3,3)
        axe.title.set_text('Diagonal')
        for i,col in enumerate(colors):
            axe.plot(diag[:, i],color = col) #Diagonal
#        figure.subplots_adjust(top=0.85)
        plt.show()




    def saveToFile(self, saveFlag, directory) :
        self.saveOn = saveFlag
        self.directory = directory
            
    def run(self):
        print('ImageThread started')
        self.imageSock = None
        try:
            sock = socket.socket()
            sock.connect((self.ip_pi, 8000))
            print('ImageThread connected')
            self.imageSock = MessageSocket(sock)
            while True:
                header = self.imageSock.receiveObject()
                if header == None :
                    print('Closed connection')
                    cv2.destroyAllWindows()
                    if self.imageSock != None:
                        self.imageSock.close()
                    break
                typ = header['type']
                if typ == HEADER_STOP:
                    break
                self.headerSignal.emit(header) #«display header info in GUI if necessary (count,...)
                if  typ == HEADER_IMAGE :
                    image = self.imageSock.receiveMsg()
                    self.processImage(header, image)
                elif typ == HEADER_BGR :
                    self.processBgr()
                elif typ == HEADER_ANALYZE :
                    self.lensAnalyze(header)
#                if  typ == HEADER_HDR :
#                    image = self.imageSock.receiveMsg()
#                    self.processHdrImage(header, image)
                
        finally:
            print('ImageThread terminated')
            cv2.destroyAllWindows()
            if self.imageSock != None:
                self.imageSock.shutdown()
                self.imageSock.close()

#Experimental Receive a set of exposures not used
    def processHdrImage(self, header, jpeg):
        jpeg = np.frombuffer(jpeg, np.uint8,count = len(jpeg))
        file = open(self.directory + "/ldr_%#05d.jpg" % (header['shutter']) ,'wb')
        file.write(jpeg)
        file.close()
        image = cv2.imdecode(jpeg, 1)   #Jpeg decode
        cv2.imshow("PiCamera", image)
        cv2.waitKey(1)



        
