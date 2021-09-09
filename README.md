# iPing360Device

## Overview
iPing360Device is a python MOOSApp that:
* Interfaces with the Ping360 sonar using the brping python module
* Provides a MOOS interface for controlling the sonar
* Publishes the ping data and status information to the MOOS DB
* Logs the ping data to a binary file; the data can be replayed with the BlueRobotics PingViewer software

## Configuration Parameters
The iPing360Device app is configured using the Ping360.ini configuration file, which must be in the same directory as the iPing360Device.py file. The Ping360.ini file parameters are as follows. 

Parameter     | Description
------------  | -------------
port_type     | (required) The port type to connect to, must be one of ‘udp’ or ‘serial’
serial_port   | (optional, default: /dev/ttyS0) The serial port to connect to, if the PORT_TYPE is set to ‘serial’
baudrate      | (optional, default: 115200) Serial communications baud rate, must be one of 2400, 4800, 9600, 19200, 38400, 57600, or 115200.
sonar_ip      | (optional, default: 192.168.0.100) IP address of the sonar for connecting via a UDP link
udp_port      | (optional, default: 12345) Port number for connecting via a UDP link
prefix        | (optional, default = ‘’) Message names subscribed for published by iPing360Device will be prefixed by this string. If not included, an underscore will inserted as the last prefix character. If a blank value is provided, no prefix or underscore will precede variable name in the publication.
log_file_dir  | (optional, default = ‘./’ ) Directory for saving log files

## Example Configuration Block
An example Ping360.ini file configuration block is provided below. 

```
[parameters]
port_type  = udp
sonar_ip = 192.168.1.123
udp_port = 5000
prefix = sonar_
log_file_dir = ./
```

## Variables Subscribed for by iPing360Device
The iPing360Device application subscribes to the MOOS messages listed in the table below, and responds to run-time changes. The Ping360.ini file parameter prefix defines the [prefix] text in the MOOS messages. For example, if prefix=PING360, the app subscribes for the PING360_TRANSMIT_ENABLE variable. 

Input Variable                  | Type     | Range            | Description
------------------------------  | -------- | -----------------| -----------
[PREFIX_]DEVICE_COMMS_ENABLE    | Integer  | 0-1              | Upon enable, initializes communication with the sonar & configures it. The default is 0. 
[PREFIX_]TRANSMIT_ENABLE        | Integer  | 0-1              | Enables pinging when set to 1. The default is 0. 
[PREFIX_]START_ANGLE_GRADS      | Integer  | 0 to 400 gradians| Scan sector start angle (inclusive). The scan sector is defined by a clockwise rotation from the start angle to the stop angle. The default is 350 gradians (i.e. 315 degrees)
[PREFIX_]STOP_ANGLE_GRADS       | Integer  | 0 to 400 gradians|Scan sector stop angle (inclusive).  The scan sector is defined by a clockwise rotation from the start angle to the stop angle. The default is 50 gradians (i.e 45 degrees)
[PREFIX_]NUM_STEPS              | Integer  | 1 to 10 gradians | Number of 0.9 degree motor steps between pings for auto scan (1 to 10 gradians is 0.9 to 9.0 degrees). The default is 1.
[PREFIX_]GAIN                   | Integer  | 0: low, 1: normal, 2: high  | Analog gain setting.The default is ‘normal’
[PREFIX_]RANGE                  | Float    | 0m to 50m        |Distance from the sonar to scan signals. Smaller ranges will scan faster as the receiver does not have to wait as long to receive a response.  The default is 15m. 
[PREFIX_]SPEED_OF_SOUND         | Float    | 1450m/s to 1550 m/s | The speed of sound to be used for distance calculations. This should be 1500 m/s in salt water, 1450 m/s in fresh water. The default is 1500m/s.
[PREFIX_]TRANSMIT_FREQUENCY     | Integer  | 500kHz to 1000kHz | Acoustic operating frequency. Although the frequency range is 500kHz to 1000kHz, however it is only practical to use say 650kHz to 850kHz due to the narrow bandwidth of the acoustic receiver. The default is 750kHz
[PREFIX_]NUMBER_OF_SAMPLES      | Integer  | 1 - 1200         | Number of samples per reflected signal. The default is 600
[PREFIX_]LOG_ENABLE             | Integer  | 0-1              | When set to 1, creates a new log file in LOG_FILE_DIR and logs ping data to it. The file can be replayed with PingViewer. The file name format is ping360_YYYMMDD_HHMMSS.bin 
[PREFIX_]DEBUG_ENABLE           | Integer  |  0-1             | Enables printing of verbose debug information, such as the complete ping data message

## Variables Published by iPing360Device
The table below lists the output variables which the app publishes to the MOOSDB.

Output Variable                 | Type     | Description
------------------------------  | -------- | ------------
[PREFIX_]PING_DATA              | Binary   | ‘2301 auto_device_data’ message containing the most recent ping intensity data. 
[PREFIX_]STATE                  | String   | Indicates the state of the app: DB Disconnected, DB Connected, Ready to Transmit or Transmitting
[PREFIX_]LAST_ERROR             | String   | Indicates the most recent error that occured
[PREFIX_]LOG_STATUS             | String   | Indicates logging status. For example: Disabled, Logging, Error (failed to open file)
[PREFIX_]TRANSMIT_ANGLE_GRADS   | Float    | The current transmit angle, in gradians
[PREFIX_]TRANSMIT_ANGLE_DEGS    | Float    | The current  transmit angle, in degrees

## Required software/packages: 

  * [Moos-Ivp](https://oceanai.mit.edu/ivpman/pmwiki/pmwiki.php?n=Lab.ClassSetup#sec_course_software)
  * Python-moos module. Install with:
  ```
  python3 -m pip install --upgrade pip setuptools wheel
  python3 -m pip install pymoos 
```
  * Bluerobotics brping module. Install with: 
```
  python3 -m pip install bluerobotics-ping
```
  * Alternatively, install the brping module from source:
```
  git clone --single-branch --branch deployment https://github.com/bluerobotics/ping-python.git
  cd ping-python/
  python3 setup.py install --user
```







