from decode_sensor_binary import PingViewerLogReader
from matplotlib import pyplot as plt
from argparse import ArgumentParser
from datetime import datetime
import numpy as np
import cv2 as cv
import copy
import os
import re

from matplotlib import rcParams
rcParams['font.family'] = 'serif'

# 20210305-031345328.bin
# ping360_20210901_123108.bin

start_time = "00:10:00.000"

start_time_obj = datetime.strptime(start_time,"%H:%M:%S.%f")

#Create directory for saving images
date_time = datetime.strftime(datetime.now(), '%Y%m%d_%H%M%S')
folder_name = f"""sonar_data_plots_{date_time}"""
parent_dir="./"
img_save_path = os.path.join(parent_dir,folder_name)

if __name__ == "__main__":

    # Parse arguments
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("file",
                        help="File that contains PingViewer sensor log file.")
    args = parser.parse_args()

    try:
        os.mkdir(img_save_path)
    except OSError as error:
        print(error)

    # Open log and begin processing
    log = PingViewerLogReader(args.file)

    first_iteration = True
    sector_intensities = np.array([])
    scan_num = 0
    start_timestamp = ""

    for index, (timestamp, decoded_message) in enumerate(log.parser()):

        timestamp = re.sub(r"\x00", "", timestamp) # Strip any extra \0x00 (null bytes)
        time_obj = datetime.strptime(timestamp,"%H:%M:%S.%f")

        # Skip to start time
        if time_obj < start_time_obj:
            continue

        # Save timestamp of start of each scan
        if start_timestamp == "":
            start_timestamp = timestamp

        # Extract ping data from message
        angle = decoded_message.angle
        ping_intensities = np.frombuffer(decoded_message.data,
                                    dtype=np.uint8)  # Convert intensity data bytearray to numpy array

        if first_iteration == True:
            first_iteration = False
            sector_intensities = np.zeros((400, len(ping_intensities)), dtype=np.uint8)

        sector_intensities[angle, :] = ping_intensities

        if angle == 199:
            scan_num += 1
            print('Last timestamp',timestamp)

            # Rearrange sector_intensities matrix to match warp co-ordinates (0 is towards right)
            sector_intensities_copy = copy.deepcopy(sector_intensities)
            sector_intensities[0:100] = sector_intensities_copy[300:400]
            sector_intensities[100:400] = sector_intensities_copy[0:300]

            # Warp intensities matrix into circular image
            radius = int(400 / (2 * np.pi))
            warp_flags = flags = cv.WARP_INVERSE_MAP + cv.WARP_POLAR_LINEAR + cv.WARP_FILL_OUTLIERS + cv.INTER_LINEAR
            warped = cv.warpPolar(sector_intensities, center=(radius, radius), maxRadius=radius, dsize=(2 * radius, 2 * radius),
                                   flags=warp_flags)

            # Display images
            fig = plt.figure()
            suptitle = 'Scan ' + str(scan_num)
            plt.suptitle(suptitle)
            plt.title('Start time: ' + start_timestamp + ', End time: ' + timestamp)
            plt.axis('off')
            fig.add_subplot(2,1,1)
            plt.imshow(sector_intensities,interpolation='bilinear',cmap='jet')

            fig.add_subplot(2, 1, 2)
            plt.imshow(warped, interpolation='bilinear',cmap='jet')
            #plt.show()
            plt.savefig(os.path.join(img_save_path, suptitle))

            start_timestamp = ""

