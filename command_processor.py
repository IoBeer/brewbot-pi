import json
import numpy
import ConfigParser
from threading import Thread
import cloud_sender

__config = ConfigParser.RawConfigParser()


def parse_cmd_json(cmd_json):
    if cmd_json["commands"]:
        settings_updated = False
        for i in range(numpy.matrix(cmd_json["commands"]).size):
            if cmd_json["commands"][i]["cmd"] == "set":
                if change_parameter(cmd_json['commands'][i]['param'], cmd_json['commands'][i]['value']):
                    settings_updated = True

        if settings_updated:
            print "Starting thread to update settings data"
            Thread(target=cloud_sender.send_fermentation_settings).start()


def change_parameter(parameter, value):
    global __config
    try:
        __config.read('fermentation.properties')
    except ConfigParser.Error:
        print "Error reading fermentation.properties"
        return False

    if __config.has_option('Settings', parameter):
        print "Parameter FOUND!! \o/"
        __config.set('Settings', parameter, value)
        try:
            config_file = open('fermentation.properties', 'w')
            __config.write(config_file)
            config_file.close()
        except ConfigParser.Error:
            print("Error writing parameters" )
            return False

        return True
    else:
        print "Parameter %s not found" % parameter
        return False


def process_command(command):
    print "Commands received: " + command
    cmd_json = json.loads(command)
    parse_cmd_json(cmd_json)
