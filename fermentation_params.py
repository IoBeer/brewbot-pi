import json
import ConfigParser
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from datetime import datetime
from datetime import timedelta
import numpy
import threading
import ast


beer = None
style = None
start_date = None
og = None
use_profile = None
constant_temperature = None
temp_delta = None
delay_state = None
sensor_read_interval = None
heater = None
fermentation_temp = None
schedule_profile = False


def on_any_event(event):
    print "File changed! %s " % event.event_type
    load_values_from_file()


def load_values_from_file():
    global beer
    global style
    global start_date
    global og
    global use_profile
    global constant_temperature
    global temp_delta
    global delay_state
    global sensor_read_interval
    global heater
    global fermentation_temp
    global schedule_profile

    print "Loading fermentation properties"
    config = ConfigParser.RawConfigParser()
    try:
        config.read('fermentation.properties')
    except ConfigParser.Error:
        # Error reading properties file. Using 19oC as default temperature
        # TODO: Improve this implementation
        print("Error opening fermentation.properties. Missing?")
        fermentation_temp = 19.00

    try:
        beer = config.get('Settings', 'beer')
        style = config.get('Settings', 'style')
        start_date = datetime.strptime(config.get("Settings", "start_date"), "%d-%m-%Y %H:%M:%S")
        og = float(config.get('Settings', 'og'))
        use_profile = ast.literal_eval(config.get("Settings", "use_profile"))
        constant_temperature = float(config.get("Settings", "constant_temperature"))
        temp_delta = float(config.get('Settings', 'temp_delta'))
        delay_state = float(config.get('Settings', 'delay_state'))
        sensor_read_interval = int(config.get("Settings", "sensor_read_interval"))
        heater = ast.literal_eval(config.get('Settings', 'heater'))
    except ConfigParser.Error:
        # Error reading parameters
        # TODO: Improve this implementation
        print("Error reading parameters")

    if use_profile:
        print "Using profile"
        data = None
        try:
            with open('current.profile') as data_file:
                data = json.load(data_file)
        except OSError:
            # TODO: Add a log message
            print("Error reading current.profile. Setting a constant temperature: %.2f"
                  % constant_temperature)
            fermentation_temp = constant_temperature

        sum_days = 0
        for i in range(numpy.matrix(data["profile"]["temperatures"]).size):
            sum_days += data['profile']['temperatures'][i]['days']
            if start_date + timedelta(days=sum_days) >= datetime.now():
                print("Dias: %i -- Temp.: %.2f" % (data['profile']['temperatures'][i]['days'],
                                                   data['profile']['temperatures'][i]['temperature']))
                print('Termino etapa: ' + datetime.strftime((start_date + timedelta(days=sum_days)),
                                                            "%d-%m-%Y %H:%M:%S"))
                fermentation_temp = data["profile"]["temperatures"][i]["temperature"]
                if schedule_profile:
                    if i < numpy.matrix(data["profile"]["temperatures"]).size - 1:
                        # Scheduling fermentation params reload
                        delay = (
                            (start_date + timedelta(days=sum_days, seconds=1)) - datetime.now()).total_seconds()
                        print("Scheduling update - delay: %i" % delay)
                        threading.Timer(delay, reload_beer_profile).start()
                break
            elif (i + 1) == numpy.matrix(data["profile"]["temperatures"]).size:
                # TODO: Send an alarm / notification indicate the end of profile timeline
                fermentation_temp = data["profile"]["temperatures"][i]["temperature"]
    else:
        print "Using constant temperature"
        fermentation_temp = constant_temperature


def reload_beer_profile():
    load_values_from_file()


def start_params_monitor():
    load_values_from_file()
    event_handler = PatternMatchingEventHandler(patterns=["*.properties", "*.profile"],
                                                ignore_patterns=[],
                                                ignore_directories=True)
    event_handler.on_any_event = on_any_event
    observer = Observer()
    observer.schedule(event_handler, '.', recursive=False)
    observer.start()
