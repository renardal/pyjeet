#
# Copyright 2014 Cumulus Networks, Inc. All rights reserved.
# Author:   Julien Fortin <julien.fortin.it@gmail.com>
#
# pyjeet --
# the distributed log analysis tool for networking troubleshooting.
#

import os
import zmq
import rfc


class Slave:
    BASE_DIRECTORY = ''#'./log/'#'/var/log/pyjeet'
    IPLINKSHOW_FILE = '/tmp/.pyjeet_ip_link_show'

    def __init__(self, args):
        self.args = args
        self.context = zmq.Context()
        self.server = self.context.socket(zmq.REP)
        self.server.bind('tcp://*:' + str(self.args.port))
        self.command = \
            {
                'get_files': self._get_files,
                'get_interfaces_files': self._get_interfaces_files,
            }

    def run(self):
        while 42:
            try:
                req = self.server.recv_json()
                print req
                if req:
                    result = self.command[req['command']](req['arg'] if 'arg' in req else [])
                    if result:
                        self.server.send_json(result)
            except Exception as e:
                print e
                """
                Stayin' alive.
                Stayin' alive.
                Ah, ha, ha, ha,
                Stayin' alive.
                """

    # target_directory=BASE_DIRECTORY
    def _get_files(self, arg=None, from_base_dir=True):
        files = arg
        # if file not specified get all files in log directory
        if files is None:
            os.path.walk(self.BASE_DIRECTORY, self._get_files_list, files)
        result = {}
        for filename in files:
            if '..' in filename or (from_base_dir and not filename.endswith('log')):
                result[filename] = {'error': 'Non-authorized file.'}
            else:
                print 'GET/ %s' % filename
                path = self.BASE_DIRECTORY + filename
                try:
                    content = []
                    raw = open(path, 'r')
                    for line in raw:
                        content.append(unicode(line[:-1], errors='replace'))
                    result[filename] = {'content': content}
                except IOError as e:
                    print path + ': ' + e.strerror
                    result[filename] = {'error': e.strerror}
        return rfc.create_reply(True, result)

    # get all files in folders and subfolders
    def _get_files_list(self, arg, dirname, names):
        for name in names:
            arg.append(name)

    @staticmethod
    def _get_ip_link_show_path():
        # os.system('ip link show > ' + self.IPLINKSHOW_FILE)
        return './test/ip_link_show'
        # return self.IPLINKSHOW_FILE

    @staticmethod
    def _get_port_tab_path():
        return './test/porttab'

    @staticmethod
    def interface_files():
        return [Slave._get_ip_link_show_path(), Slave._get_port_tab_path()]

    def _get_interfaces_files(self, arg):
        return self._get_files(self.interface_files(), False)

    def clean(self):
        pass
