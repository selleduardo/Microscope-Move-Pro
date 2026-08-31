#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan 31 13:02:26 2018

@author: pfjarschel
"""

import pyvisa as visa
import time
import numpy as np
from threading import Timer

class NewportMotors:
    rm = None
    xDev = None
    yDev = None
    zDev = None
    xOK = False
    yOK = False
    zOK = False
    xhoming = False
    yhoming = False
    zhoming = False
    maxXYVel = 0.4
    maxZVel = 0.16
    maxXYStepVel = 0.354
    maxZStepVel = 0.12
    posLimit = 25
    accelXYZ = 1.6
    xST = ""
    yST = ""
    zST = ""
    xPOS = 0
    yPOS = 0
    zPOS = 0
    xWait = 0
    xStep = 0
    yWait = 0
    yStep = 0
    zWait = 0
    zStep = 0
    yBusy = False
    zBusy = False
    
    def __init__(self, xString="COM5", yString="COM6", zString="COM3"):
        #Init stuff
        visa.log_to_screen(0)
        try:
            self.rm = visa.ResourceManager('@ni')
        except:
            pass
        
        try:
            self.xDev = self.rm.open_resource(xString, baud_rate=921600, data_bits=8, stop_bits=visa.constants.StopBits.one)
            self.xDev.clear()
            self.xST = self.xDev.query("1TS?")
            xst = self.xST[-4:-2]
            if xst[0] == "3" and xst[1] != "C" and xst[1] != "D" and xst[1] != "E" and xst[1] != "F":
                self.xPOS = float(self.xDev.query("1TP?")[3:])
                self.xOK = True
            else:
                self.xhoming = True
        except:
            pass
        try:
            self.yDev = self.rm.open_resource(yString, baud_rate=921600, data_bits=8, stop_bits=visa.constants.StopBits.one)
            self.yDev.clear()
            self.yST = self.yDev.query("1TS?")
            yst = self.yST[-4:-2]
            if yst[0] == "3" and yst[1] != "C" and yst[1] != "D" and yst[1] != "E" and yst[1] != "F":
                self.yPOS = float(self.yDev.query("1TP?")[3:])
                self.yOK = True
            else:
                self.yhoming = True
        except:
            pass
        try:
            self.zDev = self.rm.open_resource(zString, baud_rate=57600, data_bits=8, stop_bits=visa.constants.StopBits.one)
            self.zDev.clear()
            self.zST = self.xDev.query("1TS?")
            zst = self.zST[-4:-2]
            if zst[0] == "3" and zst[1] != "C" and zst[1] != "D" and zst[1] != "E" and zst[1] != "F":
                self.zPOS = float(self.zDev.query("1TP?")[3:])
                self.zOK = True
            else:
                self.zhoming = True
        except:
            pass
        
    def Close(self):
        #End stuff
        if self.xOK:
            self.xDev.clear()
            self.xDev.close()
        if self.yOK:
            self.yDev.clear()
            self.yDev.close()
        if self.zOK:
            self.zDev.clear()
            self.zDev.close()
        try:
            self.rm.close()
        except:
            pass
    
    def __del__(self):
        pass
        
    def Home(self, axis):
        if (axis == 1 or axis == "x"):
            try:
                self.xDev.write("1OR")
                time.sleep(0.2)
                self.xST = self.xDev.query("1TS?")
                while "1E" in self.xST:
                    self.xhoming = True
                    time.sleep(0.2)
                    self.xST = self.xDev.query("1TS?")
                self.xPOS = float(self.xDev.query("1TP?")[3:])
                self.xOK = True
                self.xhoming = False
            except:
                pass
        if (axis == 2 or axis == "y"):
            try:
                self.yDev.write("1OR")
                time.sleep(0.2)
                self.yST = self.yDev.query("1TS?")
                while "1E" in self.yST:
                    self.yhoming = True
                    time.sleep(0.2)
                    self.yST = self.yDev.query("1TS?")
                self.yPOS = float(self.yDev.query("1TP?")[3:])
                self.yOK = True  
                self.yhoming = False
            except:
                pass
        if (axis == 3 or axis == "z"):
            try:
                self.zDev.write("1OR")
                time.sleep(0.2)
                self.zST = self.zDev.query("1TS?")
                while "1E" in self.zST:
                    self.zhoming = True
                    time.sleep(0.2)
                    self.zST = self.zDev.query("1TS?")
                self.zPOS = float(self.zDev.query("1TP?")[3:])
                self.zOK = True  
                self.zhoming = False
            except:
                pass
            
    def HomeAll(self):
        homex = Timer(0.1, self.Home, [1])
        homey = Timer(0.1, self.Home, [2])
        homez = Timer(0.1, self.Home, [3])
        homex.start()
        homey.start()
        homez.start()
    
    def MoveAbsolute(self, axis, pos):
        if pos > self.posLimit:
            pos = self.posLimit
        if (axis == 1 or axis == "x") and self.xOK:
            self.xDev.write("1PA" + str(pos))
        if (axis == 2 or axis == "y") and self.yOK:
            self.yDev.write("1PA" + str(pos))
        if (axis == 3 or axis == "z") and self.zOK:
            self.zDev.write("1PA" + str(pos))
            
    def MoveRelative(self, axis, delta):
        if (axis == 1 or axis == "x") and self.xOK:
            self.xDev.write("1PR" + str(delta))
        if (axis == 2 or axis == "y") and self.yOK:
            self.yDev.write("1PR" + str(delta))
        if (axis == 3 or axis == "z") and self.zOK:
            self.zDev.write("1PR" + str(delta))
            
    def CalculateContParams(self, axis, amp, velmult):
        if (axis == 1 or axis == "x"):            
            #Calculate apparent velocity
            mvel = amp*self.maxXYStepVel*velmult
            sign = np.sign(mvel)
            mvel = np.fabs(mvel)
            
            #Calculate parameters from velocity
            if mvel > 0.1:
                self.xWait = 44946*pow(mvel,6) - 43857*pow(mvel,5) + 16536*pow(mvel,4) - 2937.8*pow(mvel,3) + 245.51*pow(mvel,2) - 6.4873*mvel + 0.32153
                self.xStep = 18192*pow(mvel,6) - 17870*pow(mvel,5) + 6819.3*pow(mvel,4) - 1241.9*pow(mvel,3) + 110.08*pow(mvel,2) - 3.6837*mvel + 0.03863
            else:
                self.xWait = -6.6427*pow(mvel,2) + 2.6479*mvel + 0.2317
                self.xStep = 1.6463*pow(mvel,2) + 0.27241*mvel - 0.00037
                if self.xStep < 0.0001:
                    self.xStep = 0.0001
            self.xStep = sign*self.xStep
            #print("x", mvel, self.xStep, self.xWait)
        
        if (axis == 2 or axis == "y"):
            self.yBusy = True
            
            #Calculate apparent velocity
            mvel = amp*self.maxXYStepVel*velmult
            sign = np.sign(mvel)
            mvel = np.fabs(mvel)
            
            #Calculate parameters from velocity
            if mvel > 0.1:
                self.yWait = 44946*pow(mvel,6) - 43857*pow(mvel,5) + 16536*pow(mvel,4) - 2937.8*pow(mvel,3) + 245.51*pow(mvel,2) - 6.4873*mvel + 0.32153
                self.yStep = 18192*pow(mvel,6) - 17870*pow(mvel,5) + 6819.3*pow(mvel,4) - 1241.9*pow(mvel,3) + 110.08*pow(mvel,2) - 3.6837*mvel + 0.03863
            else:
                self.yWait = -6.6427*pow(mvel,2) + 2.6479*mvel + 0.2317
                self.yStep = 1.6463*pow(mvel,2) + 0.27241*mvel - 0.00037
                if self.yStep < 0.0001:
                    self.yStep = 0.0001
            self.yStep = sign*self.yStep
            #print("y", mvel, self.yStep, self.yWait)
                
        if (axis == 3 or axis == "z"):
            self.zBusy = True
            
            #Calculate apparent velocity
            mvel = amp*self.maxZStepVel*velmult
            sign = np.sign(mvel)
            mvel = np.fabs(mvel)
            
            #Calculate parameters from velocity
            self.zWait = 802708.7464*pow(mvel,6) - 178545.7485*pow(mvel,5) + 11542*pow(mvel,4) + 474.95*pow(mvel,3) - 62.11*pow(mvel,2) + 4.2149*mvel + 0.21946
            self.zStep = 197408.9595*pow(mvel,6) - 59314*pow(mvel,5) + 7326.8*pow(mvel,4) - 420.44*pow(mvel,3) + 13.97*pow(mvel,2) + 0.09953*mvel + 0.00045
            if self.zStep < 0.0001:
                self.zStep = 0.0001
            self.zStep = sign*self.zStep
            #print("z", mvel, self.zStep, self.zWait)
    
    def Stop(self, axis):
        if (axis == 1 or axis == "x") and (self.xOK or self.xhoming):
            self.xDev.write("1ST")
        if (axis == 2 or axis == "y") and (self.xOK or self.yhoming):
            self.yDev.write("1ST")
        if (axis == 3 or axis == "z") and (self.xOK or self.zhoming):
            self.zDev.write("1ST")
    
    def StopAll(self):
        for i in range(1,4):
            self.Stop(i)
            
    def GetPos(self, axis):
        if (axis == 1 or axis == "x") and (self.xOK or self.xhoming):
            return self.xPOS
        if (axis == 2 or axis == "y") and (self.yOK or self.yhoming):
            return self.yPOS
        if (axis == 3 or axis == "z") and (self.zOK or self.zhoming):
            return self.zPOS
    
    def UpdatePositions(self):
        if self.xOK or self.xhoming:
            self.xPOS = float(self.xDev.query("1TP?")[3:])
        if self.yOK or self.yhoming:
            self.yPOS = float(self.yDev.query("1TP?")[3:])
        if self.zOK or self.zhoming:
            self.zPOS = float(self.zDev.query("1TP?")[3:])

    def AxisMoving(self, axis):
        mv = False
        if (axis == 1 or axis == "x") and (self.xOK or self.xhoming):
            st = self.xDev.query("1TS?")
            if "28" in st or "1E" in st:
                mv = True
        if (axis == 2 or axis == "y") and (self.yOK or self.yhoming):
            st = self.yDev.query("1TS?")
            if "28" in st or "1E" in st:
                mv = True
        if (axis == 3 or axis == "z") and (self.zOK or self.zhoming):
            st = self.zDev.query("1TS?")
            if "28" in st or "1E" in st:
                mv = True
        return mv





















































