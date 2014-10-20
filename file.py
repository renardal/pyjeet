#
# Copyright 2014 Cumulus Networks, Inc. All rights reserved.
# Author:   Julien Fortin <julien.fortin.it@gmail.com>
#           Alexandre Renard <arenardvv@gmail.com>
#
# pyjeet --
# the distributed log analysis tool for networking troubleshooting.
#

import os
import sys

from log import Log


class File:
    def __init__(self, path, content=None, rotate=False):
        self.path = path
        self.data = []
        tmp = self.path.split('/')
        self.name = tmp[len(tmp) - 1]
        self.content = content is not None
        self.raw = None
        self._get_file_content(content, rotate)

    def _get_file_content(self, content, rotate):
        if content is not None:
            self.raw = content
        else:
            if rotate is False:
                try:
                    self.raw = open(self.path, 'r')
                except IOError as e:
                    print self.path + ': ' + e.strerror
                    sys.exit(0)
            else:
                print "Unzipping archived logs..."
                filenames = self._get_rotated_files()
                dir_path = os.getcwd() + "/pyjeet_temp"
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path)
                with open(dir_path + "/" + self.name, 'w') as outfile:
                    #reversed because the highest number is the oldest log file
                    for fname in reversed(filenames):
                        with open(fname) as infile:
                            for line in infile:
                                outfile.write(line)
                self.raw = open(dir_path + "/" + self.name, 'r')

    def _get_rotated_files(self):
        rotation = 1
        rotated_files = []
        while os.path.isfile(self.path + '.' + str(rotation) + '.gz'):
            path_to_archive = self.path + '.' + str(rotation) + '.gz'
            os.system("gzip -d %s" % path_to_archive)
            rotated_files.append(self.path + '.' + str(rotation))
            rotation += 1
        print self.path + '.' + str(rotation) + '.gz'
        return rotated_files

    def get_file_name(self):
        return self.name

    def get_path(self):
        return self.path

    def normalize(self, normalizer, timestamp=-1, interval=-1, is_log=True, debug_context=False, normalized_logs=None):
        last_valid_time = 0
        min = timestamp - interval
        max = timestamp + interval
        for line in self.raw:
            if not is_log:
                self.data.append(normalizer.normalize({'raw': line[:-1] if not self.content else line}))
            else:
                l = Log(self,
                        normalizer.normalize({'raw': line[:-1] if not self.content else line}))
                if not l.date:
                    l.date = last_valid_time
                else:
                    last_valid_time = l.date
                if timestamp == -1 or interval == -1 or l.is_in_interval((min, max)):
                    self.data.append(l)
            if normalized_logs:
                # increase current number of normalized logs
                normalized_logs[0] += 1
                # increase chunk counter if needed, seen by load display thread
                if normalized_logs[0] % normalized_logs[1] == 0:
                    normalized_logs[2] += 1
        return self
