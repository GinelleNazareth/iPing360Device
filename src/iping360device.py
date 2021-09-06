import pymoos
import time
import configparser
import sys
import math
from datetime import datetime
from enum import Enum
from brping import Ping360
from brping import PingMessage
from brping import definitions
from ping360logger import Ping360Logger

# TODO: Replace 'name' with 'key'
# TODO: split between two files
# TODO: Write function descriptions
# TODO: Debug message handling - function to print with timestamp based on priority

# Default parameter values
g_port_type    = ''
g_sonar_ip     = "192.168.0.100"
g_udp_port     = 12345
g_serial_port  = '/dev/ttyS0'
g_baudrate     = 115200
g_prefix       = ''
g_log_file_dir = './'
g_scan_sector_changed = False

class State(Enum):
    DB_DISCONNECTED = 0
    DB_CONNECTED = 1
    READY_TO_TRANSMIT = 2
    TRANSMITTING = 3

# Global variables
g_comms = pymoos.comms()
g_sonar_setting_changed = False
g_ping_360 = Ping360()
g_transmit_angle_grads = 0
g_clockwise = True
g_transmit_duration_usec = 0
g_firmware_min_transmit_duration = 5
g_firmware_max_transmit_duration = 500
g_sample_period_ticks = 0 # The number of timer ticks between each data point
g_sample_period_tick_duration = 25e-9  # Each timer tick has a duration of 25 nanoseconds

g_ping360_device_data=PingMessage()
g_ping360_logger = Ping360Logger()

# Input (subscription) variables. The prefix is added to the variable name (var)
# at runtime when the app is configured. Variable value changes from the database
# are only accepted if the value is within the min & max range.
inputs = {
    'DEBUG_ENABLE' : {
        'var': 'DEBUG_ENABLE',
        'val': 0,
        'min': 0,
        'max': 1
    },

    'LOG_ENABLE' : {
        'var': 'LOG_ENABLE',
        'val': 0,
        'min': 0,
        'max': 1
    },

    'DEVICE_COMMS_ENABLE' : {
        'var': 'DEVICE_COMMS_ENABLE',
        'val': 0,
        'min': 0,
        'max': 1
    },

    # Note: Start angle is input from DB in degrees, and stored in gradians
    'START_ANGLE_GRADS' : {
        'var': 'START_ANGLE_GRADS',
        'val': 350,
        'min': 0,
        'max': 400
    },

    # Note: Stop angle is input from DB in degrees, and stored in gradians
    'STOP_ANGLE_GRADS' : {
        'var': 'STOP_ANGLE_GRADS',
        'val': 50,
        'min': 0,
        'max': 400
    },

    'NUM_STEPS' : {
        'var': 'NUM_STEPS',
        'val': 1,
        'min': 1,
        'max': 10
    },

    'GAIN' : { # 0: low, 1: normal, 2: high
        'var': 'GAIN',
        'val': 1,
        'min': 0,
        'max': 2
    },

    'RANGE' : {
        'var': 'RANGE',
        'val': 15.0,
        'min': 0.0,
        'max': 50.0
    },

    'SPEED_OF_SOUND' : {
        'var': 'SPEED_OF_SOUND',
        'val': 1500.0,
        'min': 1450,
        'max': 1550
    },

    'TRANSMIT_FREQUENCY' : {
        'var': 'TRANSMIT_FREQUENCY',
        'val': 750,
        'min': 500,
        'max': 1000
    },

    'NUMBER_OF_SAMPLES' : {
        'var': 'NUMBER_OF_SAMPLES',
        'val': 600,
        'min': 0,
        'max': 600
    },

    'TRANSMIT_ENABLE' : {
        'var': 'TRANSMIT_ENABLE',
        'val': 0,
        'min': 0,
        'max': 1
    },

}

# Output variables & default values
outputs = {
    'PING_DATA' : bytes(bytearray()) ,
    'STATE' : State.DB_DISCONNECTED.name,
    'LAST_ERROR' : 'None',
    'LOG_STATUS' : g_ping360_logger.status,
    'TRANSMIT_ANGLE_GRADS': g_transmit_angle_grads,
    'TRANSMIT_ANGLE_DEGS': g_transmit_angle_grads*360/400

}

