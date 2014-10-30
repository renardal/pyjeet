#
# Copyright 2014 Cumulus Networks, Inc. All rights reserved.
# Author:   Alexandre Renard <arenardvv@gmail.com>
#
# pyjeet --
# the distributed log analysis tool for networking troubleshooting.
#
from abc import ABCMeta, abstractmethod
from file import *
from network_obj import *

class LogContainer:
    __metaclass__ = ABCMeta

    def __init__(self):
        self.files = []
        self.logs = []
        self.interfaces = []
        self.selected_interfaces = []

    @abstractmethod
    def get_interfaces_files(self, standalone):
        '''
        Return the config files needed to configure interfaces
        '''
        pass

    def set_selected_interfaces(self, selected_interfaces, normalizer=None):
        #select user interfaces with user input in the loaded interfaces
        if not self.interfaces and normalizer:
            self.load_interfaces(normalizer)
        #if no particular interface is chosen get them all
        if not len(selected_interfaces):
            self.selected_interfaces = self.interfaces
        else:
            self.selected_interfaces = self.get_interfaces_from_names(selected_interfaces)

    def load_interfaces(self, normalizer, standalone):
        #loads all interfaces from interface conf files
        files_info = self.get_interfaces_files(standalone)
        for info in files_info:
            for data in File(info['name'], info['content']).normalize(normalizer, is_log=False,debug_context=True).data:
                if not data.has_key('linux_interface'):
                    continue
                if not self.find_interface(data):
                    self.interfaces.append(Interface(data))
        return self

    def load_bridges(self, normalizer, standalone):
        #loads all bridges from brctl conf files
        files_info = self.get_bridges_files(standalone)
        for info in files_info:
            for data in File(info['name'], info['content']).normalize(normalizer, is_log=False,debug_context=True).data:
                if not data.has_key('linux_interface'):
                    continue
                if not self.find_interface(data):
                    self.interfaces.append(Interface(data))
        return self

    def find_interface(self, data):
        for interface in self.interfaces:
            linux = data.get('linux_interface')
            if linux and interface.linux == linux:
                interface.update(data)
                return True
            sdk = data.get('sdk_interface')
            if sdk and interface.sdk == sdk:
                interface.update(data)
                return True
            id = data.get('id')
            if id and interface.id == id:
                interface.update(data)
                return True
        return False

    def get_interfaces_from_names(self, interfaces_name):
        return [interface for interface in self.interfaces if
                (interface.linux and interfaces_name.count(interface.linux)) or (
                    interface.sdk and interfaces_name.count(interface.sdk))]

    def normalize_files(self, normalizer, timestamp, interval, normalized_logs=None):
        for f in self.files:
            f.normalize(normalizer, timestamp, interval, True, True, normalized_logs)
        return self

    def sort_logs(self):
        for f in self.files:
            self.logs.extend(f.data)
        self.logs.sort(lambda l1, l2: int(l1.date - l2.date))
        return self
