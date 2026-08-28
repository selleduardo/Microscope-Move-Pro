#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import numpy as np
from PyQt6.QtGui import QImage


class USBCam:
    """
    Generic UVC camera opened via cv2.VideoCapture, same method used in the
    "Refs/Moving stages" notebooks (Chip mapper, Image Stitcher). Unlike
    PAXCam, capture resolution is not forced: this camera did not accept the
    2448x2048 request PAXCam.py makes (that's for a different camera), so we
    let the driver report/keep its own default (~1280x960 in the notebooks).
    """

    fps = 0
    exposure = -6 #-13 to -3, value validated in the notebooks
    gain = 0
    whiteBalance = 4000 #Kelvin, value validated in the notebooks
    cam = None
    camOK = False
    maxW = 1280
    maxH = 960
    frameW = maxW
    frameH = maxH
    # TODO: placeholder copied from PAXCam's sensor - this camera's real chip
    # size (in um) is unknown and needs to be measured/calibrated. Until then,
    # the on-screen micron scale (CalcCalibrationScale) will be wrong.
    ccdSize = [12986, 10867]

    def __init__(self, usbID=0):
        self.cam = cv2.VideoCapture(usbID)
        self.cam.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
        self.cam.set(cv2.CAP_PROP_WB_TEMPERATURE, self.whiteBalance)
        self.TestCam()
        self.GetCaptureDimensions()
        self.GetExposure()
        self.GetGain()
        self.GetWhiteBalance()

    def __del__(self):
        self.Close()

    def Close(self):
        self.cam.release()
        cv2.destroyAllWindows()

    def TestCam(self):
        fOK, _ = self.cam.read()
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
        self.maxW = w
        self.maxH = h

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
        self.maxW = w
        self.maxH = h
        return [w, h]
