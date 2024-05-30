#!/usr/bin/env python3

# MIT License
#
# Copyright (c) 2024 Michael Caldwell-Waller (@chipguyhere)
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# This copyright notice and this permission notice are not required to appear in the
# binary (executable/object/compiled) copy of a project.


'''
This connects to Crestron over TCP port 18000 to get realtime signals and events sent by the
diagnostic send symbols I created and are running on the Crestron processor.

This also connects to the MQTT server to post those events for downstream consumption.

The first thing we do on connecting to MQTT is subscribe to all of the retained
messages, so that they will be left intact if they are still correct and consistent
with retained information from Crestron.  We update anything that is either changed,
or that has the immediate/not-retained status coming from the Crestron code.

'''

import socket
import threading
import queue
import paho.mqtt.client as mqtt
import time

# Configuration
MQTT_BROKER = '192.168.555.555'  # MQTT SERVER IP GOES HERE
MQTT_PORT = 1883  # Default MQTT port is 1883
MQTT_TOPIC = 'crestron/#'
MQTT_USERNAME = "MQTT USERNAME GOES HERE"
MQTT_PASSWORD = "MQTT PASSWORD GOES HERE"
CRESTRON_HOST = "192.168.444.444"   # CRESTRON PROCESSOR IP GOES HERE
CRESTRON_TCP_SERVER_PORT = 18000




# Queue for inter-thread communication
message_queue = queue.Queue()

retained_messages = {}
published_topics = {}
last_retained_message_time = 0


mqtt_has_connected=False
mqtt_has_connected_when=0
mqtt_has_disconnected=False
mqtt_connect_has_failed=False
mqtt_topic_prefix = MQTT_TOPIC.replace('#','')
tcp_has_connected=False
tcp_has_connected_when=0
tcp_has_disconnected=False
tcp_connect_has_failed=False

# MQTT Callbacks
def on_connect(client, userdata, flags, rc, properties):
    global last_retained_message_time
    global mqtt_has_connected,mqtt_has_connected_when
    print("Connected to MQTT with result code " + str(rc))
    client.subscribe(MQTT_TOPIC)
    last_retained_message_time = time.monotonic()
    mqtt_has_connected_when = time.monotonic()
    mqtt_has_connected=True
    
def on_connect_fail(client, userdata):
    global mqtt_connect_has_failed
    mqtt_connect_has_failed=True
    

def on_message(client, userdata, msg):
    global retained_messages
    global last_retained_message_time
    print(f"Received mqtt message '{msg.payload.decode()}' on topic '{msg.topic}'")
    if msg.retain:
        retained_messages[msg.topic] = msg.payload.decode()
        last_retained_message_time = time.monotonic()

def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    global mqtt_has_disconnected
    mqtt_has_disconnected=True
    message_queue.put('') # this will break the queue processing's wait
    print("Disconnected with result code " + str(reason_code))

# MQTT Thread
def mqtt_thread():
    try:
        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, reconnect_on_failure=False)
        client.on_connect = on_connect
        client.on_connect_fail = on_connect_fail
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        client.username_pw_set(MQTT_USERNAME,MQTT_PASSWORD)
        client.enable_bridge_mode()
        client.connect(MQTT_BROKER, MQTT_PORT, 60)

        client.loop_start()
    except:
        global mqtt_connect_has_failed
        mqtt_connect_has_failed=True
        print("MQTT connection has failed.")
        return

    t = 0
    while t < 120:
        t=t+1
        if mqtt_connect_has_failed: return
        if mqtt_has_connected: break
        time.sleep(1)


    try:
        while True:
            global retained_messages
            if mqtt_has_disconnected: return
            if tcp_has_disconnected: return
            if tcp_connect_has_failed: return
            condA = len(retained_messages) > 0
            condB = tcp_has_connected and mqtt_has_connected
            condC = not tcp_has_disconnected and not mqtt_has_disconnected 
            condD = time.monotonic() - mqtt_has_connected_when >= 20.0
            condE = time.monotonic() - tcp_has_connected_when >= 20.0
            condF = time.monotonic() - last_retained_message_time >= 5.0
            if condA and condB and condC and condD and condE and condF:
                # Publish any retained messages
                my_retained_messages = retained_messages
                retained_messages = {}
                for k,v in my_retained_messages.items():
                    if not k in published_topics:
                        print(f"Could delete topic {k} having value {v}.")
                print("Nothing more recommended for deletion.")
            while not message_queue.empty():
                message = message_queue.get()
                if isinstance(message, tuple):
                    client.publish(message[0],message[1], retain=True)
            time.sleep(0.1)
    finally:
        client.loop_stop()
            
            
