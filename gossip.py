#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
import requests
import threading
import time

import RPi.GPIO as GPIO
import alsaaudio
import wave

import neopixel
import gaugette.rotary_encoder

#from pprint import pprint

# Constants

RATE = 44100

BUFFER_SIZE = 60;  # in seconds

BUTTON_PIN = 21

ROTARY_A_PIN = 27
ROTARY_B_PIN = 23

# Neopixel LED strip configuration:
LED_COUNT      = 24      # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (must support PWM!).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 5       # DMA channel to use for generating signal (try 5)
LED_BRIGHTNESS = 255     # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift

strip = neopixel.Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS)

# Setup

buffer = []

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
#GPIO.setup(LED_CHANNEL, GPIO.OUT)

time_marker_start = 0
time_marker_size = 6

encoder = None

button_press_start = 0

def main():
    global time_marker_start
    print("* recording")

    GPIO.add_event_detect(BUTTON_PIN, GPIO.BOTH, callback=button_event)

    encoder = gaugette.rotary_encoder.RotaryEncoder.Worker(ROTARY_A_PIN, ROTARY_B_PIN)
    encoder.start()

    inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE)

    inp.setchannels(1)
    inp.setrate(RATE)
    inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    inp.setperiodsize(160)

    strip.begin()
    # Startup animation
    threading.Thread(target=theaterChase, args=(neopixel.Color(0, 255, 239),)).start()

    start = time.time()
    while True:
        if (len(buffer) > int(RATE / 920 * BUFFER_SIZE)):
            # print time.time() - start
            buffer.pop(0);

        l, data = inp.read()

        if l:
            buffer.append(data)

        delta = encoder.get_delta()
        if delta != 0 and GPIO.input(BUTTON_PIN):
            if time_marker_start + time_marker_size + delta > LED_COUNT:
                time_marker_start = LED_COUNT - time_marker_size
            elif time_marker_start + delta < 0:
                time_marker_start = 0
            else:
                time_marker_start += delta
            updateStrip()

    stream.stop_stream()
    stream.close()

last_button_press = 0
last_button_release = 0
def button_event(pin):
    global last_button_press, last_button_release

    if GPIO.input(pin):
        if time.clock() - last_button_release < 0.1:
            return

        last_button_release = time.clock()
        button_released()
    else:
        if time.clock() - last_button_press < 0.05:
            return

        last_button_press = time.clock()
        button_pressed()

def button_pressed():
    print("* button pressed")
    grow_marker_until_button_released()

def grow_marker_until_button_released():
    global time_marker_size

    if not GPIO.input(BUTTON_PIN):
        if time_marker_start + time_marker_size + 1 <= LED_COUNT:
            time_marker_size += 1
            threading.Timer(0.1, grow_marker_until_button_released).start()

    updateStrip()

def button_released():
    global time_marker_start, time_marker_size

    button_press_start = time.time()
    print("* saving buffer")

    snapshot = b''.join(buffer)

    time_marker_start = 1
    time_marker_size = 6

    threading.Thread(target=mail_snapshot, args=(snapshot,)).start()
    #threading.Timer(0.1, theatreChase).start()
    threading.Thread(target=theaterChase, args=(neopixel.Color(0, 255, 239),), kwargs={'iterations': 5}).start()

def mail_snapshot(snapshot):

    virtual_file = io.BytesIO('snippet')
    wf = wave.open(virtual_file, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(RATE)
    wf.writeframes(snapshot)
    wf.close()

#    virtual_file.seek(0)
#    requests.post(
#            MAILGUN_ENDPOINT + '/messages',
#            auth=("api", MAILGUN_API_KEY),
#            files=[("attachment", ("gossip.wav", virtual_file))],
#            data={"from": "Gossip <david@davidchouinard.com>",
#                "to": "chouichoui@me.com",
#                "subject": "🎤 Gossip saved!",
#                "text": email_content(transcription) })

    requests.get('http://apns-demo.herokuapp.com/')

    # save to disk just to be sure
    virtual_file.seek(0)
    with open('/home/pi/gossip/snippets/' + str(int(time.time())) + '.wav','wb') as f:
        f.write(virtual_file.read())

    print("* buffer sent")

def email_content(transcription):
    if transcription['Status'] == 'OK':
        text =  "\t" + transcription['NBest'][0]['ResultText']
        text += " ({:.0%})".format(transcription['NBest'][0]['Confidence'])
    else:
        return ""

def updateStrip():
    #print str(time_marker_start) + "-" + str(time_marker_size)
    for n in range(0, strip.numPixels()):
        if n >= time_marker_start and n < time_marker_start + time_marker_size:
		    strip.setPixelColor(n, neopixel.Color(0, 255, 239))
        else:
		    strip.setPixelColor(n, 0)

    strip.show()

def theaterChase(color, wait_ms=50, iterations=20):
	"""Movie theater light style chaser animation."""
	for j in range(iterations):
		for q in range(3):
			for i in range(0, strip.numPixels(), 3):
				strip.setPixelColor(i+q, color)
			strip.show()
			time.sleep(wait_ms/1000.0)
			for i in range(0, strip.numPixels(), 3):
				strip.setPixelColor(i+q, 0)

	eraseStrip()

def fadeoutStrip(iterations=50):
    colors = [strip.getPixelColor(n) for n in range(strip.numPixels())]
    start = [[(color >> 16) & 0xff, (color >> 8) & 0xff, color & 0xff] for color in colors]
    for i in range(1, iterations + 1):
        for n in range(strip.numPixels()):
            # quadratic ease out
            rgb = [int(color - color * pow(i/float(iterations), 2)) for color in start[n]]

            strip.setPixelColor(n, neopixel.Color(rgb[0],rgb[1],rgb[2]))
        strip.show()
        time.sleep(0.01)

    # make sure pixels are truly at 0
    eraseStrip()

def eraseStrip():
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, 0)
    strip.show()

if __name__ == "__main__":
    main()