# -*- coding: utf-8 -*-

"""
Created on Wed Jan 31 17:52:19 2018

@author: pfjarschel

Edited on Fri Aug 28 2026

@author: esell

"""

import sys, time, os.path, datetime
import numpy as np
from threading import Timer, Thread, Lock
from PyQt6 import uic
from PyQt6.QtCore import Qt, QCoreApplication, QTimer, QPoint, QRectF, QDir
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox, QLabel, QColorDialog
from PyQt6.QtGui import QIcon, QPixmap, QImage, QColor, QCursor, QTransform, QPainter, QBrush, QPolygon, QFont, QTextOption

import PAXCam
import IngaasCam
import USBCam

import CorvusStage

ilmd_available = False
try:
    import importlib.metadata
    ilmd_available = True
except:
    pass


FormUI, WindowUI = uic.loadUiType("MainWindow_UI.ui")


class ImageAcquisition:
    def __init__(self):
        self.thread = None

        self.cam = None
        self.camOpen = False
        self.img = QImage(640, 512, QImage.Format.Format_RGB32)
        self.img.fill(Qt.GlobalColor.black)

        self.started = False
        self.read_lock = Lock()

        self.t0 = time.time()
        self.t1 = time.time()
        self.fpsframes = 10
        self.fps = 0
        self.framecount = 0

    def OpenCam(self, camid):
        if camid == "USBCam":
            self.cam = USBCam.USBCam(0)
        elif camid == "PAXCam":
            self.cam = PAXCam.PAXCam(0)
        elif camid == "IngaasCam":
            self.cam = IngaasCam.IngaasCam(0)
        elif camid == "IngaasCamHG":
            self.cam = IngaasCam.IngaasCam(1)

        if self.cam.camOK:
            self.camOpen = True

        return self.camOpen

    def CloseCam(self):
        self.cam.Close()

    def start(self):
        if self.started :
            return None
        self.started = True
        self.thread = Thread(target=self.update, args=())
        self.t0 = time.time()
        self.framecount = 0
        self.thread.start()
        return self

    def update(self) :
        while self.started :
            self.read_lock.acquire()
            
            if self.camOpen:
                self.img = self.cam.GetQImage()
            else:
                self.img = QImage(640, 480, QImage.Format.Format_RGB32)
                self.img.fill(Qt.GlobalColor.black)
            
            self.framecount += 1
            if self.framecount >= self.fpsframes:
                self.t1 = time.time()
                self.fps = self.framecount/(self.t1 - self.t0)
                self.framecount = 0
                self.t0 = time.time()

            self.read_lock.release()

    def get(self):
        # self.read_lock.acquire()
        # frame = self.img.copy()
        # self.read_lock.release()
        # return frame
        return self.img.copy()

    def stop(self) :
        self.started = False
        if self.thread.is_alive():
            self.thread.join()

    def __exit__(self, exc_type, exc_value, traceback) :
        self.stop()
        self.CloseCam()


