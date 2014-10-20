#
# Copyright 2014 Cumulus Networks, Inc. All rights reserved.
# Author:   Alexandre Renard <arenardvv@gmail.com>
#
# pyjeet --
# the distributed log analysis tool for networking troubleshooting.
#

from logcontainer import *


class Clsupport(LogContainer):
    def __init__(self, path_to_archive):
        LogContainer.__init__(self)
        self.path_to_archive = path_to_archive
        self.path_to_untar = None
        self.name = None

        self.untar()
        self._get_name_from_path()

    def _get_name_from_path(self):
        if "cl_support__" not in self.path_to_archive:
            raise ValueError("The given path does not point to a cl-support archive: %s" % self.path_to_archive)
        else:
            self.name = self.path_to_archive.split('/')[-1].split('_')[3] + '(cls)'
            self.path_to_untar = "./" + self.path_to_archive.split('/')[-1].split('.')[0]

    def untar(self):
        os.system("tar -zxf %s" % self.path_to_archive)

    def get_interfaces_files(self, standalone):
        #get files from untared archive in config folder
        files = [{'name': self.path_to_untar + "/support/porttab", 'content': None}]
        return files

    def set_files(self, selected_files, unzip):
        for filename in selected_files:
            path_to_file = self.path_to_untar + '/var/log/' + filename
            if not os.path.isfile(path_to_file):
                print '[' + self.name + '] Error: ' + path_to_file + ': File not found in clsupport'
                continue
            else:
                self.files.append(File(path_to_file, None, unzip))

    def clean(self):
        if os.path.exists(self.path_to_untar):
            os.system("rm -rf %s" % self.path_to_untar)
            pass