def tcp_listener():
    tcp_listener2()
    global tcp_has_disconnected
    tcp_has_disconnected=True

def tcp_listener2():
    host = CRESTRON_HOST
    port = CRESTRON_TCP_SERVER_PORT

    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(40.0)

    global tcp_has_connected, tcp_has_connected_when
    global tcp_has_disconnected
    global tcp_connect_has_failed

    # Connect the socket to the server
    try:
        sock.connect((host, port))
        print(f"Connected to {host} on port {port}")
    except Exception as e:
        print(f"Failed to connect to {host}: {e}")
        tcp_connect_has_failed=True
        return

    tcp_has_connected=True
    tcp_has_connected_when = time.monotonic()
    buffer = b''
    try:
        while True:
            # Receive data from the socket
            # Note we have set a 20 second timeout, but we expect to
            # disconnect if we reach that.
            data = sock.recv(1024)
            if not data:
                break  # Connection closed

            if mqtt_has_disconnected: break
            if mqtt_connect_has_failed: break

            if len(buffer) != 0: print(f"Buffered: {buffer}")
            print(f"Data: {data}")

            buffer += data
            bufwas = str(buffer)
            while b'\r\n' in buffer:
                # What comes first, \r\n, or two instances of an equal sign?
                # If two equal signs come first, we may have string data
                # which contains a length byte and could literally contain \r\n.
                eq1 = buffer.find(b'=')
                eq2 = buffer.find(b'$=', eq1+1)
                rn = buffer.find(b'\r\n')
                if eq2>eq1 and eq1>0 and eq2<rn:
                    # CONCLUSION:
                    # this is a string value where a numeric length is given.
                    # the string could contain a literal \r\n which is why the length is given.
                    # EXAMPLE:
                    # :topicname=21$=firstline\r\nsecondline\r\n
                    #           ^--eq1        ^--part of the value
                    #              ^--eq2                   ^--terminator, not part of the value
                    #            ^--slen=21
                    #  |--lhs--|     |----rhs--(len 21)----|    |---buffer---...
                    # ^--retained
                    slen = int(buffer[eq1+1:eq2])
                    # for the message to be there, I need to see eq2 + slen + 2 + 2
                    # (2 for \r\n and 2 for $=).  Must break if the only \r\n is part of the string literal
                    # and wait for more data to arrive.
                    if len(buffer) < (eq2+slen+4): break
                    rhs = buffer[eq2+2:eq2+slen+2]
                    lhs = buffer[1:eq1]
                    retained = (buffer[0:1]!=b'!')
                    buffer = buffer[eq2+slen+4:]
                elif eq1>1:
                    # CONCLUSION:
                    # this is a nonstring value where \r\n delineates the end of the value.
                    # EXAMPLE:
                    # :topicname=12345\r\n
                    # ^--retained     ^rn
                    #           ^--eq1
                    #  |--lhs--| |rhs|    |--buffer---...
                    #
                    lhs=buffer[1:eq1]
                    rhs=buffer[eq1+1:rn]
                    retained=(buffer[0:1]!=b'!')
                    buffer=buffer[rn+2:]
                else:
                    # CONCLUSION:
                    # nonconforming input containing \r\n (as tested by while loop condition).
                    # Ignore the line but keep everything following \r\n
                    lhs=None
                    rhs=None
                    buffer=buffer[rn+2:]
                    
                if rhs==b"": rhs=b'""'
                
                lhs = lhs.decode()
                lhs = lhs.replace('#','$')
                    
                
                # determine whether there are non-printable bytes.
                # If there are, we will publish them using Python's string representation
                # of escaped binary strings (which is very similar to Crestron's).
                # Crestron:  \x00\x01ABCDEFG
                # Python:    b'\x00\x01ABCDEFG' where the b means binary, \' escapes a quote, \\ escapes a \
                #              and where " can be used in place of ' as long as it's consistent.
                contains_nonprintables=False
                for b in rhs:
                    if b < 0x20 or b > 0x7e:
                        contains_nonprintables=True
                        break
                
                
                rhs = str(rhs) if contains_nonprintables else rhs.decode()
                lhs = mqtt_topic_prefix + lhs
            
                
                if lhs:
                    global published_topics
                    published_topics[lhs]=1
                    if not retained:
                        # Live message, remove from retained message reconciliation if present.
                        retained_messages.pop(lhs, None)
                        message_queue.put((lhs,rhs))
                    else:
                        global last_retained_message_time
                        last_retained_message_time = time.monotonic()
                        if lhs in retained_messages:
                            if retained_messages[lhs] != rhs:
                                # newer than what we have -- publish it.
                                retained_messages.pop(lhs, None)
                                message_queue.put((lhs,rhs))
                        else:
                            # just put it.
                            message_queue.put((lhs,rhs))
                            
                        
                    print(f"Publishing {'(crestron-retained) ' if retained else ''}{lhs}={rhs}")
                    
    except Exception as e:
        print(f"Error during receiving data: {e}")
    finally:
        sock.close()
        print("Connection closed.")

