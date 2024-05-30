# SimplDiagnosticSend

These three custom SIMPL+ blocks can be used to create a TCP Server service on a Crestron processor that allows
the sending of an unlimited number of diagnostic signals from within a SIMPL program.

One block is for sending Digital signals, one is for sending Analog signals, and one is for sending Strings.
You can expand the blocks to allow up to 100 signals.  Each signal is also sent with a text string identifying
the signal, which you must include in the block (and which ideally could just be the same name as the signal
you're sending from the SIMPL program).

Additionally, upon connection, the client will be given the current status of all the signals within
the first minute of being connected, to allow for a paradigm of "synchronization".  Each message includes a
"retained" flag to distinguish between a pre-existing value, versus an immediate change or update to the value.

# Usage

* In your SIMPL program, configure a TCP/IP Server symbol with a unique IP-ID.  Select a port number (e.g. 18000)
* Provide a constant 1 or other logic to _enable_ it
* Plan to connect the _Connect-F_ feedback output into the _Enable_ input
  of each of the Diagnostic Send symbols (from this module) you'll create.  _Enable_ drives the initial refresh behavior,
  and prevents sending data to the TCP/IP Server if no connection is active.
* Add one or more Diagnostic Send symbols to your project, and choose some signals to report.  Use Alt-+ to expand
  the symbol to add additional lines as necessary.
* Make sure each symbol has a text parameter that provides the name of the symbol as you would like it to be seen
  in the output.  If your output will be going to an MQTT server, consider that MQTT allows for optional path hierarchy (with
  forward slashes), and also forbids # and + symbols (since these are considered wildcards for selection/search).
* Connect the Enable input.  Connect the Output to the TX$ input of the TCP/IP Server.
* It is okay to have an unlimited number of Diagnostic Sends sending their output to the same TX$ input of the
  TCP/IP server.
  
# Data format

When an incoming TCP connection is opened, these modules will send the value of the symbols, as plain text,
terminated with CR+LF, as follows:

## Digital Signals

```
:SignalNameHere=0
:SignalNameHere=1
!SignalNameHere=0
!SignalNameHere=1
```

The first character will be a ```!``` if the signal is being reported due to an immediate update or change,
or ```:``` if it is being reported upon connection.  Because the reporting is paced over the first seconds
of the connection to avoid overwhelming system resources,
it is possible that you may only get the ```!``` version, if the value is updated or changes
very shortly upon first connect.  You will never receive a ```:``` message after receiving a ```!``` message
for the same signal, unless you disconnect and reconnect.

## Analog Signals

```
:SignalNameHere=12345
!SignalNameHere=23456
````

Same idea, except that you receive the analog value, instead of 0 and 1.

## String Values

Strings are sent with an extra field to signify the length of the string.  There is no escaping of non-printable
bytes -- all raw bytes (which could include any value between \x00 and \xff, inclusive
of CR and LF) are sent over the TCP/IP connection without any modification.  The length is used
to communicate how many bytes will belong to the value.

```
:SignalNameHere=2$=AA
:SignalNameHere=5$=AAAAA
:SignalNameHere=00$=
!SignalNameHere=0$=
!SignalNameHere=12$=Hello
World
!SignalNameHere=11$=Hello World
```

The dollar sign signifies this will be a string, and that the digits prior to the dollar sign are the length.

* The : and ! prefix means the same thing as in the Analog/Digital signals.
* The example containing "Hello<CR><LF>World" is 12 bytes: five for Hello, five for World, and two for the CR and LF.
  The client application is expected to understand from the length of 12, that the new line (CR+LF) is part of the value
  and isn't the start of a new message.
* The length of 00 is meant to convey a sometimes useful piece of metadata: that the string has not been set since
  program startup, and that its value of being blank is by default rather than by having been updated.


