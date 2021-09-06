#!/usr/bin/env python3

# TODO: Remove imports which are not required
import sys
import struct
from argparse import ArgumentParser
from brping import PingParser
from dataclasses import dataclass
from typing import IO, Any
from datetime import datetime


@dataclass
class PingViewerBuildInfo:
    hash_commit: str = 'a1e1cb2'
    date: str = '2019-09-24T11:41:18-03:00'
    tag: str = 'v2.0.4'
    os_name: str = 'Windows 10 (10.0)'
    os_version: str = '10'

    def __str__(self):
        return f"""
PingViewerBuildInfo:
    hash: {self.hash_commit}
    date: {self.date}
    tag: {self.tag}
    os:
        name: {self.os_name}
        version: {self.os_version}
    """


@dataclass
class Sensor:
    family: int = 1
    type_sensor: int = 2

    def __str__(self):
        return f"""Sensor:
    Family: {self.family}
    Type: {self.type_sensor}
    """


@dataclass
class Header:
    string: str = 'PingViewer sensor log file'
    version: int = 1
    ping_viewer_build_info = PingViewerBuildInfo()
    sensor = Sensor()

    def __str__(self):
        return f"""Header:
    String: {self.string}
    Version: {self.version}
    PingViewerBuildInfo:
        hash: {self.ping_viewer_build_info.hash_commit}
        date: {self.ping_viewer_build_info.date}
        tag: {self.ping_viewer_build_info.tag}
        os:
            name: {self.ping_viewer_build_info.os_name}
            version: {self.ping_viewer_build_info.os_version}
    Sensor:
        Family: {self.sensor.family}
        Type: {self.sensor.type_sensor}
    """


class Ping360Logger():
    def __init__(self):
        self.file = None
        self.header = Header()
        self.messages = []
        self.status = "Disabled"

    def file_write(self, data):
        try:
            self.file.write(data)
            self.status = "Enabled"
        except IOError as e:
            self.status = f"""Error: {e}"""

    def pack_int(self, data: int):
        data_format = '>1i'
        packed_data = struct.Struct(data_format).pack(data)
        self.file_write(packed_data)

    def pack_array(self, array: bytearray):
        self.pack_int(len(array))
        self.file_write(array)

    def pack_string(self, text: str):
        encoding = 'UTF-16-BE'
        encoded_text = text.encode(encoding)
        self.pack_int(len(encoded_text.decode()))
        self.file_write(encoded_text)

    def pack_header(self):
        self.pack_string(self.header.string)
        self.pack_int(self.header.version)

        self.pack_string(self.header.ping_viewer_build_info.hash_commit)
        self.pack_string(self.header.ping_viewer_build_info.date)
        self.pack_string(self.header.ping_viewer_build_info.tag)
        self.pack_string(self.header.ping_viewer_build_info.os_name)
        self.pack_string(self.header.ping_viewer_build_info.os_version)

        self.pack_int(self.header.sensor.family)
        self.pack_int(self.header.sensor.type_sensor)

    def log_message(self, msg_data):
        '''Logs the msg_data bytearray to the file with the current timestamp.
        Returns if no file is open for logging'''
        if self.file is None:
            return
        timestamp = str(datetime.now().time())[:-3]
        self.pack_string(timestamp)
        self.pack_array(msg_data)

    def create_new_file(self, dir):
        '''Closes any existing file, opens a new file in the specified dir and adds the header data.
        The file name format is ping360_<YYYYMMDD>_<HHMMSS>.bin '''
        if self.file is not None:
            self.file.close()
            self.file = None

        date_time = datetime.strftime(datetime.now(), '%Y%m%d_%H%M%S')
        file_name = f"""{dir}ping360_{date_time}.bin"""
        try:
            self.file = open(file_name, 'wb')
        except (OSError, IOError) as e:
            print(e)
            self.status = f"""Error: {e}"""
            return False

        self.pack_header()
        self.status = "Enabled"
        return True

    def close_log_file(self):
        if self.file is not None:
            self.file.close()
        self.status = "Disabled"