import dbus.mainloop.glib;dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
from gi.repository import GObject
import paho.mqtt.client as mqtt
from google.cloud import pubsub
from commons import Commons
import sqlite3 as lite
from network_status import NetworkStatus
import NetworkManager
import json
import requests
from threading import Thread
import ConfigParser

__devices = {}

__d_args = ('sender', 'destination', 'interface', 'member', 'path')
__d_args = dict([(x + '_keyword', 'd_' + x) for x in __d_args])

TEMP_TOPIC = "smarthomebrew/sensor/temperatura"
SERIAL_NUMBER = Commons.getserial()
__network_status = NetworkStatus()
__db_con = None
__db_cur = None
__topic = None


def on_connect(client, data, rc):
    client.subscribe([(TEMP_TOPIC, 0)])


def on_message(client, userdata, msg):
    if __network_status.is_connected():
        publish_temp_cloud(msg.payload)
    else:
        save_temperature(msg.payload, False)


def save_temperature(msg, sent):
    global __db_con
    global __db_cur

    msg_data = msg.split("#")
    __db_cur.execute('INSERT INTO temperatures (timestamp, temp, sent) VALUES(?, ?, ?)',
                     (msg_data[0], msg_data[1], sent))
    __db_con.commit()


def publish_temp_cloud(msg):
    global __topic

    # Data must be a bytestring
    cloud_msg = SERIAL_NUMBER + "#" + msg
    cloud_msg.encode('utf-8')

    message_id = __topic.publish(cloud_msg)
    save_temperature(msg, True)
    print('Message {} published.'.format(message_id))


def device_add_remove(*args, **kwargs):
    global __d_args
    global __devices

    msg = kwargs['d_member']
    if msg == "DeviceAdded":
        # Argument will be the device, which we want to monitor now
        args[0].connect_to_signal('StateChanged', device_state_change, **__d_args)
        return

    if msg == "DeviceRemoved":
        if args[0].object_path in __devices:
            del args[0].object_path


def device_state_change(*args, **kwargs):
    global __devices
    global __network_status

    msg = kwargs['d_member']
    path = kwargs['d_path']
    device = NetworkManager.Device(path)
    newState = NetworkManager.const('device_state', args[0])

    try:
        if device.DeviceType == NetworkManager.NM_DEVICE_TYPE_ETHERNET:
            connectionType = "Ethernet"
        elif device.DeviceType == NetworkManager.NM_DEVICE_TYPE_WIFI:
            connectionType = "Wifi"
    except:
        # D-Bus likely doesn't know about the device any longer,
        # this is typically a removable Wifi stick
        path = kwargs['d_path']
        if path in __devices:
            connectionType = __devices[path]["type"]

    if newState == "activated":
        path = kwargs['d_path']
        __devices[path] = {"type": connectionType,
                           "active": True}
        if connectionType == "Ethernet":
            __network_status.ethernet = True
        if connectionType == "Wifi":
            __network_status.wifi = True
        send_unsent_batch()
    else:
        if connectionType == "Ethernet":
            __network_status.ethernet = False
        if connectionType == "Wifi":
            __network_status.wifi = False


def send_unsent_batch():
    global __db_con
    global __db_cur

    try:
        __db_con.row_factory = lite.Row
        __db_cur = __db_con.cursor()
        rows = __db_cur.execute("SELECT timestamp, temp AS temperature FROM temperatures WHERE sent = 0").fetchall()

        json_history = json.dumps([dict(ix) for ix in rows])

        req = requests.post("<YOUR_FIREBASE_FUNCTIONS_ENDPOINT>/batchTemperatureUpdate",
                            headers={'content-type': 'application/json', 'x-serial': '%s'} % Commons.getserial(),
                            data=json_history)
        if req.status_code == requests.codes.ok:
            __db_cur.execute("UPDATE temperatures SET sent = 1 WHERE sent = 0")
            __db_con.commit()
        else:
            print("Erro ao enviar batch")
    except lite.Error, e:
        print "Error %s:" % e.args[0]


def send_fermentation_settings():
    config = ConfigParser.RawConfigParser()
    try:
        config.read('fermentation.properties')
    except ConfigParser.Error:
        print("Error opening fermentation.properties. Missing?")

    settings_data = json.dumps({Commons.getserial() : dict(config.items('Settings'))})
    req = requests.post("<YOUR_FIREBASE_FUNCTIONS_ENDPOINT>/fermentationData",
                        headers={'content-type': 'application/json'},
                        data=settings_data)
    if req.status_code == requests.codes.ok:
        print "Fermentation settings sent!"
    else:
        print("Error sending fermentation data :(")


def start_sender():
    try:
        global __network_status
        global __db_con
        global __db_cur
        global __topic
        global __devices
        global __network_status

        ################################################################################################################
        # database connection                                                                                          #
        ################################################################################################################
        __db_con = lite.connect('fermentation.db')
        __db_cur = __db_con.cursor()

        ################################################################################################################
        # Network d-bus communitcation                                                                                 #
        ################################################################################################################
        NetworkManager.NetworkManager.connect_to_signal('DeviceAdded', device_add_remove, **__d_args)
        NetworkManager.NetworkManager.connect_to_signal('DeviceRemoved', device_add_remove, **__d_args)

        for dev in NetworkManager.NetworkManager.GetDevices():
            print("DEVICE!!")
            dev.connect_to_signal('StateChanged', device_state_change, **__d_args)
            __devices[dev.object_path] = {}
            if dev.DeviceType == NetworkManager.NM_DEVICE_TYPE_ETHERNET and \
                            NetworkManager.const('device_state', dev.State) == "activated":
                __devices[dev.object_path]["active"] = True
                __devices[dev.object_path]["type"] = "Ethernet"
                __network_status.ethernet = True
            if dev.DeviceType == NetworkManager.NM_DEVICE_TYPE_WIFI and \
                            NetworkManager.const('device_state', dev.State) == "activated":
                __devices[dev.object_path]["active"] = True
                __devices[dev.object_path]["type"] = "Wifi"
                __network_status.wifi = True

        print "Starting network manager thread"
        thread = Thread(target = start_network_manager_loop)
        thread.start()

        ################################################################################################################
        # Send fermentation settings                                                                                   #
        ################################################################################################################
        settings_thread = Thread(target=send_fermentation_settings)
        settings_thread.start()

        ################################################################################################################
        # PubSub Cloud topic setup                                                                                     #
        ################################################################################################################
        print "Starting cloud connection"
        pubsub_client = pubsub.Client()
        __topic = pubsub_client.topic('temperature')

        ################################################################################################################
        # Local MQTT server                                                                                            #
        ################################################################################################################
        print "Starting local MQTT connection"
        client = mqtt.Client(client_id='PUBSUB',
                             protocol=mqtt.MQTTv31)

        client.on_connect = on_connect
        client.on_message = on_message

        client.connect("127.0.0.1", 1883)
        client.loop_forever()

    except KeyboardInterrupt:
        print("Pressed CTRL+C! :(")
    finally:
        if __db_con:
            __db_con.close()


def start_network_manager_loop():
    print "Starting network manager loop"
    loop = GObject.MainLoop()
    loop.run()