def main():
    
    # Here is the basic strategy.
    # We are going to connect to both Crestron and MQTT,
    # and subscribe to receive our own retained output (from the past) on MQTT.
    # Our Crestron SIMPL+ drivers will automatically send "retained"
    # values immediately upon connection (and a "retained" flag is included
    # to indicate they are the last known value, not an instantaneous change).
    
    # We will first receive all of the Retained information from both sides.
    # Then we will compare them.
    # Then we will only update MQTT with things that have changed.
    # We will leave things in MQTT alone without update, if they are already correct.
    # Once all Retained information has been synchronized, we will then
    # publish real-time changes as they happen.
    # A real-time change will always be published, even if we're publishing something
    # identical to what's already there.
    #
    # We keep going, until we lose either side of the connection.
    # After connection loss, we disconnect and restart everything.
        
    # The goal is that someone subscribing to things should always
    # see the retained flag False for things that either changed NOW,
    # or where we noticed a change NOW, but we never want to publish
    # an message over top of an identical retained message if it's
    # historical.
    
    
    runs=0    
    while True:
        runs=runs+1
        print(f"==========\r\nRUN NUMBER {runs}\r\n==========")

        # reset all globals
        global message_queue
        global retained_messages 
        global published_topics
        global last_retained_message_time
        global mqtt_has_connected
        global mqtt_has_disconnected
        global mqtt_connect_has_failed
        global tcp_has_connected
        global tcp_has_disconnected
        global tcp_connect_has_failed
        
        message_queue = queue.Queue()
        retained_messages = {}
        published_topics = {}
        last_retained_message_time = 0
        mqtt_has_connected=False
        mqtt_has_disconnected=False
        mqtt_connect_has_failed=False
        tcp_has_connected=False
        tcp_has_disconnected=False
        tcp_connect_has_failed=False

        thread = threading.Thread(target=mqtt_thread)
        thread.daemon = True
        thread.start()
        
        listener_thread = threading.Thread(target=tcp_listener)
        listener_thread.daemon = True
        listener_thread.start()    


        thread.join()
        listener_thread.join()
        
        print("All threads have finished, waiting 30 seconds and then restarting")
        time.sleep(30)

if __name__ == "__main__":
    main()
