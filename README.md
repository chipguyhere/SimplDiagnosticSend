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
* Name a new digital signal on the _Connect-F_ feedback output.  This needs to be fed into the _Enable_ input
  of each of the diagnostic symbols defined in this module.  Enable drives the initial refresh behavior,
  and prevents sending data to the TCP/IP Server if no connection is active.
* Add one or more Diagnostic Send symbols to your project, and choose some signals to report.  Use Alt-+ to expand
  the symbol to add additional lines as necessary.
* Make sure each symbol has a text parameter that provides the name of the symbol as you would like it to be seen
  in the output.  If your output will be going to MQTT, keep in mind that MQTT allows for optional path hierarchy (with
  forward slashes), and also forbids # and + symbols (since these are considered wildcards for selection/search).
* Connect the Enable input.  Connect the Output to the TX$ input of the TCP/IP Server.
* It is okay to have an unlimited number of Diagnostic Sends sending their output to the same TX$ input of the
  TCP/IP server.
  