class MainWindow(FormUI, WindowUI):
    #Main stuff
    delayedInit = None

    #Camera stuff
    camOpen = False
    capTimer = None
    videoBusy = False
    img = QImage()
    camThread = None
    fps = 0

    #motors stuff
    posdb = []
    motors = None
    getposTimer = None
    getposBusy = False
    getcontposBusy = False
    movXTimer = None
    movYTimer = None
    movZTimer = None
    getcontposTimer = None
    mouseBusy = False
    mouseGoDown = False
    mouseX0 = 0
    mouseY0 = 0
    mouseX = 0
    mouseY = 0

    #Other stuff
    drawing = False
    marking = False
    mouseDrawingDown = False
    mouseMarkingDown = False
    drawColor = QColor()

    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)
        self.LoadSavedPos()
        self.setupOtherUi()
        self.SetupActions()
        self.show()
        self.setWindowIcon(QIcon("micro.ico"))

        #self.delayedInit = Timer(0.1, self.InitializeDevices)
        #self.delayedInit.start()
        self.InitializeDevices()

    def OnWindowResize(self, event):
        Timer(0.1, self.FixOverlays).start()
        Timer(0.2, self.DrawFixedScale).start()
        if self.camOpen and not self.capTimer.isActive():
            pix = QPixmap(self.camView.width(), self.camView.height())
            pix.fill(Qt.GlobalColor.black)
            img = self.img.scaled(self.camView.size(), Qt.KeepAspectRatio)
            painter = QPainter(pix)
            painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform, True)
            pointx = int(np.round(np.fabs(self.camView.width() - img.width())/2))
            pointy = int(np.round(np.fabs(self.camView.height() - img.height())/2))
            painter.drawImage(pointx, pointy, img)
            painter.end()
            fh = 1
            fv = 1
            if self.fliphCheck.isChecked():
                fh = -1
            if self.flipvCheck.isChecked():
                fv = -1
            if(fv != 1 or fh != 1):
                pix = pix.transformed(QTransform().scale(fh, fv))
            self.camView.setPixmap(pix)
    resizeEvent = OnWindowResize

    def setupOtherUi(self):
        self.scaleOverlay = QLabel(self.camView)
        self.scaleOverlay.setText("")
        self.markerOverlay = QLabel(self.camView)
        self.markerOverlay.setText("")
        self.fscaleOverlay = QLabel(self.camView)
        self.fscaleOverlay.setText("")
        self.camOverlay = QLabel(self.camView)
        self.camOverlay.setText("")

        self.FixOverlays()

        self.camOverlay.mousePressEvent = self.GetMousePress
        self.camOverlay.mouseMoveEvent = self.GetMouseMove
        self.camOverlay.mouseReleaseEvent = self.GetMouseRelease
        self.camOverlay.mouseDoubleClickEvent = self.GetDoubleClick

        self.drawColor = QColor(0, 255, 0, 255)
        self.drawcolorBut.setStyleSheet(f"background-color: rgb({self.drawColor.red()}, {self.drawColor.green()}, {self.drawColor.blue()})")

        self.statusbar.showMessage(f"FPS: {self.fps:.2f} (Camera closed)")

    def FixOverlays(self):
        self.fscaleOverlay.move(0, 0)
        self.fscaleOverlay.resize(self.camView.width(), self.camView.height())
        self.scaleOverlay.move(0, 0)
        self.scaleOverlay.resize(self.camView.width(), self.camView.height())
        self.markerOverlay.move(0, 0)
        self.markerOverlay.resize(self.camView.width(), self.camView.height())
        self.camOverlay.move(0, 0)
        self.camOverlay.resize(self.camView.width(), self.camView.height())

    def LoadSavedPos(self):
        posfilename = "positions.txt"
        if not os.path.isfile(posfilename):
            with open(posfilename, "w") as posfile:
                posfile.write("[0.000, 0.000, 0.000]\t0.000,0.000,0.000\n")
                posfile.write("[12.500, 12.500, 12.500]\t12.500,12.500,12.500\n")
                posfile.write("[25.000, 25.000, 25.000]\t25.000,25.000,25.000\n")
                posfile.close()

        with open(posfilename, "r") as posfile:
            lines = posfile.readlines()
            for i in range(0, len(lines)):
                line = lines[i].strip("\n")
                name = line.split("\t")[0]
                x = line.split("\t")[1].split(",")[0]
                y = line.split("\t")[1].split(",")[1]
                z = line.split("\t")[1].split(",")[2]
                self.posdb.append([name, [float(x), float(y), float(z)]])
                self.savedposCombo.addItem(name)
            posfile.close()
            self.savedposCombo.setCurrentIndex(0)


    def SetupActions(self):
        #Buttons and etc
        self.usbRadio.clicked.connect(self.ChangeCam)
        self.paxRadio.clicked.connect(self.ChangeCam)
        self.ingaasRadio.clicked.connect(self.ChangeCam)
        self.ingaasHGRadio.clicked.connect(self.ChangeCam)
        self.startBut.clicked.connect(self.OnStartButClicked)
        self.stopBut.clicked.connect(self.OnStopButClicked)
        self.saveFrameBut.clicked.connect(self.SaveFrame)
        self.savefullimgBut.clicked.connect(self.SaveFullImg)
        self.exposureSlider.valueChanged.connect(self.OnExpSliderChanged)
        self.gainSlider.valueChanged.connect(self.OnGainSliderChanged)
        self.multiDial.valueChanged.connect(self.UpdateMultiSpin)
        self.multiSpin.valueChanged.connect(self.UpdateMultiDial)
        self.emergBut.clicked.connect(self.StopAllMov)
        self.upBut.clicked.connect(self.MoveUp)
        self.downBut.clicked.connect(self.MoveDown)
        self.leftBut.clicked.connect(self.MoveLeft)
        self.rightBut.clicked.connect(self.MoveRight)
        self.zdownBut.clicked.connect(self.MoveZDown)
        self.zupBut.clicked.connect(self.MoveZUp)
        self.xPosSpin.valueChanged.connect(self.OnXPosChanged)
        self.yPosSpin.valueChanged.connect(self.OnYPosChanged)
        self.zPosSpin.valueChanged.connect(self.OnZPosChanged)
        self.zSlider.sliderMoved.connect(self.OnZSliderChanged)
        self.zSlider.sliderPressed.connect(self.OnZSliderClick)
        self.zSlider.sliderReleased.connect(self.OnZSliderRelease)
        #self.saveposBut.clicked.connect(self.SavePosition)
        self.savedposCombo.lineEdit().returnPressed.connect(self.SavePosition)
        self.gotoposBut.clicked.connect(self.GoToPos)
        self.delposBut.clicked.connect(self.DelPos)
        self.npixelsSpin.valueChanged.connect(self.CalcMicrons)
        self.microcalSpin.valueChanged.connect(self.CalcMicrons)
        self.lensmagSpin.valueChanged.connect(self.CalcCalibrationScale)
        self.zoomSpin.valueChanged.connect(self.CalcCalibrationScale)
        self.drawcolorBut.clicked.connect(self.SetDrawColor)
        self.drawlinemeasBut.clicked.connect(self.DrawLineMeasurement)
        self.clearmeasBut.clicked.connect(self.ClearLineMeasurement)
        self.meassaveBut.clicked.connect(self.SaveMeas)
        self.measloadBut.clicked.connect(self.LoadMeas)
        self.placemarkerBut.clicked.connect(self.PlaceMarker)
        self.clearmarkerBut.clicked.connect(self.ClearMarker)
        self.markersaveBut.clicked.connect(self.SaveMarker)
        self.markerloadBut.clicked.connect(self.LoadMarker)
        self.fixedscaleCheck.stateChanged.connect(self.DrawFixedScale)

        #Video
        self.capTimer = QTimer()
        self.capTimer.timeout.connect(self.CaptureVideo)
        self.capTimer.setInterval(10)

        #Motors
        self.getposTimer = QTimer()
        self.getposTimer.timeout.connect(self.UpdateMotorsPos)
        self.getposTimer.setInterval(100)
        self.getcontposTimer = QTimer()
        self.getcontposTimer.timeout.connect(self.UpdateMotorsContPos)
        self.getcontposTimer.setInterval(100)
        self.movXTimer = QTimer()
        self.movXTimer.timeout.connect(self.MoveXCont)
        self.movXTimer.setInterval(500)
        self.movYTimer = QTimer()
        self.movYTimer.timeout.connect(self.MoveYCont)
        self.movYTimer.setInterval(500)
        self.movZTimer = QTimer()
        self.movZTimer.timeout.connect(self.MoveZCont)
        self.movZTimer.setInterval(500)

        #Menu bar
        self.action_Reserved.triggered.connect(self.ShowReserved)
        self.actionGuide.triggered.connect(self.ShowGuide)
        self.actionAbout_Qt.triggered.connect(self.AboutQt)
        self.actionAbout_Python.triggered.connect(self.AboutPython)
        self.actionAbout.triggered.connect(self.About)
        self.actionExit.triggered.connect(self.Exit)

    def InitializeDevices(self):
        self.motors = CorvusStage.Corvus()
        homing = False
        time.sleep(0.2)
        if self.motors.xOK:
            self.xOK.setPixmap(QPixmap("green_led.png"))
            self.xPosSpin.setValue(self.motors.xPOS)
        elif self.motors.xhoming:
            self.xOK.setPixmap(QPixmap("yellow_led.png"))
            homing = True
        if self.motors.yOK:
            self.yOK.setPixmap(QPixmap("green_led.png"))
            self.yPosSpin.setValue(self.motors.yPOS)
        elif self.motors.yhoming:
            self.yOK.setPixmap(QPixmap("yellow_led.png"))
            homing = True
        if self.motors.zOK:
            self.zOK.setPixmap(QPixmap("green_led.png"))
            self.zPosSpin.setValue(self.motors.zPOS)
        elif self.motors.zhoming:
            self.zOK.setPixmap(QPixmap("yellow_led.png"))
            homing = True

        if homing:
            time.sleep(0.5)
            box = QMessageBox()
            box.setIcon(QMessageBox.Warning)
            box.setText("One or more motors need homing. Before continuing, please confirm that the microscope " +
                        "lens is very far from any object. Since in the homing process the whole tube will " +
                        "move down considerably, this is VERY IMPORTANT!\n\n By clicking OK, you accept that " +
                        "anything bad that might eventually happen is entirely your fault.")
            box.setWindowTitle("Please be careful and patient")
            box.exec()
            self.motors.HomeAll()
            self.getposTimer.start()

    def OpenCamera(self):
        if self.usbRadio.isChecked():
            self.camThread.OpenCam("USBCam")
        elif self.paxRadio.isChecked():
            self.camThread.OpenCam("PAXCam")
        elif self.ingaasRadio.isChecked():
            self.camThread.OpenCam("IngaasCam")
        elif self.ingaasHGRadio.isChecked():
            self.camThread.OpenCam("IngaasCamHG")

        if self.camThread.cam.camOK:
            self.camOpen = True
            self.camOK.setPixmap(QPixmap("green_led.png"))
            self.gainSlider.setValue(int(self.camThread.cam.GetGain()))
            self.exposureSlider.setValue(int(self.camThread.cam.GetExposure()))
            self.CalcCalibrationScale()

    def ChangeCam(self):
        if self.camOpen:
            recap = self.capTimer.isActive()
            self.capTimer.stop()
            self.camOpen = False
            self.camOK.setPixmap(QPixmap("red_led.png"))
            self.camThread.cam.Close()
            time.sleep(0.2)
            del self.camThread.cam
            time.sleep(0.2)
            self.OpenCamera()
            if recap:
                self.capTimer.start()

    def CloseDevices(self):
        if self.camOpen:
            self.camThread.stop()
            self.camThread.CloseCam()
            self.camOpen = False
            self.camThread = None
            self.statusbar.showMessage(f"FPS: {self.fps:.2f} (Camera closed)")
        if self.motors is not None:
            self.motors.Close()
            

    def OnStartButClicked(self):
        self.camThread = None
        self.camThread = ImageAcquisition().start()

        if not self.camOpen:
            self.OpenCamera()

        self.capTimer.start()
        Timer(0.2, self.DrawFixedScale).start()


    def OnStopButClicked(self):
        self.capTimer.stop()
        self.CloseDevices()

    def OnExpSliderChanged(self):
        if self.camOpen:
            self.camThread.cam.SetExposure(self.exposureSlider.value())

    def OnGainSliderChanged(self):
        if self.camOpen:
            self.camThread.cam.SetGain(self.gainSlider.value())

    def UpdateMultiSpin(self):
        self.multiSpin.setValue(self.multiDial.value())

    def UpdateMultiDial(self):
        self.multiDial.setValue(self.multiSpin.value())

    def CaptureVideo(self):
        if not self.videoBusy and self.camOpen:
            self.videoBusy = True
            self.img = self.camThread.get()
            pix = QPixmap(self.camView.width(), self.camView.height())
            pix.fill(Qt.GlobalColor.black)
            img = self.img.scaled(self.camView.width(), self.camView.height())
            painter = QPainter(pix)
            painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform, True)
            pointx = int(np.round(np.fabs(self.camView.width() - img.width())/2))
            pointy = int(np.round(np.fabs(self.camView.height() - img.height())/2))
            painter.drawImage(pointx, pointy, img)
            painter.end()
            fh = 1
            fv = 1
            if self.fliphCheck.isChecked():
                fh = -1
            if self.flipvCheck.isChecked():
                fv = -1
            if(fv != 1 or fh != 1):
                pix = pix.transformed(QTransform().scale(fh, fv))
            self.camView.setPixmap(pix)
            if self.fps != self.camThread.fps:
                self.fps = self.camThread.fps
                self.statusbar.showMessage(f"FPS: {self.fps:.2f}")
            self.videoBusy = False

    def SaveFrame(self):
        recap = self.capTimer.isActive()
        self.capTimer.stop()
        file = QFileDialog.getSaveFileName(self, "Save file", QDir.homePath(), "PNG images (*.png)")
        filename = file[0]
        if filename != "":
            if filename[-4:] != ".png" and filename[-4:] != ".PNG":
                filename = filename + ".png"
            self.img.save(filename)
        if recap:
            self.capTimer.start()

    def SaveFullImg(self):
        recap = self.capTimer.isActive()
        self.capTimer.stop()
        file = QFileDialog.getSaveFileName(self, "Save file", QDir.homePath(), "PNG images (*.png)")
        filename = file[0]
        if filename != "":
            if filename[-4:] != ".png" and filename[-4:] != ".PNG":
                filename = filename + ".png"
            stackPix = QPixmap(self.camView.width(), self.camView.height())
            painter = QPainter(stackPix)
            painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform, True)
            if self.camView.pixmap() is not None:
                painter.drawPixmap(0,0,self.camView.pixmap().scaled(self.camView.size(), Qt.AspectRatioMode.IgnoreAspectRatio))
            if self.scaleOverlay.pixmap() is not None:
                painter.drawPixmap(0,0,self.scaleOverlay.pixmap())
            if self.fscaleOverlay.pixmap() is not None:
                painter.drawPixmap(0,0,self.fscaleOverlay.pixmap())
            if self.markerOverlay.pixmap() is not None:
                painter.drawPixmap(0,0,self.markerOverlay.pixmap())
            painter.end()
            stackPix.toImage().scaled(self.camView.size(), Qt.AspectRatioMode.IgnoreAspectRatio).save(filename)
        if recap:
            self.capTimer.start()

    def SaveMeas(self):
        recap = self.capTimer.isActive()
        self.capTimer.stop()
        file = QFileDialog.getSaveFileName(self, "Save file", QDir.homePath(), "PNG images (*.png)")
        filename = file[0]
        if filename != "":
            if filename[-4:] != ".png" and filename[-4:] != ".PNG":
                filename = filename + ".png"
            self.scaleOverlay.pixmap().toImage().scaled(self.camView.size(), Qt.AspectRatioMode.IgnoreAspectRatio).save(filename)
        if recap:
            self.capTimer.start()

    def LoadMeas(self):
        recap = self.capTimer.isActive()
        self.capTimer.stop()
        file = QFileDialog.getOpenFileName(self, "Load file", QDir.homePath(), "PNG images (*.png)")
        filename = file[0]
        if filename != "":
            pix = QPixmap(filename)
            painter = QPainter(pix)
            if self.scaleOverlay.pixmap() is not None:
                painter.drawPixmap(0, 0, self.scaleOverlay.pixmap())
            painter.drawPixmap(0, 0, self.camOverlay.pixmap())
            self.scaleOverlay.setPixmap(pix)
            painter.end()
        if recap:
            self.capTimer.start()

    def SaveMarker(self):
        recap = self.capTimer.isActive()
        self.capTimer.stop()
        file = QFileDialog.getSaveFileName(self, "Save file", QDir.homePath(), "PNG images (*.png)")
        filename = file[0]
        if filename != "":
            if filename[-4:] != ".png" and filename[-4:] != ".PNG":
                filename = filename + ".png"
            self.markerOverlay.pixmap().toImage().scaled(self.camView.size(), Qt.AspectRatioMode.IgnoreAspectRatio).save(filename)
        if recap:
            self.capTimer.start()

    def LoadMarker(self):
        recap = self.capTimer.isActive()
        self.capTimer.stop()
        file = QFileDialog.getOpenFileName(self, "Load file", QDir.homePath(), "PNG images (*.png)")
        filename = file[0]
        if filename != "":
            pix = QPixmap(filename)
            painter = QPainter(pix)
            if self.markerOverlay.pixmap() is not None:
                painter.drawPixmap(0, 0, self.markerOverlay.pixmap())
            painter.drawPixmap(0, 0, self.camOverlay.pixmap())
            self.markerOverlay.setPixmap(pix)
            painter.end()
        if recap:
            self.capTimer.start()

    def UpdateMotorsPos(self):
        if not self.getposBusy:
            self.getposBusy = True
            self.motors.UpdatePositions()
            xmov = self.motors.AxisMoving(1)
            ymov = self.motors.AxisMoving(2)
            zmov = self.motors.AxisMoving(3)
            if xmov:
                self.xPosSpin.setValue(self.motors.xPOS)
            elif self.motors.xOK:
                self.xOK.setPixmap(QPixmap("green_led.png"))
            if ymov:
                self.yPosSpin.setValue(self.motors.yPOS)
            elif self.motors.yOK:
                self.yOK.setPixmap(QPixmap("green_led.png"))
            if zmov:
                self.zPosSpin.setValue(self.motors.zPOS)
            elif self.motors.zOK:
                self.zOK.setPixmap(QPixmap("green_led.png"))
            if not (xmov or ymov or zmov):
                self.getposTimer.stop()
            self.getposBusy = False

    def MoveUp(self):
        if self.motors.yOK:
            self.motors.MoveRelative(2, self.xyStepSpin.value())
            self.yOK.setPixmap(QPixmap("yellow_led.png"))
            self.getposTimer.start()

    def MoveDown(self):
        if self.motors.yOK:
            self.motors.MoveRelative(2, -self.xyStepSpin.value())
            self.yOK.setPixmap(QPixmap("yellow_led.png"))
            self.getposTimer.start()

    def MoveLeft(self):
        if self.motors.xOK:
            self.motors.MoveRelative(1, -self.xyStepSpin.value())
            self.xOK.setPixmap(QPixmap("yellow_led.png"))
            self.getposTimer.start()

    def MoveRight(self):
        if self.motors.xOK:
            self.motors.MoveRelative(1, self.xyStepSpin.value())
            self.zOK.setPixmap(QPixmap("yellow_led.png"))
            self.getposTimer.start()

    def MoveZUp(self):
        if self.motors.zOK:
            self.motors.MoveRelative(3, self.zStepSpin.value())
            self.zOK.setPixmap(QPixmap("yellow_led.png"))
            self.getposTimer.start()

    def MoveZDown(self):
        if self.motors.zOK:
            self.motors.MoveRelative(3, -self.zStepSpin.value())
            self.zOK.setPixmap(QPixmap("yellow_led.png"))
            self.getposTimer.start()

    def OnXPosChanged(self):
        if self.motors.xOK:
            self.motors.MoveAbsolute(1, self.xPosSpin.value())
            self.xOK.setPixmap(QPixmap("yellow_led.png"))
            self.getposTimer.start()

    def OnYPosChanged(self):
        if self.motors.yOK:
            self.motors.MoveAbsolute(2, self.yPosSpin.value())
            self.yOK.setPixmap(QPixmap("yellow_led.png"))
            self.getposTimer.start()

    def OnZPosChanged(self):
        if self.motors.zOK:
            self.motors.MoveAbsolute(3, self.zPosSpin.value())
            self.zOK.setPixmap(QPixmap("yellow_led.png"))
            self.getposTimer.start()

    def SavePosition(self):
        if self.savedposCombo.currentText() == "":
            self.savedposCombo.setCurrentText("[" + str(self.xPosSpin.value()) + "," +
                                       str(self.yPosSpin.value()) + "," + str(self.zPosSpin.value()) + "]")

        duplicate = True
        while duplicate:
            itemExistsIndex = self.savedposCombo.findText(self.savedposCombo.currentText())
            if itemExistsIndex != -1 and itemExistsIndex != self.savedposCombo.count() - 1:
                dupi = 0
                foundupi = 0
                while foundupi != -1:
                    dupi = dupi + 1
                    foundupi = self.savedposCombo.findText(self.savedposCombo.currentText() + " (" + str(dupi) + ")")
                self.savedposCombo.setCurrentText(self.savedposCombo.currentText() + " (" + str(dupi) + ")")
                duplicate = True
            else:
                if self.savedposCombo.currentText() == self.posdb[len(self.posdb) - 1][0]:
                    dupi = 0
                    foundupi = 0
                    while foundupi != -1:
                        dupi = dupi + 1
                        foundupi = self.savedposCombo.findText(self.savedposCombo.currentText() + " (" + str(dupi) + ")")
                    self.savedposCombo.setCurrentText(self.savedposCombo.currentText() + " (" + str(dupi) + ")")
                    duplicate = True
                else:
                    duplicate = False

        self.posdb.append([self.savedposCombo.currentText(),[self.xPosSpin.value(),
                           self.yPosSpin.value(), self.zPosSpin.value()]])
        with open("positions.txt", "a") as posfile:
            posfile.write(self.savedposCombo.currentText() + "\t" + str(self.xPosSpin.value()) + "," +
                          str(self.yPosSpin.value()) + "," + str(self.zPosSpin.value()) + "\n")
            posfile.close()
        if len(self.posdb) > self.savedposCombo.count():
            self.savedposCombo.addItem(self.savedposCombo.currentText())
            self.savedposCombo.setCurrentIndex(self.savedposCombo.count() - 1)

    def GoToPos(self):
        i = self.savedposCombo.currentIndex()
        self.xPosSpin.setValue(self.posdb[i][1][0])
        self.yPosSpin.setValue(self.posdb[i][1][1])
        self.zPosSpin.setValue(self.posdb[i][1][2])

    def DelPos(self):
        i = self.savedposCombo.currentIndex()
        if i > 2:
            self.savedposCombo.removeItem(i)
            self.posdb.pop(i)
            self.RebuildPositionsFile()
        else:
            QMessageBox.warning(self, "Wait!", "Not permitted to delete base positions!")

    def RebuildPositionsFile(self):
        with open("positions.txt", "w") as posfile:
            for i in range(0, len(self.posdb)):
                posfile.write(self.posdb[i][0] + "\t" + str(self.posdb[i][1][0]) + "," +
                            str(self.posdb[i][1][1]) + "," + str(self.posdb[i][1][2]) + "\n")
            posfile.close()

    def UpdateMotorsContPos(self):
        if not self.getcontposBusy:
            self.getcontposBusy = True
            self.motors.UpdatePositions()
            xmov = self.motors.AxisMoving(1)
            ymov = self.motors.AxisMoving(2)
            zmov = self.motors.AxisMoving(3)
            if xmov and self.motors.xOK:
                self.xPosSpin.setValue(self.motors.xPOS)
                self.xOK.setPixmap(QPixmap("yellow_led.png"))
            elif self.motors.xOK:
                self.xOK.setPixmap(QPixmap("green_led.png"))
            if ymov and self.motors.yOK:
                self.yPosSpin.setValue(self.motors.yPOS)
                self.yOK.setPixmap(QPixmap("yellow_led.png"))
            elif self.motors.yOK:
                self.yOK.setPixmap(QPixmap("green_led.png"))
            if zmov and self.motors.zOK:
                self.zPosSpin.setValue(self.motors.zPOS)
                self.zOK.setPixmap(QPixmap("yellow_led.png"))
            elif self.motors.zOK:
                self.zOK.setPixmap(QPixmap("green_led.png"))
            self.getcontposBusy = False

    def OnZSliderClick(self):
        self.OnZPosChanged()
        self.movZTimer.start()
        if self.motors.zOK:
            self.zOK.setPixmap(QPixmap("yellow_led.png"))
            self.getcontposTimer.start()

    def OnZSliderChanged(self):
        self.motors.CalculateContParams(3, self.zSlider.value()/1000.0, 0.008875*np.exp(0.04721*self.multiDial.value()))
        self.movZTimer.setInterval(self.motors.zWait*1000)

    def OnZSliderRelease(self):
        self.movZTimer.stop()
        self.getcontposTimer.stop()
        self.zSlider.setValue(0)
        self.getposTimer.start()
        self.motors.StopAll()

    def MoveXCont(self):
        self.motors.MoveRelative(1, self.motors.xStep)

    def MoveYCont(self):
        self.motors.MoveRelative(2, self.motors.yStep)

    def MoveZCont(self):
        self.motors.MoveRelative(3, self.motors.zStep)

    def StopAllMov(self):
        self.motors.StopAll()

    def GetMousePress(self, event):
        self.FixOverlays()

        self.mouseX0 = event.x()
        self.mouseY0 = event.y()
        self.mouseX = self.mouseX0
        self.mouseY = self.mouseY0

        if event.button() == 1 and self.drawing and self.camOpen:
            self.mouseDrawingDown = True
            self.DrawMeasOverlay()
        
        elif event.button() == 1 and self.marking and self.camOpen:
            self.mouseMarkingDown = True
            self.DrawMarkerOverlay(self.markersizeSpin.value())

        if event.button() == 2:
            self.mouseGoDown = True
            self.mouseX0 = int(self.camView.width() / 2)
            self.mouseY0 = int(self.camView.height() / 2)
            self.mouseX = self.mouseX0
            self.mouseY = self.mouseY0
            dx = self.mouseX - self.mouseX0
            dy = self.mouseY - self.mouseY0
            self.motors.CalculateContParams(1, 2*dx/self.camView.width(), 0.008875*np.exp(0.04721*self.multiDial.value()))
            self.motors.CalculateContParams(2, 2*dy/self.camView.height(), 0.008875*np.exp(0.04721*self.multiDial.value()))
            self.movXTimer.setInterval(self.motors.xWait*1000)
            self.movYTimer.setInterval(self.motors.yWait*1000)

            self.movXTimer.start()
            self.movYTimer.start()
            if self.motors.xOK:
                self.xOK.setPixmap(QPixmap("yellow_led.png"))
            if self.motors.yOK:
                self.yOK.setPixmap(QPixmap("yellow_led.png"))
            self.getcontposTimer.start()

            self.DrawGoOverlay()
            cursor = QCursor()
            cursor.setShape(Qt.SizeAllCursor)
            cursor.setPos(self.camOverlay.mapToGlobal(QPoint(self.mouseX, self.mouseY)))
            QApplication.setOverrideCursor(cursor)

    def GetMouseMove(self, event):
        mX = event.x()
        mY = event.y()
        lock = False
        if mX < 0:
            mX = 0
            lock = True
        if mX > self.camView.width():
            mX = self.camView.width()
            lock = True
        if mY < 0:
            mY = 0
            lock = True
        if mY > self.camView.height():
            mY = self.camView.height()
            lock = True
        if lock:
            cursor = QCursor()
            cursor.setPos(self.camOverlay.mapToGlobal(QPoint(mX, mY)))
            QApplication.setOverrideCursor(cursor)

        self.mouseX = mX
        self.mouseY = mY

        if self.mouseDrawingDown and self.camOpen:
            self.DrawMeasOverlay()

        elif self.mouseMarkingDown and self.camOpen:
            self.DrawMarkerOverlay(self.markersizeSpin.value())
        
        elif self.mouseGoDown:
            self.DrawGoOverlay()
            dx = self.mouseX - self.mouseX0
            dy = -(self.mouseY - self.mouseY0)
            self.motors.CalculateContParams(1, 2*dx/self.camView.width(), 0.008875*np.exp(0.04721*self.multiDial.value()))
            self.motors.CalculateContParams(2, 2*dy/self.camView.height(), 0.008875*np.exp(0.04721*self.multiDial.value()))
            self.movXTimer.setInterval(self.motors.xWait*1000)
            self.movYTimer.setInterval(self.motors.yWait*1000)

    def GetMouseRelease(self, event):
        if event.button() == 1 and self.mouseDrawingDown:
            self.mouseDrawingDown = False
            self.drawing = False
            self.drawlinemeasBut.setDown(False)
            pix = QPixmap(self.scaleOverlay.width(), self.scaleOverlay.height())
            pix.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pix)
            painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform, True)
            if self.scaleOverlay.pixmap() is not None:
                painter.drawPixmap(0, 0, self.scaleOverlay.pixmap())
            painter.drawPixmap(0, 0, self.camOverlay.pixmap())
            self.scaleOverlay.setPixmap(pix)
            painter.end()
            pix0 = QPixmap(self.scaleOverlay.width(), self.scaleOverlay.height())
            pix0.fill(Qt.GlobalColor.transparent)
            self.camOverlay.setPixmap(pix0)
        if event.button() == 1 and self.mouseMarkingDown:
            self.mouseMarkingDown = False
            self.marking = False
            self.placemarkerBut.setDown(False)
            pix = QPixmap(self.markerOverlay.width(), self.markerOverlay.height())
            pix.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pix)
            painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform, True)
            if self.markerOverlay.pixmap() is not None:
                painter.drawPixmap(0, 0, self.markerOverlay.pixmap())
            painter.drawPixmap(0, 0, self.camOverlay.pixmap())
            self.markerOverlay.setPixmap(pix)
            painter.end()
            pix0 = QPixmap(self.markerOverlay.width(), self.markerOverlay.height())
            pix0.fill(Qt.GlobalColor.transparent)
            self.camOverlay.setPixmap(pix0)
        if event.button() == 2 and self.mouseGoDown:
            self.mouseGoDown = False
            self.movXTimer.stop()
            self.movYTimer.stop()
            pix = QPixmap(self.scaleOverlay.width(), self.scaleOverlay.height())
            pix.fill(Qt.GlobalColor.transparent)
            self.camOverlay.setPixmap(pix)
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            self.getcontposTimer.stop()
            self.getposTimer.start()
            self.motors.StopAll()

    def GetDoubleClick(self, event):
        if event.button() == 1 and self.camOpen:
            self.FixOverlays()
            dx = event.x() - self.camView.width() / 2
            dy = event.y() - self.camView.height() / 2
            ratioView = self.camView.width()/self.camView.height()
            ratioFrame = self.camThread.cam.frameW/self.camThread.cam.frameH
            scale = 1
            if ratioView < ratioFrame:
                scale = self.camThread.cam.frameW/self.camView.width()
            else:
                scale = self.camThread.cam.frameH/self.camView.height()
            dx = dx*scale
            dy = dy*scale
            dxm = dx/self.microcalSpin.value()
            dym = -dy/self.microcalSpin.value()
            self.xPosSpin.setValue(self.xPosSpin.value() + dxm/1000.0)
            self.yPosSpin.setValue(self.yPosSpin.value() + dym/1000.0)

    def CreateBlankImg(self, w, h):
        img = QImage(w, h, QImage.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        return img

    def SetDrawColor(self):
        self.drawColor = QColorDialog.getColor()
        self.drawcolorBut.setStyleSheet(f"background-color: rgb({self.drawColor.red()}, {self.drawColor.green()}, {self.drawColor.blue()})")
        self.drawcolorBut.update()

    def SetDrawPen(self, painter, thick, color, fill=False):
        pen = painter.pen()
        pen.setColor(color)
        pen.setWidthF(thick)
        painter.setPen(pen)
        if fill:
            painter.setBrush(QBrush(color, Qt.BrushStyle.SolidPattern))
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform, True)
        return painter

    def DrawGoOverlay(self):
        self.FixOverlays()

        thick = self.drawthickSpin.value()*2
        endhs = thick*3

        dx = self.mouseX - self.mouseX0
        dy = -(self.mouseY - self.mouseY0)
        if np.abs(dx) < 0.001:
            dx = 0.001
        if np.abs(dy) < 0.001:
            dy = 0.001
        slope = dx/dy
        length = np.sqrt(dx**2 + dy**2)
        cosine = dx/length
        sine = dy/length

        endx = np.sqrt(endhs**2/(slope**2 + 1))
        endy = slope*endx
        
        start1 = QPoint(int(np.round(self.mouseX0 + endx)), int(np.round(self.mouseY0 + endy)))
        start2 = QPoint(int(np.round(self.mouseX0 - endx)), int(np.round(self.mouseY0 - endy)))

        arrowx = self.mouseX - endhs*2*cosine
        arrowy = self.mouseY + endhs*2*sine
        arrow1 = QPoint(int(np.round(arrowx + endx)), int(np.round(arrowy + endy)))
        arrow2 = QPoint(int(np.round(arrowx - endx)), int(np.round(arrowy - endy)))
        arrow3 = QPoint(self.mouseX, self.mouseY)

        pix = QPixmap(self.scaleOverlay.width(), self.scaleOverlay.height())
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter = self.SetDrawPen(painter, 2*self.thick, self.drawColor, True)
        painter.setFont(QFont("Sans", pointSize=int(np.round(11*(thick**(1/3))))))
        painter.drawLine(start1, start2)
        painter.drawLine(QPoint(self.mouseX0, self.mouseY0), QPoint(arrowx, arrowy))
        painter.drawPolygon(QPolygon([arrow1, arrow2, arrow3]))
        painter.end()
        self.camOverlay.setPixmap(pix)

    def DrawMeasOverlay(self):
        self.FixOverlays()

        thick = self.drawthickSpin.value()
        endhs = thick*3

        dx = self.mouseX - self.mouseX0
        dy = -(self.mouseY - self.mouseY0)
        if np.abs(dx) < 0.001:
            dx = 0.001
        if np.abs(dy) < 0.001:
            dy = 0.001
        slope = dx/dy

        endx = np.sqrt(endhs**2/(slope**2 + 1))
        endy = slope*endx
        
        start1 = QPoint(int(np.round(self.mouseX0 + endx)), int(np.round(self.mouseY0 + endy)))
        start2 = QPoint(int(np.round(self.mouseX0 - endx)), int(np.round(self.mouseY0 - endy)))
        end1 = QPoint(int(np.round(self.mouseX + endx)), int(np.round(self.mouseY + endy)))
        end2 = QPoint(int(np.round(self.mouseX - endx)), int(np.round(self.mouseY - endy)))

        ratioView = self.camView.width()/self.camView.height()
        ratioFrame = self.camThread.cam.frameW/self.camThread.cam.frameH
        scale = 1
        if ratioView < ratioFrame:
            scale = self.camThread.cam.frameW/self.camView.width()
        else:
            scale = self.camThread.cam.frameH/self.camView.height()
        dx = dx*scale
        dy = dy*scale

        dist = np.sqrt(dx**2 + dy**2)
        self.npixelsSpin.setValue(int(dist))
        meastring = "{:.2f}".format(self.micronSpin.value()) + " " + u"\u03BC" + "m"

        midx = self.mouseX0 + (self.mouseX - self.mouseX0)/2
        midy = self.mouseY0 + (self.mouseY - self.mouseY0)/2
        textx = int(np.round(-len(meastring)*4*(thick**(1/3))))
        texty = int(np.round(-2*thick - 8))
        textangle = 90 + 180*np.arctan(slope)/np.pi
        if textangle > 90:
            textangle += 180

        pix = QPixmap(self.scaleOverlay.width(), self.scaleOverlay.height())
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter = self.SetDrawPen(painter, thick, self.drawColor, False)
        painter.setFont(QFont("Sans", pointSize=int(np.round(11*(thick**(1/3))))))
        painter.drawLine(start1, start2)
        painter.drawLine(QPoint(self.mouseX0, self.mouseY0), QPoint(self.mouseX, self.mouseY))
        painter.drawLine(end1, end2)
        painter.translate(midx, midy)
        painter.rotate(textangle)
        painter.drawText(QPoint(textx, texty), meastring)
        painter.end()
        self.camOverlay.setPixmap(pix)

    def DrawLineMeasurement(self):
        self.drawing = True
        self.drawlinemeasBut.setDown(True)

    def ClearLineMeasurement(self):
        pix = QPixmap(self.markerOverlay.width(), self.markerOverlay.height())
        pix.fill(Qt.GlobalColor.transparent)
        self.scaleOverlay.setPixmap(pix)

    def DrawMarkerOverlay(self, size):
        text = self.markerEdit.text()

        markertype = 0
        if self.markcircleRadio.isChecked():
            markertype = 0
        elif self.marktriRadio.isChecked():
            markertype = 1
        elif self.marksquareRadio.isChecked():
            markertype = 2
        elif self.markstarRadio.isChecked():
            markertype = 3
        elif self.marktextRadio.isChecked():
            markertype = 4

        pix = QPixmap(self.markerOverlay.width(), self.markerOverlay.height())
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter = self.SetDrawPen(painter, self.drawthickSpin.value(), self.drawColor, False)
        painter.setFont(QFont("Sans", pointSize=size))

        if markertype == 0:
            painter.drawEllipse(QPoint(self.mouseX, self.mouseY), int(size/2), int(size/2))
        elif markertype == 1:
            p1 = QPoint(int(self.mouseX - size/2), int(self.mouseY + size/2))
            p2 = QPoint(int(self.mouseX + size/2), int(self.mouseY + size/2))
            p3 = QPoint(int(self.mouseX), int(self.mouseY - size/2))
            painter.drawLine(p1, p2)
            painter.drawLine(p2, p3)
            painter.drawLine(p3, p1)
        elif markertype == 2:
            painter.drawRect(self.mouseX, self.mouseY, size, size)
        elif markertype == 3:
            r0 = size/2
            alpha = 2.0*np.pi/10.0
            omega = alpha*11
            r1 = r0*(11 % 2 + 1)/2
            p0 = QPoint(int(np.round(r1 * np.sin(omega) + self.mouseX)), int(np.round(r1 * np.cos(omega) + self.mouseY)))
            for i in reversed(range(1, 11)):
                r1 = r0*(i % 2 + 1)/2
                omega = alpha * i
                p1 = QPoint(int(np.round(r1 * np.sin(omega) + self.mouseX)), int(np.round(r1 * np.cos(omega) + self.mouseY)))
                painter.drawLine(p0, p1)
                p0 = p1

        elif markertype == 4:
            painter.drawText(QPoint(self.mouseX, self.mouseY), text)
        
        painter.end()

        self.camOverlay.setPixmap(pix)

    def PlaceMarker(self):
        self.marking = True
        self.placemarkerBut.setDown(True)

    def ClearMarker(self):
        pix = QPixmap(self.markerOverlay.width(), self.markerOverlay.height())
        pix.fill(Qt.GlobalColor.transparent)
        self.markerOverlay.setPixmap(pix)

    def DrawFixedScale(self):
        self.FixOverlays()

        if self.fixedscaleCheck.isChecked() and self.camOpen:
            scaleColor = QColor(220, 220, 220, 255)
            linewidth = 2
            basesize = int(np.round(self.camView.width()/2))
            midtickh1 = 10
            midtickh2 = 6
            ratioView = self.camView.width()/self.camView.height()
            ratioFrame = self.camThread.cam.frameW/self.camThread.cam.frameH
            scale = 1
            if ratioView < ratioFrame:
                scale = self.camThread.cam.frameW/self.camView.width()
            else:
                scale = self.camThread.cam.frameH/self.camView.height()
            micronScale = basesize*scale/self.microcalSpin.value()
            if micronScale <= 10:
                micronScale = int(np.round(micronScale))
            elif micronScale < 100:
                micronScale = 10*int(np.round(micronScale/10))
            else:
                micronScale = 100*int(np.round(micronScale/100))
            roundsize = int(np.round(micronScale*self.microcalSpin.value()/scale))
            posI = int(np.round((self.camView.width()/2 - roundsize/2)))
            posF = int(np.round((self.camView.width()/2 + roundsize/2)))
            bottom = self.camView.height() - midtickh1*2
            posmidtick = int(np.round(self.camView.width()/2)) - (int(np.round(linewidth/2)))
            posquartertick1 = posmidtick + int(np.round(roundsize/4)) - (int(np.round(linewidth/2)))
            posquartertick2 = posmidtick - int(np.round(roundsize/4)) - (int(np.round(linewidth/2)))
            labelHeight = int(np.round(midtickh1*6.5))

            pix = QPixmap(self.fscaleOverlay.width(), self.fscaleOverlay.height())
            pix.fill(Qt.GlobalColor.transparent)
            now = datetime.datetime.now()
            painter = QPainter(pix)
            painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform, True)
            self.SetDrawPen(painter, linewidth, QColor(0, 0, 0, 160), True)
            painter.drawRect(0, self.camView.height() - labelHeight, self.camView.width(), labelHeight)
            self.SetDrawPen(painter, linewidth, scaleColor, False)
            painter.drawLine(QPoint(posI, bottom), QPoint(posF, bottom))
            painter.drawLine(QPoint(posI, bottom - midtickh1), QPoint(posI, bottom + midtickh1))
            painter.drawLine(QPoint(posF, bottom - midtickh1), QPoint(posF, bottom + midtickh1))
            painter.drawLine(QPoint(posmidtick, bottom - midtickh1), QPoint(posmidtick, bottom + midtickh1))
            painter.drawLine(QPoint(posquartertick1, bottom - midtickh2), QPoint(posquartertick1, bottom + midtickh2))
            painter.drawLine(QPoint(posquartertick2, bottom - midtickh2), QPoint(posquartertick2, bottom + midtickh2))
            painter.setFont(QFont("Sans", pointSize=int(1.5*midtickh1)))
            rect = QRectF(0, bottom - 4*midtickh1, self.camView.width(), midtickh1*3)
            rect2 = QRectF(0, bottom - 1*midtickh1, self.camView.width(), midtickh1*3)
            painter.drawText(rect, str(micronScale) + " " + u"\u03BC" + "m", QTextOption(Qt.AlignmentFlag.AlignHCenter))
            painter.drawText(rect2, " LCO", QTextOption(Qt.AlignmentFlag.AlignLeft))
            painter.drawText(rect2, str(now.year) + "-" + str(now.month) + "-" + str(now.day) + " ", QTextOption(Qt.AlignmentFlag.AlignRight))
            painter.end()
            self.fscaleOverlay.setPixmap(pix)
        else:
            pix = QPixmap(self.fscaleOverlay.width(), self.fscaleOverlay.height())
            pix.fill(Qt.GlobalColor.transparent)
            self.fscaleOverlay.setPixmap(pix)

    def CalcCalibrationScale(self):
        if self.camOpen:
            size = self.camThread.cam.ccdSize[0]/(self.lensmagSpin.value()*self.zoomSpin.value())
            scale = self.camThread.cam.maxW/size
            magic = 1.52
            self.microcalSpin.setValue(scale*magic)
        else:
            size = 12986/(self.lensmagSpin.value()*self.zoomSpin.value())
            scale = 2448/size
            magic = 1.52
            self.microcalSpin.setValue(scale*magic)
        self.DrawFixedScale()

    def CalcMicrons(self):
        microns = self.npixelsSpin.value()/self.microcalSpin.value()
        self.micronSpin.setValue(microns)

    def ShowReserved(self):
        aboutText = f"<p>In the future, there is going to be more functions in this menu, maybe even a neat toolbar!</p>" \
                    "<p>It is on my To-Do list, honest!</p>"

        about = QMessageBox()
        about.setWindowTitle("Reserved")
        about.setText("<b>Reserved Menu</b>")
        about.setInformativeText(aboutText)
        about.setStandardButtons(QMessageBox.StandardButton.Ok)
        about.setDefaultButton(QMessageBox.StandardButton.Ok)
        about.setIconPixmap(QPixmap(f"hourglass.png").scaledToHeight(64, Qt.TransformationMode.SmoothTransformation))
        about.show()
        about.exec()

    def ShowGuide(self):
        aboutText = f"<p>In the future, this will be a short guide.</p>" \
                    "<p>It is not available yet.</p>"

        about = QMessageBox()
        about.setWindowTitle("Quick Guide")
        about.setText("<b>Quick Guide</b>")
        about.setInformativeText(aboutText)
        about.setStandardButtons(QMessageBox.StandardButton.Ok)
        about.setDefaultButton(QMessageBox.StandardButton.Ok)
        about.setIconPixmap(QPixmap(f"guide.png").scaledToHeight(64, Qt.TransformationMode.SmoothTransformation))
        about.show()
        about.exec()

    def AboutQt(self):
        QMessageBox.aboutQt(self, "About Qt")

    def AboutPython(self):
        aboutText = f"<p>This software is using Python version {sys.version}.</p>" \
                    "<p>It uses the following modules:<br>"

        include_na = True
        moduleslist = []
        for module in sys.modules:
            fullnm = str(sys.modules[module])
            if not "." in module and not module.startswith("_") and not "(built-in)" in fullnm:
                try:
                    if ilmd_available:
                        moduleslist.append(f"{module}\t{importlib.metadata.version(module)}, ")
                except:
                    try:
                        moduleslist.append(f"{module}\t{sys.modules[module].__version__}, ")
                    except:
                        try:
                            if type(sys.modules[module].version) is str:
                                moduleslist.append(f"{module}\t{sys.modules[module].version}, ")
                            else:
                                moduleslist.append(f"{module}\t{sys.modules[module].version()}, ")
                        except:
                            try:
                                moduleslist.append(f"{module}\t{sys.modules[module].VERSION}, ")
                            except:
                                if include_na:
                                    moduleslist.append(f"{module}, ")

        moduleslist.sort(key=str.lower)
        for text in moduleslist:
            aboutText += text
        aboutText = aboutText[:-2] + ".</p>"

        about = QMessageBox()
        about.setWindowTitle("About Python")
        about.setText("<b>About Python</b>")
        about.setInformativeText(aboutText)
        about.setStandardButtons(QMessageBox.StandardButton.Ok)
        about.setDefaultButton(QMessageBox.StandardButton.Ok)
        pyicon = np.random.randint(1, 3)
        about.setIconPixmap(QPixmap(f"python_{pyicon}.png").scaled(64,64, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
        about.show()
        about.exec()

    def About(self):
        aboutText = "<p><b>LCO Microscope Move PRO v.0.9</b></p>" \
                    "<p>This software is made with Python and PyQt.</p>" \
                    "<p>Copyright &copy; 2020</p>" \
                    "<p>By Paulo Jarschel, no rights reserved.</p>" \
                    "<p>Edited by Eduardo Sell Gonçalves, no rights reserved.</p>" \

        QMessageBox.about(self, "About", aboutText)

    def Exit(self):
        self.capTimer.stop()
        self.CloseDevices()
        QCoreApplication.quit()
        
    
    def closeEvent(self, event):
        self.capTimer.stop()
        self.CloseDevices()


#Run
if __name__ == "__main__":

    app = QApplication(sys.argv)
    window = MainWindow()

    sys.exit(app.exec())