def configure_app():
    ''' Reads in parameters from the Ping360.ini file to configure the app '''

    global g_port_type, g_sonar_ip, g_udp_port, g_serial_port, g_baudrate
    global g_prefix, g_log_file_dir
    error = ''

    # Parse Ping360.ini file
    config = configparser.ConfigParser()
    config.read('Ping360.ini')
    params = config['parameters']  # TODO: handle case of no 'parameters' header?

    # Read in required parameter: port_type
    try:
        g_port_type = params['port_type']
    except KeyError as e:
        raise Exception("{0} is required but was not found".format(e))

    # Read in optional parameters, use defaults if not found
    g_sonar_ip = params.get('sonar_ip', g_sonar_ip)
    g_udp_port = params.getint('udp_port', g_udp_port)
    g_serial_port = params.get('serial_port', g_serial_port)
    g_baudrate = params.getint('baudrate', g_baudrate)
    g_prefix = params.get('prefix', g_prefix)
    g_log_file_dir = params.get('log_file_dir', g_log_file_dir)

    # Check validity of port_type
    if g_port_type not in ['serial', 'udp']:
        raise Exception("Invalid port_type ({0})".format(g_port_type))

    # Check validity of baudrate
    if g_baudrate not in [2400, 4800, 9600, 19200, 38400, 57600, 115200]:
        raise Exception("Invalid baudrate ({0})".format(g_baudrate))

    # Ensure that prefix has '_' at the end if it is not empty
    if g_prefix and not g_prefix.endswith('_'):
        g_prefix += '_'
    g_prefix = g_prefix.upper()

    # Print configuration
    print('port_type is', g_port_type)
    if g_port_type == 'udp':
        print('sonar_ip is', g_sonar_ip)
        print('udp_port is', g_udp_port)
    elif g_port_type == 'serial':
        print('serial_port is', g_serial_port)
        print('baudrate is ', g_baudrate)
    print("prefix is '{0}'".format(g_prefix))
    print('log_file_dir is', g_log_file_dir)

    print(inputs)

def on_connect():
    ''' Updates state to 'DB_CONNECTED', registers subscription vars with the
    MOOS DB & publishes all outputs'''
    global g_prefix, g_comms

    set_output('STATE', State.DB_CONNECTED.name)

    # Register all inputs with the DB
    registered_vars = 0
    for input_id, input in inputs.items():
        msg_name = g_prefix + input_id
        if (g_comms.register(msg_name,0)):
            registered_vars += 1
        else:
            set_output('LAST_ERROR', 'Error registering {0}'.format(msg_name))

    # Publish all outputs - all values except for 'state will be the default'
    for output_id, value in outputs.items():
        set_output(output_id, value)

    return True

def set_output(output_id, value):
    ''' Store & publish output'''
    global g_prefix, g_comms

    # TODO: Print info if debug is enabled
    outputs[output_id] = value
    msg_name = g_prefix + output_id

    if output_id == 'PING_DATA':
        g_comms.notify_binary(msg_name, value, pymoos.time())
    else:
        g_comms.notify(msg_name, value, pymoos.time())

def on_new_mail():
    global g_comms, g_prefix

    # Get new messages
    msg_list = g_comms.fetch()

    for msg in msg_list:
        #Remove prefix from message name for use with inputs dict
        msg_name = msg.name()
        empty, input_id = msg_name.split(g_prefix)

        # Call processing function for input
        on_input_changed(input_id, msg)

    return True

def get_msg_time_str( msg ):
    timestamp = msg.time()
    date_time = datetime.fromtimestamp(timestamp)
    return date_time.strftime('%c')

def on_input_changed ( input_id, msg ):
    global g_ping360_logger, g_scan_sector_changed

    value = msg.double() # TODO: how to handle ints
    input = inputs[input_id] #TODO: handle case where input not found?

    #Do not accept the value if it is out of range
    # TODO: Update DB with current value if invalid value is specified?
    # TODO: If updating DB from here, will also have to initialize as required in on_new_mail?
    if value < input['min'] or value > input['max']:
        # TODO: use debug message function when created + use message name?
        print ("{0} value ({1}) out of range".format(input_id, value))
        return

    # Save valid values
    inputs[input_id]['val'] = value

    # TODO: use debug message function when created + use message name?
    print("{0}: {1} changed to {2}".\
    format(get_msg_time_str(msg), input_id, value))

    if input_id in ['NUMBER_OF_SAMPLES', 'RANGE', 'SPEED_OF_SOUND']:
        calculate_sample_period_and_transmit_duration()

    if input_id in ['START_ANGLE_GRADS', 'STOP_ANGLE_GRADS']:
        g_scan_sector_changed = True

    if input_id == 'LOG_ENABLE':
        if value:
            g_ping360_logger.create_new_file(g_log_file_dir)
        else:
            g_ping360_logger.close_log_file()
        set_output('LOG_STATUS', g_ping360_logger.status)

    return

def connect_to_sonar():
    global g_port_type, g_serial_port, g_baudrate, g_sonar_ip, g_udp_port, g_ping_360

    if g_port_type == 'serial':
        g_ping_360.connect_serial(g_serial_port, g_baudrate)
    elif g_port_type == 'udp':
       	print("Connecting to {0}:{1}".format(g_sonar_ip,g_udp_port)) 
        g_ping_360.connect_udp(g_sonar_ip,g_udp_port)
    print("Initialized: %s" % g_ping_360.initialize())
    return

