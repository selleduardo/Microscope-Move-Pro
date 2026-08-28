import pystages
from pystages.exceptions import ConnectionFailure


class Corvus:
    """
    Wrapper around pystages.corvus.Corvus exposing the same interface as
    NewportMotors, so MainWindow can drive either backend with minimal changes.

    The Corvus controller talks to X/Y/Z over a single serial connection (unlike
    the old per-axis Newport controllers), so per-axis status here just mirrors
    the single connection/motion state.
    """

    stage = None

    posLimit = 25  # mm, software safety clamp - adjust to the real stage travel range
    maxXYVel = 0.4  # mm/s, jog speed scale for X/Y
    maxZVel = 0.16  # mm/s, jog speed scale for Z
    jogInterval = 0.1  # s, fixed tick used for continuous jog (matches UI poll rate)

    def __init__(self, port_name="COM5"):
        self.xOK = self.yOK = self.zOK = False
        self.xhoming = self.yhoming = self.zhoming = False
        self.xPOS = self.yPOS = self.zPOS = 0.0
        self.xStep = self.yStep = self.zStep = 0.0
        self.xWait = self.yWait = self.zWait = self.jogInterval

        try:
            self.stage = pystages.corvus.Corvus(port_name)
        except ConnectionFailure:
            print("Error connecting to Corvus stage controller")
            return
        except Exception as e:
            print(f"Error connecting to Corvus stage controller: {e}")
            return

        homed = True
        try:
            for axis in (1, 2, 3):
                if int(self.stage.send_receive(f"{axis} getcaldone")) != 3:
                    homed = False
        except Exception:
            pass

        if homed:
            self.xOK = self.yOK = self.zOK = True
            self.UpdatePositions()
        else:
            self.xhoming = self.yhoming = self.zhoming = True

    def Close(self):
        if self.stage is not None:
            try:
                self.stage.serial.close()
            except Exception:
                pass

    def HomeAll(self):
        if self.stage is None:
            return
        self.xOK = self.yOK = self.zOK = False
        self.xhoming = self.yhoming = self.zhoming = True
        try:
            self.stage.calibrate()
        except Exception:
            pass
        self.xhoming = self.yhoming = self.zhoming = False
        self.xOK = self.yOK = self.zOK = True
        self.UpdatePositions()

    def MoveAbsolute(self, axis, pos):
        if self.stage is None:
            return
        if pos > self.posLimit:
            pos = self.posLimit
        pos_um = pos * 1000.0
        p = self.stage.position
        if axis == 1 or axis == "x":
            p.x = pos_um
        elif axis == 2 or axis == "y":
            p.y = pos_um
        elif axis == 3 or axis == "z":
            p.z = pos_um
        self.stage.position = p

    def MoveRelative(self, axis, delta):
        if self.stage is None:
            return
        delta_um = delta * 1000.0
        dx = dy = dz = 0.0
        if axis == 1 or axis == "x":
            dx = delta_um
        elif axis == 2 or axis == "y":
            dy = delta_um
        elif axis == 3 or axis == "z":
            dz = delta_um
        self.stage.move_relative(dx, dy, dz)

    def CalculateContParams(self, axis, amp, velmult):
        if self.stage is None:
            return
        sign = 1.0 if amp >= 0 else -1.0
        maxvel = self.maxXYVel if axis in (1, 2, "x", "y") else self.maxZVel
        vel_mm_s = min(abs(amp) * maxvel * velmult, maxvel)
        vel_mm_s = max(vel_mm_s, 0.001)

        try:
            self.stage.velocity = vel_mm_s * 1000.0
        except Exception:
            pass

        step_mm = sign * vel_mm_s * self.jogInterval
        if axis == 1 or axis == "x":
            self.xStep = step_mm
        elif axis == 2 or axis == "y":
            self.yStep = step_mm
        elif axis == 3 or axis == "z":
            self.zStep = step_mm

    def Stop(self, axis):
        self.StopAll()

    def StopAll(self):
        if self.stage is None:
            return
        try:
            self.stage.send("abort")
        except Exception:
            pass

    def GetPos(self, axis):
        if axis == 1 or axis == "x":
            return self.xPOS
        if axis == 2 or axis == "y":
            return self.yPOS
        if axis == 3 or axis == "z":
            return self.zPOS

    def UpdatePositions(self):
        if self.stage is None:
            return
        try:
            p = self.stage.position
        except Exception:
            return
        self.xPOS = p.x / 1000.0
        self.yPOS = p.y / 1000.0
        self.zPOS = p.z / 1000.0

    def AxisMoving(self, axis):
        if self.stage is None:
            return False
        try:
            return self.stage.is_moving
        except Exception:
            return False
