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
        self.id = -1
        self.update(data)
        self.history = []

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

    def update(self, data):
        self.set_linux_id(data.get('linux_interface'))
        self.set_sdk_id(data.get('sdk_interface'))
        self.set_ip(data.get('ip_interface'))
        self.set_id(data.get('id_interface'))

    def __str__(self):
        return str(self.linux) + ' ' + str(self.sdk) + ' ' + str(self.id)
