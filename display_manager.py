from __future__ import with_statement
import paho.mqtt.client as mqtt
import Adafruit_CharLCD.PCF_CharLCD as char_lcd
import command_processor as cnfg_file
import RPi.GPIO as GPIO
from datetime import datetime
import time
from threading import Thread, Lock
import cloud_sender
import fermentation_params as params


BUTTON_SET = 16
BUTTON_UP = 20
BUTTON_DOWN = 21

PAGE_MAIN = 0
PAGE_BEER_INFO = 1
PAGE_FERM_SESSION = 2
PAGE_SETTINGS = 3
PAGE_SETUP = 4
PAGE_SETUP_TEMP = 5
PAGE_SETUP_DELTA = 6
PAGE_SETUP_HEATER = 7
PAGE_CONF_TEMP = 8

TEMP_TOPIC = "smarthomebrew/sensor/temperatura"
__lines = 4
__cols = 20
__busnum = 1
__address = 0x3f
__lcd = char_lcd.PCF_CharLCD(0, address=__address, busnum=__busnum, cols=__cols, lines=__lines)
__current_page = None
__set_pressed = None
__setup_opt = None
__last_action = None
__aux_setup = None

# Custom font setup
__segs = [[0b11111, 0b11111, 0b11111, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000],
          [0b11100, 0b11110, 0b11111, 0b11111, 0b11111, 0b11111, 0b11111, 0b11111],
          [0b11111, 0b11111, 0b11111, 0b11111, 0b11111, 0b11111, 0b01111, 0b00111],
          [0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b11111, 0b11111, 0b11111],
          [0b11111, 0b11111, 0b11111, 0b11111, 0b11111, 0b11111, 0b11110, 0b11100],
          [0b11111, 0b11111, 0b11111, 0b00000, 0b00000, 0b00000, 0b11111, 0b11111],
          [0b11111, 0b11111, 0b00000, 0b00000, 0b00000, 0b11111, 0b11111, 0b11111],
          [0b00111, 0b01111, 0b11111, 0b11111, 0b11111, 0b11111, 0b11111, 0b11111]]

# Create digits and stuff from the custom characters
__digits = [["\x07\x00\x01", "\x02\x03\x04"],
            ["\xfe\xfe\x07", "\xfe\xfe\xff"],
            ["\x05\x05\x01", "\x02\x06\x06"],
            ["\x05\x05\x01", "\x06\x06\x04"],
            ["\x02\x03\x01", "\xfe\xfe\xff"],
            ["\xff\x05\x05", "\x06\x06\x04"],
            ["\x07\x05\x05", "\x02\x06\x04"],
            ["\x00\x00\x01", "\xfe\x07\xfe"],
            ["\x07\x05\x01", "\x02\x06\x04"],
            ["\x07\x05\x01", "\x06\x06\x04"]]

__neg = ["\x03\x03", "\xfe\xfe"]
__dot = ["\xfe", "\x2e"]
__space = ["\xfe", "\xfe"]
__blank = ["\xfe\xfe\xfe", "\xfe\xfe\xfe"]
__degree = ["\xdf\x43", "\xfe\xfe"]
__prev_digits = None


