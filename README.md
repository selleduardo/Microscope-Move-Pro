# Microscope-Move-Pro

Python application to control a microscope via a Corvus motorized stage, and capture its image via standard USB cv-compatible camera.

## Running (development)

With dependencies installed (`pip install -r requirements.txt`):

```
python src/main.py
```

Can be launched from any working directory; icons and `positions.txt` are resolved relative to the repository itself, not the current directory.

## Structure

```
src/
  main.py            # entry point
  gui/                # MainWindow.py + MainWindow_UI.ui
  hardware/           # CorvusStage.py, USBCam.py
resources/
  icons/               # UI icons (LEDs, window icon, buttons)
  images/              # About-dialog images
scripts/
  testCorvus.py        # manual smoke test for the Corvus stage driver
legacy/                # superseded modules (Newport motors, PAXCam, IngaasCam, old MainWindow) kept for reference
run.bat                # Windows launcher, see "Deploying on a shared Windows PC"
positions.txt          # saved stage positions, generated on first run (git-ignored)
```