def smallest_angle_between(angle_a_grads, angle_b_grads):
    ''' Returns the smaller of the two possible sectors between angle a & b. Result is always positive.'''
    return min( (angle_a_grads - angle_b_grads)%400,
                (angle_b_grads-angle_a_grads)%400 )

def angle_within(test_angle_grads, sector_start_grads, sector_end_grads):
    ''' Returns true if the test angle lies within the sector defined by a clockwise rotation from the
    sector start angle to the sector end angle'''
    if sector_start_grads > sector_end_grads:
        sector_end_grads += 400
    if sector_start_grads > test_angle_grads:
        test_angle_grads +=400
    return sector_start_grads <= test_angle_grads <= sector_end_grads

def calc_initial_transmit_angle():
    global g_transmit_angle_grads, g_ping_360

    device_state = g_ping_360.get_device_data()
    if device_state is not None: # TODO: properly handle case where no device state is returned
        head_angle_grads = device_state['angle']
        print('calc_initial_transmit_angle: Got device state ')

    start_angle_grads = inputs['START_ANGLE_GRADS']['val']
    stop_angle_grads = inputs['STOP_ANGLE_GRADS']['val']

    # TODO: Logic assumes sonar head always rotated via shortest route
    angle_to_start_grads = smallest_angle_between(head_angle_grads, start_angle_grads)
    angle_to_stop_grads  = smallest_angle_between(head_angle_grads, stop_angle_grads)

    if angle_to_start_grads <= angle_to_stop_grads:
        g_transmit_angle_grads = start_angle_grads
    else:
        g_transmit_angle_grads = stop_angle_grads

    set_output('TRANSMIT_ANGLE_GRADS', g_transmit_angle_grads)
    set_output('TRANSMIT_ANGLE_DEGS', g_transmit_angle_grads * 360 / 400)

    if inputs['DEBUG_ENABLE']['val']:
        print("Initial transmit angle: {0} gradians", g_transmit_angle_grads)

    return

# TODO: accept head angle as argument so that function is easily testable?
def calc_next_transmit_angle():
    global g_clockwise, g_transmit_angle_grads, g_ping360_device_data

    start_angle_grads = inputs['START_ANGLE_GRADS']['val']
    stop_angle_grads = inputs['STOP_ANGLE_GRADS']['val']
    num_steps_grads = inputs ['NUM_STEPS']['val']

    if g_ping360_device_data is not None:
        head_angle_grads = g_ping360_device_data.angle

        # TODO: Test, specifically at limits
        if g_clockwise:
            g_transmit_angle_grads = (head_angle_grads + num_steps_grads)%400
            if not angle_within(g_transmit_angle_grads, start_angle_grads, stop_angle_grads):
                g_transmit_angle_grads -= (2*num_steps_grads) # Reverse
                g_clockwise = False
        else: # counter-clockwise
            g_transmit_angle_grads = (head_angle_grads - num_steps_grads)%400
            if not angle_within(g_transmit_angle_grads, start_angle_grads, stop_angle_grads):
                g_transmit_angle_grads += (2*num_steps_grads) # Reverse
                g_clockwise = True

    g_transmit_angle_grads = g_transmit_angle_grads%400

    set_output('TRANSMIT_ANGLE_GRADS', g_transmit_angle_grads)
    set_output('TRANSMIT_ANGLE_DEGS', g_transmit_angle_grads * 360 / 400)

    if inputs['DEBUG_ENABLE']['val']:
        print('Transmit Angle: {0} gradians, {1} degrees'.
              format(g_transmit_angle_grads, g_transmit_angle_grads * 360 / 400))
    return


def calculate_sample_period_and_transmit_duration():
    """
     @brief Calculate the sample period based on the range, number of samples and
     the speed of sound.

     Adjust the transmit duration for a specific range. Per firmware engineer:
     1. Starting point is TxPulse in usec = ((one-way range in metres) * 8000) / (Velocity of sound in metres
     per second)
     2. Then check that TxPulse is wide enough for currently selected sample interval in usec, i.e.,
          if TxPulse < (2.5 * sample interval) then TxPulse = (2.5 * sample interval)
        (transmit duration is microseconds, samplePeriod() is nanoseconds)
     3. Perform limit checking
     """
    global g_sample_period_ticks, g_sample_period_tick_duration, g_firmware_min_transmit_duration, \
           g_transmit_duration_usec, g_firmware_max_transmit_duration

     # TODO: Don't use globals?
    range = inputs['RANGE']['val']
    number_of_samples = inputs['NUMBER_OF_SAMPLES']['val']
    speed_of_sound = inputs['SPEED_OF_SOUND']['val']

    # g_sample_period_ticks is the number of timer ticks between each data point.
    g_sample_period_ticks = int(2 * range / (number_of_samples * speed_of_sound * g_sample_period_tick_duration))
    sample_period_nsec = g_sample_period_ticks * g_sample_period_tick_duration #TODO: Understand units

    # The maximum transmit duration that will be applied is limited internally by the firmware to prevent damage to the
    # hardware. The maximum transmit duration is equal to 64 * the sample period in microseconds
    max_transmit_duration_usec = min(g_firmware_max_transmit_duration, sample_period_nsec * 64e6)

    # Calculate transmit duration
    g_transmit_duration_usec = round(8000 * range / speed_of_sound)
    g_transmit_duration_usec = max(2.5 * sample_period_nsec/ 1000, g_transmit_duration_usec)
    g_transmit_duration_usec = max(g_firmware_min_transmit_duration, min(max_transmit_duration_usec, g_transmit_duration_usec))



