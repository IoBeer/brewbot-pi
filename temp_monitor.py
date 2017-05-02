import paho.mqtt.client as mqtt
import os
import glob
import time
from time import strftime
import fermentation_params as params

os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

# Configurations
__base_dir = '/sys/bus/w1/devices/'
__device_folder = glob.glob(__base_dir + '28*')[0]
__device_file = __device_folder + '/w1_slave'
TEMP_TOPIC = "smarthomebrew/sensor/temperatura"


def read_temp_raw():
    f = open(__device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines


def read_temp():
    lines = read_temp_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos + 2:]
        temp_c = float(temp_string) / 1000.0
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        return temp_c, temp_f


def start_monitor():
    params.start_params_monitor()
    # MQTT connection and identifier
    client = mqtt.Client(client_id='shb:thermostat',
                         protocol=mqtt.MQTTv31)
    client.connect("127.0.0.1", 1883)

    while True:
        temp_c = read_temp()[0]
        print('Temperatura lida: %.2f' % temp_c)
        client.publish(TEMP_TOPIC, strftime("%d-%m-%Y %H:%M:%S", time.localtime()) + '#%.2f' % temp_c, qos=0)
        time.sleep(params.sensor_read_interval)
