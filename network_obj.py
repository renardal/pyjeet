#
# Copyright 2014 Cumulus Networks, Inc. All rights reserved.
# Author:   Julien Fortin <julien.fortin.it@gmail.com>
#           Alexandre Renard <arenardvv@gmail.com>
#
# pyjeet --
# the distributed log analysis tool for networking troubleshooting.
#

class Interface:
    def __init__(self, data):
        self.linux = None
        self.sdk = None
        self.ip = None
        self.id = None
        self.update(data)
        self.history = []
        self.bridge = None

    def set_linux_id(self, linux):
        if self.linux == None:
            self.linux = linux
        return self

    def set_sdk_id(self, sdk):
        if self.sdk == None:
            self.sdk = sdk
        return self

    def set_id(self, id):
        if self.id == None:
            self.id = id
        return self

    def set_ip(self, ip):
        if self.ip == None:
            self.ip = ip

    def set_bridge(self, bridge):
        if self.bridge == None:
            self.bridge = bridge

    def update(self, data):
        self.set_linux_id(data.get('linux_interface'))
        self.set_sdk_id(data.get('sdk_interface'))
        self.set_ip(data.get('ip_interface'))
        self.set_id(data.get('id_interface'))

    def __str__(self):
        return str(self.linux) + ' ' + str(self.sdk) + ' ' + str(self.id)

class Bridge:
    def __init__(self, name):
        self.name = name
        self.interfaces = []
        self.ip = None

    def set_ip(self, ip):
        if self.ip == None:
            self.ip = ip

    def add_if(self, interface):
        if interface not in self.interfaces:
            self.interfaces.append(interface)
