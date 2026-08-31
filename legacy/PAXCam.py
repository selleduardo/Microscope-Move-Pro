#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan 31 13:07:35 2018

@author: pfjarschel
"""

import cv2
import numpy as np
from PyQt6.QtGui import QImage

class PAXCam:
    fps = 0
    maxW = 2448
    maxH = 2048
    frameW = maxW
    frameH = maxH
    exposure = -5 #-13 to -3
    gain = 1000 #0 to 5000
    whiteBalance = 4000 #Kelvin
    cam = None
    camOK = False
    ccdSize = [12986,10867]

    def __init__(self, usbID=0):
        self.cam = cv2.VideoCapture(usbID)
        self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, 2448)
        self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 2048)
        self.cam.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
        #self.cam.set(cv2.CAP_PROP_GAIN, 1000) #0 to 5000
        self.TestCam()
        self.GetExposure()
        self.GetGain()
        self.GetWhiteBalance()
        
    def __del__(self):
        self.Close()
    
    def Close(self):
        self.cam.release()
        cv2.destroyAllWindows()
        
    def TestCam(self):
        fOK = self.cam.read()
        self.camOK = fOK
        return fOK
        
    def GetFrameMatrix(self, scale=1):
        fOK, frame = self.cam.read()
        if not fOK:
            frame = np.zeros([int(np.round(self.frameH*scale)), int(np.round(self.frameW*scale)), 3])
        return frame

    def GetQImage(self, scale=1):
        frame = self.GetFrameMatrix(scale)
        w = len(frame[0])
        h = len(frame)
        img = QImage(frame.data, w, h, QImage.Format.Format_RGB888)
        
        return img.rgbSwapped()
    
    def SetCaptureDimensions(self, w, h):
        self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        self.frameH = h
        self.frameW = w
        
    def SetExposure(self, expercent):
        exp = -13 + (expercent/100.0)*10
        self.cam.set(cv2.CAP_PROP_EXPOSURE, exp)
        self.exposure = expercent
        
    def SetGain(self, gpercent):
        g = (gpercent/100.0)*5000
        self.cam.set(cv2.CAP_PROP_GAIN, g)
        self.gain = gpercent
        
    def GetExposure(self):
        e = self.cam.get(cv2.CAP_PROP_EXPOSURE)
        self.exposure = 100*(e + 13)/10
        return self.exposure
    
    def GetGain(self):
        g = self.cam.get(cv2.CAP_PROP_GAIN)
        self.gain = 100*g/5000
        return self.gain

    def SetWhiteBalance(self, kelvin):
        self.cam.set(cv2.CAP_PROP_WB_TEMPERATURE, kelvin)
        self.whiteBalance = kelvin

    def GetWhiteBalance(self):
        self.whiteBalance = self.cam.get(cv2.CAP_PROP_WB_TEMPERATURE)
        return self.whiteBalance

    def GetCaptureDimensions(self):
        w = self.cam.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = self.cam.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self.frameW = w
        self.frameH = h
        return [w, h]
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        