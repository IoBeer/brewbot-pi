import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import fermentation_params as params

RELAY_COOL = 23
RELAY_HEAT = 24
TEMP_TOPIC = "smarthomebrew/sensor/temperatura"


def gpio_setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAY_COOL, GPIO.OUT)
    GPIO.setup(RELAY_HEAT, GPIO.OUT)
    GPIO.setwarnings(False)
    GPIO.output(RELAY_COOL, GPIO.HIGH)
    GPIO.output(RELAY_HEAT, GPIO.HIGH)


def on_connect(client, data, rc):
    client.subscribe([(TEMP_TOPIC, 0)])


def on_message(client, userdata, msg):
    temp_c = float(msg.payload.split("#")[1])
    if temp_c >= (params.fermentation_temp + params.temp_delta):
        # ligar geladeira
        GPIO.output(RELAY_COOL, GPIO.LOW)
        GPIO.output(RELAY_HEAT, GPIO.HIGH)
    elif temp_c <= (params.fermentation_temp - params.temp_delta):
        # desligar geladeira
        GPIO.output(RELAY_COOL, GPIO.HIGH)
        GPIO.output(RELAY_HEAT, GPIO.LOW)


def start_controller():
    params.schedule_profile = True
    params.start_params_monitor()
    try:
        gpio_setup()
        client = mqtt.Client(client_id='RELAYS',
                             protocol=mqtt.MQTTv31)

        client.on_connect = on_connect
        client.on_message = on_message

        client.connect("127.0.0.1", 1883)
        client.loop_forever()
    except KeyboardInterrupt:
        print("Pressed CTRL+C! :(")
    finally:
        GPIO.cleanup()  # this ensures a clean exit
        # print config.get('DatabaseSection', 'database.dbname');