def main():
    global g_scan_sector_changed, g_ping360_device_data, g_comms, g_ping_360, g_transmit_angle_grads, \
           g_transmit_duration_usec, g_sample_period_ticks
    # TODO: Add command line argument specifying ini file?
    # TODO: Add MOOS DB Connection params to the ini file

    assert (sys.version_info.major >= 3 and sys.version_info.minor >= 7), "Python version should be at least 3.7."

    # Parse Ping360.ini file
    try:
        configure_app()
    except Exception as e:
        print ("Error reading parameters from the Ping360.ini file: {0}".format(e))
        sys.exit()

    # Setup MOOS communications
    g_comms.set_on_connect_callback(on_connect)
    g_comms.set_on_mail_callback(on_new_mail)
    g_comms.run('localhost',9000,'iPing360Device') # TODO: Register with unique name

    while True:
        state = outputs['STATE']

        if (state != State.TRANSMITTING.name):
            time.sleep(0.1)

        if (state == State.DB_DISCONNECTED.name):
            # State will be changed to DB_CONNECTED in on_connect
            pass

        elif (state == State.DB_CONNECTED.name):
            if inputs['DEVICE_COMMS_ENABLE']['val'] == 1:
                connect_to_sonar()
                set_output('STATE', State.READY_TO_TRANSMIT.name)
                print ('STATE: READY_TO_TRANSMIT')

        elif (state == State.READY_TO_TRANSMIT.name):
            if inputs ['DEVICE_COMMS_ENABLE']['val'] == 0:
                # TODO: Figure out how to disconnect from sonar?
                #set_output('STATE', State.DB_CONNECTED.name)
                pass
            elif inputs['TRANSMIT_ENABLE']['val'] == 1:
                calc_initial_transmit_angle()
                set_output('STATE',State.TRANSMITTING.name)
                print('STATE: TRANSMITTING')

        elif (state == State.TRANSMITTING.name):
            if inputs['DEVICE_COMMS_ENABLE']['val'] == 0:
                # TODO: Stop motor, Call function to disconnect from sonar?
                pass
            elif g_scan_sector_changed or inputs['TRANSMIT_ENABLE']['val'] == 0:
                g_ping_360.control_motor_off()
                set_output('STATE', State.READY_TO_TRANSMIT.name)
                print('STATE: READY_TO_TRANSMIT')
                g_scan_sector_changed = False

            else:
                g_ping_360.control_transducer(1, int(inputs['GAIN']['val']), int(g_transmit_angle_grads),
                                              int(g_transmit_duration_usec), int(g_sample_period_ticks),
                                              int(inputs['TRANSMIT_FREQUENCY']['val']),
                                              int(inputs['NUMBER_OF_SAMPLES']['val']),1,0)
                response = g_ping_360.wait_message([definitions.PING360_DEVICE_DATA, definitions.COMMON_NACK], 4.0)

                if response is None:
                    set_output('LAST_ERROR','Timeout: No response to control command')
                elif response.name == 'nack':
                    set_output('LAST_ERROR', 'Control Command Nacked')
                elif response.name == 'device_data':
                    #Publish ping data
                    g_ping360_device_data = response
                    set_output('PING_DATA', bytes(g_ping360_device_data.pack_msg_data()) )
                    if inputs['DEBUG_ENABLE']['val']:
                        print(g_ping360_device_data.__repr__())

                    # Log ping data if logging is enabled
                    if inputs['LOG_ENABLE']['val']:
                        g_ping360_logger.log_message(g_ping360_device_data.msg_data)
                        set_output('LOG_STATUS', g_ping360_logger.status)

                    # Only calculate the next transmit angle if the current angle was successfully scanned, so that it
                    # will attempt to scan the same angle again on the text iteration
                    calc_next_transmit_angle()

if __name__=="__main__":
    main()
