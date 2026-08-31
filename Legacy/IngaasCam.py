#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb  6 10:42:02 2018

@author: pfjarschel
"""

import cv2
import numpy as np
from PyQt6.QtGui import QImage
import ctypes
import time

class IngaasCam:
    fps = 0
    maxW = 640
    maxH = 512
    frameW = maxW
    frameH = maxH
    exposure = 10 #ms
    gain = 0 #0 or 1
    cam = None
    ifaceOK = False
    camOK = False
    ccdSize = [16000,12800]
    
    def __init__(self, hgain = 0):  
        self.cam = ctypes.cdll.LoadLibrary("snakecamlinkcontrol.dll")
        campath = ""
        if hgain == 1:
            campath = "ingaas_files/Snake_High_Gain/PSL_camera_files"
        else:
            campath = "ingaas_files/Snake_Mid_Gain/PSL_camera_files"    

        self.gain = hgain
        #self.ifaceOK = not self.cam.PSL_VHR_Init(campath)
        ptype = ctypes.POINTER(ctypes.c_char_p)
        caminit = self.cam.PSL_VHR_Init
        caminit.argtypes = [ptype]        
        campathb = campath.encode(encoding="utf-8")
        campathca = ctypes.create_string_buffer(campathb)
        self.ifaceOK = not caminit(ctypes.cast(ctypes.addressof(campathca), ptype))

        if self.ifaceOK:
            load_dc = self.cam.PSL_VHR_load_dark_current_file
            load_ff = self.cam.PSL_VHR_load_flat_field_file
            load_dc.argtypes = [ptype]    
            load_ff.argtypes = [ptype]
            dcfile = "darkcusdfrrent.flf"
            fffile = "incamtemsdfpflat.flf"
            dcfileb = dcfile.encode()
            fffileb = fffile.encode()
            dcfileca = ctypes.create_string_buffer(dcfileb)
            fffileca = ctypes.create_string_buffer(fffileb)
            load_dc(ctypes.cast(ctypes.addressof(dcfileca), ptype))
            load_ff(ctypes.cast(ctypes.addressof(fffileca), ptype))
            #self.cam.PSL_VHR_load_dark_current_file("darkcusdfrrent.flf")
            #self.cam.PSL_VHR_load_flat_field_file("incamtemsdfpflat.flf")
            
            
            if hgain == 1:
                self.cam.PSL_VHR_enable_high_gain_mode(True)
            else:
                self.cam.PSL_VHR_enable_high_gain_mode(False)
            
            self.cam.PSL_VHR_SetTriggerMode(0)
            self.cam.PSL_VHR_WriteExposure(1000*self.exposure)
            self.cam.PSL_VHR_enable_offset_subtraction(True)
            self.cam.PSL_VHR_enable_dark_current_correction(True)
            self.cam.PSL_VHR_enable_dark_field_subtraction(True)
        
        self.TestCam()
        self.GetExposure()
        self.GetGain()
        
    def __del__(self):
        self.Close()
    
    def Close(self):
        if self.ifaceOK:
            self.cam.PSL_VHR_Free()
        
    def TestCam(self):
        if self.ifaceOK:
            self.cam.PSL_VHR_Snap_and_return()
            if self.exposure > 17:
                time.sleep(2.0*self.exposure/1000.0)
            else:
                time.sleep(2.0*17.0/1000.0)
            self.camOK = self.cam.PSL_VHR_Get_snap_status()
        return self.camOK
        
    def GetFrameMatrix(self, scale=1):
        frame = None
        if self.camOK:
            self.cam.PSL_VHR_Snap_and_return()
            done = self.cam.PSL_VHR_Get_snap_status()
            while not done:
                done = self.cam.PSL_VHR_Get_snap_status()
                #time.sleep(self.exposure/(2.0*1000.0))
            ptype = ctypes.POINTER(ctypes.c_ushort)
            improc = self.cam.PSL_VHR_apply_post_snap_processing
            improc.argtypes = [ptype]
            impointer = ctypes.cast(self.cam.PSL_VHR_Get_image_pointer(), ptype)
            improc(impointer)
            
            data = np.fromiter(impointer, dtype=np.ushort, count=self.frameH*self.frameW)
            frame = np.reshape(data, (512, 640))
            frame = cv2.convertScaleAbs(frame, alpha=(255.0/65535.0))
        else:
            frame = np.zeros([int(np.round(self.frameH*scale)), int(np.round(self.frameW*scale)), 3])
        return frame

    def GetQImage(self, scale=1):
        frame = self.GetFrameMatrix()
        w = len(frame[0])
        h = len(frame)
        img = QImage(frame.data, w, h, QImage.Format.Format_Grayscale8)
        #img = img.convertToFormat(QImage.Format_RGB888)
        return img
    
    def SetCaptureDimensions(self, w, h):
        self.frameH = 512
        self.frameW = 640
        
    def SetExposure(self, expercent):
        expms = expercent
        if expms < 1:
            expms = 1
        self.cam.PSL_VHR_WriteExposure(1000*expms)
        self.exposure = expercent
        
    def SetGain(self, hgain):
        self.gain = self.gain
        
    def GetExposure(self):
        return self.exposure
    
    def GetGain(self):
        return self.gain
    
    def GetCaptureDimensions(self):
        return [640, 512]
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        