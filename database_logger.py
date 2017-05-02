import sqlite3 as lite
import paho.mqtt.client as mqtt


def on_connect(client, data, rc):
    client.subscribe([(temperatureTopic, 0)])


def on_message(client, userdata, msg):
    msg_data = msg.payload.split("#")
    cur.execute("INSERT INTO temperatures (timestamp, temp, sent) VALUES(?, ?, ?)", (msg_data[0], msg_data[1], False))
    con.commit()


try:
    con = lite.connect('fermentation.db')
    cur = con.cursor()

    temperatureTopic = "smarthomebrew/sensor/temperatura"

    client = mqtt.Client(client_id='DATABASE',
                         protocol=mqtt.MQTTv31)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("127.0.0.1", 1883)
    client.loop_forever()

except KeyboardInterrupt:
    print("Pressed CTRL+C! :(")
finally:
    if con:
        con.close()