def gpio_setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_SET, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(BUTTON_UP, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(BUTTON_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(BUTTON_SET, GPIO.BOTH, callback=button_pressed, bouncetime=300)
    GPIO.add_event_detect(BUTTON_UP, GPIO.FALLING, callback=button_pressed, bouncetime=500)
    GPIO.add_event_detect(BUTTON_DOWN, GPIO.FALLING, callback=button_pressed, bouncetime=500)


def button_pressed(pin):
    global PAGE_MAIN
    global PAGE_FERM_SESSION
    global PAGE_SETTINGS
    global PAGE_BEER_INFO
    global PAGE_SETUP
    global PAGE_SETUP_TEMP
    global PAGE_SETUP_DELTA
    global PAGE_SETUP_HEATER
    global PAGE_CONF_TEMP

    global __prev_digits
    global __current_page
    global __lcd
    global __set_pressed
    global __setup_opt
    global __last_action
    global __aux_setup

    __last_action = now = datetime.now()
    if pin == BUTTON_SET:
        if GPIO.input(pin):
            if __current_page < PAGE_SETUP:
                if __set_pressed is None or (now - __set_pressed).total_seconds() > 10:
                    __set_pressed = now
            else:
                if __current_page == PAGE_SETUP:
                    if __setup_opt == 0:
                        __aux_setup = params.fermentation_temp
                        __current_page = PAGE_SETUP_TEMP
                        show_setup_temp_ferm()
                    elif __setup_opt == 1:
                        __aux_setup = params.temp_delta
                        __current_page = PAGE_SETUP_DELTA
                        show_setup_delta_temp()
                    elif __setup_opt == 2:
                        __aux_setup = params.heater
                        __current_page = PAGE_SETUP_HEATER
                        show_setup_heater()
                elif __current_page == PAGE_SETUP_TEMP:
                    save_temp_ferm()
                elif __current_page == PAGE_SETUP_DELTA:
                    save_temp_delta()
                elif __current_page == PAGE_SETUP_HEATER:
                    save_heater()
        else:
            if __current_page < PAGE_SETUP and 2 < (now - __set_pressed).total_seconds() <= 5:
                # Show configurations screen
                __current_page = PAGE_SETUP
                __setup_opt = 0
                show_setup()

    elif pin == BUTTON_UP:
        if __current_page == PAGE_BEER_INFO:
            __prev_digits = None
            __current_page = PAGE_MAIN
            __lcd.clear()
        elif __current_page == PAGE_FERM_SESSION:
            __current_page = PAGE_BEER_INFO
            show_beer_details()
        elif __current_page == PAGE_SETTINGS:
            __current_page = PAGE_FERM_SESSION
            show_ferm_data()
        elif __current_page == PAGE_SETUP:
            print_text("\xfe", 0, __setup_opt + 1)
            __setup_opt -= 1
            if __setup_opt < 0:
                __setup_opt = 2
            print_text("\x7e", 0, __setup_opt + 1)
        elif __current_page == PAGE_SETUP_TEMP:
            __aux_setup += 0.1
            print_text(str(__aux_setup), 13, 1)
        elif __current_page == PAGE_SETUP_DELTA:
            if __aux_setup < 5:
                __aux_setup += 0.1
                print_text(str(__aux_setup), 15, 1)
        elif __current_page == PAGE_SETUP_HEATER:
            __aux_setup = not __aux_setup
            if __aux_setup:
                print_text("SIM", 17, 1)
            else:
                print_text("NAO", 17, 1)

    elif pin == BUTTON_DOWN:
        if __current_page == PAGE_MAIN:
            __current_page = PAGE_BEER_INFO
            show_beer_details()
        elif __current_page == PAGE_BEER_INFO:
            __current_page = PAGE_FERM_SESSION
            show_ferm_data()
        elif __current_page == PAGE_FERM_SESSION:
            __current_page = PAGE_SETTINGS
            show_settings()
        elif __current_page == PAGE_SETUP:
            print_text("\xfe", 0, __setup_opt + 1)
            __setup_opt += 1
            if __setup_opt > 2:
                __setup_opt = 0
            print_text("\x7e", 0, __setup_opt + 1)
        elif __current_page == PAGE_SETUP_TEMP:
            __aux_setup -= 0.1
            print_text(str(__aux_setup), 13, 1)
        elif __current_page == PAGE_SETUP_DELTA:
            if __aux_setup > 0:
                __aux_setup -= 0.1
                print_text(str(__aux_setup), 15, 1)
        elif __current_page == PAGE_SETUP_HEATER:
            __aux_setup = not __aux_setup
            if __aux_setup:
                print_text("SIM", 17, 1)
            else:
                print_text("NAO", 17, 1)
    else:
        print "PIN nao reconhecido"


def show_setup():
    print_text("****** SETUP *******", 0, 0, True)
    print_text("  Temperatura ferm. ", 0, 1)
    print_text("  Delta temp. ferm. ", 0, 2)
    print_text("  Uso de aquecedor  ", 0, 3)
    print_text("\x7e", 0, __setup_opt + 1)


def show_setup_temp_ferm():
    global __aux_setup

    print_text("*** CONFIGURACAO ***", 0, 0, True)
    print_text("Temperatura: " + str(__aux_setup) + "\xdf\x43", 0, 1)
    print_text(" + e - para ajustar ", 0, 2)
    print_text(" Set para confirmar ", 0, 3)


def show_setup_delta_temp():
    global __aux_setup

    print_text("*** CONFIGURACAO ***", 0, 0, True)
    print_text("Delta Max.:    " + str(__aux_setup) + "\xdf\x43", 0, 1)
    print_text(" + e - para ajustar ", 0, 2)
    print_text(" Set para confirmar ", 0, 3)


def show_setup_heater():
    global __aux_setup

    print_text("*** CONFIGURACAO ***", 0, 0, True)
    print_text("Usar Aquecedor?  SIM", 0, 1)
    print_text(" + e - para ajustar ", 0, 2)
    print_text(" Set para confirmar ", 0, 3)

    if __aux_setup:
        print_text("SIM", 17, 1)
    else:
        print_text("NAO", 17, 1)


def save_temp_ferm():
    global __aux_setup
    global __prev_digits
    global __current_page
    global __lcd

    if __aux_setup == params.fermentation_temp:
        __prev_digits = None
        __current_page = PAGE_MAIN
        __lcd.clear()
    else:
        cnfg_file.change_parameter("constant_temperature", __aux_setup)
        if params.use_profile:
            cnfg_file.change_parameter("use_profile", False)
        print_text("********************", lin=0, col=0, clear=True)
        print_text("*   CONFIGURACAO   *", lin=1, col=0)
        print_text("*      SALVA       *", lin=2, col=0)
        print_text("********************", lin=3, col=0)
        time.sleep(1)
        Thread(target=cloud_sender.send_fermentation_settings).start()
        __prev_digits = None
        __current_page = PAGE_MAIN
        __lcd.clear()


def save_temp_delta():
    global __aux_setup
    global __prev_digits
    global __current_page
    global __lcd

    if __aux_setup == params.temp_delta:
        __prev_digits = None
        __current_page = PAGE_MAIN
        __lcd.clear()
    else:
        cnfg_file.change_parameter("temp_delta", __aux_setup)
        print_text("********************", lin=0, col=0, clear=True)
        print_text("*   CONFIGURACAO   *", lin=1, col=0)
        print_text("*      SALVA       *", lin=2, col=0)
        print_text("********************", lin=3, col=0)
        time.sleep(1)
        Thread(target=cloud_sender.send_fermentation_settings).start()
        __prev_digits = None
        __current_page = PAGE_MAIN
        __lcd.clear()


def save_heater():
    global __aux_setup
    global __prev_digits
    global __current_page
    global __lcd

    if __aux_setup == params.heater:
        __prev_digits = None
        __current_page = PAGE_MAIN
        __lcd.clear()
    else:
        cnfg_file.change_parameter("heater", __aux_setup)
        print_text("********************", lin=0, col=0, clear=True)
        print_text("*   CONFIGURACAO   *", lin=1, col=0)
        print_text("*      SALVA       *", lin=2, col=0)
        print_text("********************", lin=3, col=0)
        time.sleep(1)
        Thread(target=cloud_sender.send_fermentation_settings).start()
        __prev_digits = None
        __current_page = PAGE_MAIN
        __lcd.clear()


def show_beer_details():
    print_text("Cerveja:", 0, 0, True)
    print_text(params.beer[:20], 0, 1)
    print_text("Estilo:", 0, 2)
    print_text(params.style[:20], 0, 3)

    print_text("\x5e", 19, 0)
    print_text("\x2b", 19, 3)


def show_ferm_data():
    print_text('Temp. Ferm.: ' + str(params.fermentation_temp) + "\xdf\x43", 0, 0, True)
    print_text("OG: " + str(params.og), 0, 1)
    print_text("Inicio: " + datetime.strftime(params.start_date, "%d %b %Y"), 0, 2)

    if params.use_profile:
        print_text("Perfil Ferm.: SIM", 0, 3)
    else:
        print_text("Perfil Ferm.: NAO", 0, 3)

    print_text("\x5e", 19, 0)
    print_text("\x2b", 19, 3)


def show_settings():
    print_text("Interv. sensor: " + str(params.sensor_read_interval) + '"', 0, 0, True)
    print_text("Delta Temp.: " + str(params.temp_delta) + "\xdf\x43", 0, 1)
    print_text("Delay estado: " + str(params.delay_state) + "'", 0, 2)
    if params.heater:
        print_text("Aquecedor: SIM", 0, 3)
    else:
        print_text("Aquecedor: NAO", 0, 3)

    print_text("\x5e", 19, 0)


def print_digit(index, item):
    print_text(item[0], index, 0)
    print_text(item[1], index, 1)


def display_temp_c(temp_c):
    global __lcd
    global __current_page
    global __prev_digits

    if __current_page != PAGE_MAIN:
        if (datetime.now() - __last_action).total_seconds() > 15:
            __current_page = PAGE_MAIN
            __prev_digits = None
            __lcd.clear()
        else:
            return

    global __dot
    global __neg
    global __space
    global __degree

    temp_text = str(temp_c)
    counter = 0
    index = 0
    for ch in temp_text:
        if ch == '-':
            print_digit(0, __neg)
            index = 1
        elif ch == '.':
            if __prev_digits is None:
                print_digit(index, __dot)
            index += 1
        else:
            if 0 < counter < len(temp_text) and temp_text[counter - 1] != '.':
                print_digit(index, __space)
                index += 1

            if __prev_digits is None or ch != __prev_digits[counter]:
                print_digit(index, __digits[int(ch)])
            index += 3

        counter += 1
    print_digit(index, __degree)
    __prev_digits = temp_text

    print_text('Temp. Ferm.: ' + str(params.fermentation_temp) + "\xdf\x43", 0, 2)
    print_text('Desde: ' + datetime.strftime(params.start_date, "%d %b %Y"), 0, 3)
    print_text("\xfe", 19, 0)
    print_text("\x2b", 19, 3)


def on_connect(client, data, rc):
    client.subscribe([(TEMP_TOPIC, 0)])


def on_message(client, userdata, msg):
    display_temp_c(msg.payload.split("#")[1])


def print_text(text, col, lin, clear=False):
    global __lcd

    lock = Lock()
    with lock:
        if clear is True:
            __lcd.clear()

        __lcd.set_cursor(row=lin, col=col)
        __lcd.message(text)


def start_display():
    global __lcd
    global __digits
    global __segs
    global __current_page

    params.start_params_monitor()

    for i in range(8): __lcd.create_char(i, __segs[i])
    __current_page = PAGE_MAIN
    __lcd.clear()

    gpio_setup()

    client = mqtt.Client(client_id='DISPLAY', protocol=mqtt.MQTTv31)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("127.0.0.1", 1883)
    client.loop_forever()
