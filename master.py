#
# Copyright 2014 Cumulus Networks, Inc. All rights reserved.
# Author:   Julien Fortin <julien.fortin.it@gmail.com>
#
# pyjeet --
# the distributed log analysis tool for networking troubleshooting.
#


import zmq
import os

from gui import *
from host import Host
from logsparser.lognormalizer import LogNormalizer as LN
from clsupport import Clsupport
from slave import Slave
import threading
import pdb
import glob
import logging
import difflib
logging.basicConfig(filename='/var/log/pyjeet.log',level=logging.DEBUG)


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

class Master:
    def __init__(self, args):
        self.args = args
        self.context = zmq.Context()
        self.normalizer = LN('/usr/share/normalizers')
        self.gui = None
        self.hosts = None
        self.port = self.args.port
        self.interval = self.args.interval
        self.verbose = self.args.verbose
        self.display_cb = None
        self.selected_interfaces = {}
        self.selected_hosts = {}
        self.cl_support_archive = self.args.clsupport
        self.cl_support = None
        # used to save current state when user
        # wants to see log line in original file
        self.current_log_buffer = []
        # number of logs in database for loading bar
        self.total_logs = 0
        self.normalized_logs = {'number': 0, 'chunk_size': 0, 'current_chunk': 0}
        self.num_chunks = 50
        # count number lines going to be sent
        # so that it does not exceed limit (useless computation)
        self.output_count = 0
        # max number of lines
        self.cap = 10000

    def timestamp_from_datestr(self, date):
        time_str = {'raw': date}  # a LogNormalizer expects input as a dictionary
        self.normalizer.normalize(time_str)
        if 'date' in time_str:
            return time_str['date'] if type(time_str['date']) == float \
                                    else time.mktime(time_str['date'].timetuple())
        else:
            return 0

    @property
    def date(self):
        if self.args.date:
            if is_number(self.args.date):
                return float(self.args.date)
            elif type(self.args.date) is str:
                return self.timestamp_from_datestr(self.args.date)
            else:
                raise ValueError('--date option takes only timestamp or date_str as parameter')
        else:
            return -1

    def build_topology(self):
        #the topology is used to see if hosts provided by the user are real
        #the host objects are created here by giving info as argument
        """
         Parse dot file to create the topology
         """
        self.hosts = {}
        hosts_infos = \
            [
                {
                    'name': 'localhost',
                    'ip': '127.0.0.1',
                    'port': self.port,
                    'links': [],
                },
            ]
        for info in hosts_infos:
            if not 'port' in info:
                info['port'] = self.args.port
            info['files'] = self._get_list_for_host(None, info['name'],
                                                    [file.split(':') for file in self.args.files if file])
            self.hosts[info['name']] = Host(info)
        if not len(self.hosts):
            raise Exception, 'Error: no host found in the speficied dotfile'

    def run(self):
        # uncommnent next line to use debugging
        # pdb.set_trace()
        self.build_topology()
        self.process_date_arg()
        self.select_files_and_interfaces()
        self.normalize_logs()
        # by default display by host (cl-support considered as host)
        # overwritten by display by interface if valid interface list given
        if self.args.interfaces:
            self.display_cb = self._display_interfaces_history
        else:
            self.display_cb = self._display_hosts_history

        if not self.is_master_ready():
            return 1

        if self.gui:
            output = None
            while 42:
                req = self.gui.run(output, self.cap)
                # thread to not go back to shell while processing
                # only cosmetics
                self.gui.launch_waiting_thread()
                output = self.analyse_gui_req(req)
        else:
            self.display()

        self.clean()
        return 0

    def process_date_arg(self):
        # if interval with two dates is given set corresponding middle date and interval
        if self.args.dateInterval:
            if len(self.args.dateInterval) != 2 or any(not isinstance(item, str) for item in self.args.dateInterval):
                raise ValueError('--dateInterval takes two string dates as parameter')
            else:
                (time1, time2) = tuple(float(self.timestamp_from_datestr(self.args.dateInterval[i])) for i in range(2))
                self.args.date = (time1 + time2)/2.
                self.args.interval = (time2 - time1)/2.
                self.interval = self.args.interval

    def select_files_and_interfaces(self):
        #setting the standalone or giving only localhost are equivalent
        if self.args.standalone:
            self.args.hosts = ['localhost']
        if self.args.hosts == ['localhost']:
            self.args.standalone = True
        # if no file is specified select all files in /var/log/ on localhost
        if not self.args.files and not self.cl_support_archive:
            self.args.files = glob.glob("/var/log/*.log")
            for i in range(len(self.args.files)):
                self.args.files[i] = "localhost:" + self.args.files[i]

        # if we get a folder we add all files inside it to file list with corresponding host
        #
        # /!\ not OK need to be fixed, has to ask Slave for remote glob of folder
        if self.args.folders:
            for f in self.args.folders:
                f = f.split(':')
                if len(f) == 2:
                    host = f[0]
                    if f[1][-1] != '/': f[1]+='/'
                    files = glob.glob(f[1]+"*.log")
                    for i in range(len(files)):
                        files[i] = host + ":" + files[i]
                elif len(f) == 1:
                    if f[0][-1] != '/': f[0]+='/'
                    files = glob.glob(f[0]+"*.log")
                else:
                    logging.error("Error in formatting of folders names")
                    sys.exit(1)
                self.args.files += files

        if self.args.hosts:
            self.set_selected_hosts(self.args.hosts)
            self.set_selected_files_for_hosts(self.args.files, self.args.unzip, self.args.standalone)
            self.set_selected_interfaces_for_hosts(self.args.interfaces, self.args.standalone)

        if self.cl_support_archive:
            self.cl_support = Clsupport(self.cl_support_archive)
            self.set_selected_files_for_clsupport(self.args.files, self.args.unzip)
            self.set_selected_interfaces_for_clsupport(self.args.interfaces)

    def normalize_logs(self):
        if self.args.gui:
            self.gui = Gui()
            #launch the load display thread
            try:
                self.compute_num_logs()
                t = threading.Thread(target=self.gui.loading, args=(self.normalized_logs, self.num_chunks, ))
                t.start()
                # normalize logs
                self.normalize()
                # joining loading thread
                main_thread = threading.currentThread()
                for t in threading.enumerate():
                    if t is not main_thread:
                        t.join()
            except (KeyboardInterrupt, SystemExit):
                logging.debug("Error or interrupt while normalizing logs")
                self.normalized_logs['current_chunk'] = self.num_chunks
                self.gui.leave()
                sys.exit()
        else:
            # normalize logs
            self.compute_num_logs()
            self.normalize()

    def compute_num_logs(self):
        if self.hosts:
            for host in self.selected_hosts.values():
                for f in host.files:
                    self.total_logs += sum(1 for l in f.raw)
                    f.raw.seek(0)
        if self.cl_support:
            for f in self.cl_support.files:
                self.total_logs += sum(1 for l in f.raw)
                f.raw.seek(0, 0)
        size_of_chunk = self.total_logs/self.num_chunks
        if size_of_chunk == 0:
            self.normalized_logs['chunk_size'] = 1
            if self.total_logs > 0:
                self.num_chunks = self.total_logs
            else:
                logging.debug("No logs were normalized")
                sys.exit(1)
        else:
            self.normalized_logs['chunk_size'] = size_of_chunk

    def normalize(self):
        if self.hosts:
            self.normalize_hosts(self.normalized_logs)
        if self.cl_support:
            self.cl_support.normalize_files(self.normalizer, self.date,
                                            self.interval, self.normalized_logs).sort_logs()

    def is_master_ready(self):
        if not len(self.selected_hosts) and not self.cl_support:
            logging.error('Error: No valid host nor clsupport archive specified.')
            logging.info('List of given hostname(s) (from the populated dotfile): ' + str(
                self.hosts.keys()) + '.')
            return False
        return True

    def set_selected_hosts(self, desired_hosts):
        for hostname in desired_hosts:
            if hostname and hostname in self.hosts:
                host = self.hosts[hostname]
                host.connect(self.context)
                self.selected_hosts[hostname] = host
            else:
                logging.warn('Warning: Unknown hostname: `' + str(hostname) + '`.')
        return self.selected_hosts

    def set_selected_files_for_hosts(self, file_list, unzip, standalone):
        files = [f.split(':') for f in file_list if f]
        for host in self.selected_hosts.values():
            host.set_files(self._get_list_for_host(None, host.name, files), unzip, standalone)

    def set_selected_files_for_clsupport(self, file_list, unzip):
        if not file_list:
            file_list = glob.glob(self.cl_support.path_to_untar + "/var/log/*.log")
            file_list = [f.split('/')[-1] for f in file_list]
        files = [f.split(':') for f in file_list if f]
        self.cl_support.set_files(self._get_list_for_clsupport(files), unzip)

    def set_selected_interfaces_for_hosts(self, interface_list, standalone):
        if interface_list is None:
            return
        interfaces_names = [interface.split(':') for interface in
                            interface_list if interface]
        for host in self.selected_hosts.values():
            host.load_interfaces(self.normalizer, standalone).set_selected_interfaces(
                self._get_list_for_host(self.hosts.values(), host.name, interfaces_names))
        self.display_cb = self._display_interfaces_history

    def set_selected_interfaces_for_clsupport(self, interface_list):
        if interface_list is None:
            return
        interfaces_names = [interface.split(':') for interface in
                            interface_list if interface]
        self.cl_support.load_interfaces(self.normalizer).set_selected_interfaces(
            self._get_list_for_clsupport(interfaces_names))

    @staticmethod
    # get list for host when arguments of type [host]:[argument]
    def _get_list_for_host(hosts, hostname, src):
        res = []
        for elem in src:
            if len(elem) == 2:
                if elem[0] != hostname:
                    if hosts and not elem[0] in hosts:
                        logging.warn('Warning: Unknown hostname: `' + elem[0] + '`.')
                    continue
                else:
                    res.append(elem[1])
            else:
                # when file does not belong to particular
                # host it is added everywhere
                res.append(elem[0])
        return res

    @staticmethod
    def _get_list_for_clsupport(src):
        res = []
        for elem in src:
            if len(elem) == 2:
                if elem[0] != "clsupport":
                    continue
                else:
                    res.append(elem[1])
            else:
                res.append(elem[0])
        return res

    def normalize_hosts(self, normalized_logs):
        for host in self.selected_hosts.values():
            host.normalize_files(self.normalizer, self.date,
                                 self.interval, normalized_logs).sort_logs()

    def display(self):
        if callable(self.display_cb):
            self.display_cb()

    @property
    def _get_interfaces_history(self):
        if self.gui:
            self.gui.info.line_add('Interface\'s history by host:', (2, 0), "top-left", self.gui.window)
        content = []
        for host in self.selected_hosts.values():
            for interface in host.selected_interfaces:
                if_name = '[' + str(interface.linux) + '/' + str(interface.sdk) + ']'
                for line in host.logs:
                    if 'intf' in line.data.keys():
                        if line.data['intf'] in [interface.linux, interface.sdk]:
                            content.append(self.__get_display_output_from_line(str(host.name), line, if_name))
                            self.current_log_buffer.append([line, host])
        if self.cl_support:
            host_name = str(self.cl_support.name)
            if not self.cl_support.logs:
                content.append('\tNothing to display')
            else:
                for interface in self.cl_support.selected_interfaces:
                    if_name = '[' + str(interface.linux) + '/' + str(interface.sdk) + ']'
                    for line in self.cl_support.logs:
                        if 'intf' in line.data.keys():
                            if line.data['intf'] in [interface.linux, interface.sdk]:
                                content.append(self.__get_display_output_from_line(host_name, line, if_name))
                                self.current_log_buffer.append([line, self.cl_support])
        return content

    def _get_time_history(self, line, time_input, interval=1000):
        time_str = {'raw': time_input}  # a LogNormalizer expects input as a dictionary
        self.normalizer.normalize(time_str)
        time_input = (
            time_str['date'] if type(time_str['date']) == float else time.mktime(time_str['date'].timetuple())) \
            if 'date' in time_str else 0.0
        return abs(line.date - float(time_input)) < float(interval)

    @staticmethod
    def _get_grep_history(line, pattern):
        return 'raw' in line.data.keys() and pattern in line.data['raw']

    @staticmethod
    def _get_ip_history(line, pattern):
        return 'ip' in line.data.keys() and pattern == line.data['ip']

    def _get_history(self, label, search_callback=None, *args):
        self.output_count = 0
        if self.gui:
            self.gui.info.line_add(label, (2, 0), "top-left", self.gui.window)
        content = []
        for host in self.selected_hosts.values():
            if not host.logs:
                content.append('\tNothing to display')
            else:
                for line in host.logs:
                    if (search_callback and search_callback(line, *args)) or not search_callback:
                        content.append(self.__get_display_output_from_line(str(host.name), line))
                        self.current_log_buffer.append([line, host])
                        self.output_count += 1
                        if self.output_count >= self.cap:
                            return content
        if self.cl_support:
            host_name = str(self.cl_support.name)
            if not self.cl_support.logs:
                content.append('\tNothing to display')
            else:
                for line in self.cl_support.logs:
                    if (search_callback and search_callback(line, *args)) or not search_callback:
                        content.append(self.__get_display_output_from_line(host_name, line))
                        self.current_log_buffer.append([line, self.cl_support])
                        self.output_count += 1
                        if self.output_count >= self.cap:
                            return content
        return content

    def __get_display_output_from_line(self, host_name, line, interface='', line_number=''):
        if not self.verbose:
            output = ('[' + str(line.date) + '] ' + (
                line.message.body if line.message.body else line.message.raw))
        else:
            output = (line_number + '[' + str(host_name) + ']' + interface + ' [' +
                              str(line.verbose_date() if line.verbose_date() else line.date) + ']' +
                            ' [' + str(line.context.logfile).split('/')[-1] + '] ' +
                            (line.message.body if line.message.body else line.message.raw))
        try:
            output.encode('utf-8')
        except UnicodeDecodeError:
            pass
        return output

    def _display_hosts_history(self):
        for line in self._get_history('History by host:'):
            print line

    def _display_interfaces_history(self):
        for line in self._get_interfaces_history:
            print line

    def _get_origin_file(self, label, log, host):
        highlight_number = None
        self.gui.info.line_add(label, (2, 0), "top-left", self.gui.window)
        content = []
        if not log.context.root_file:
            content.append('\tNothing to display')
        else:
            for (i, line) in enumerate(log.context.root_file.data):
                line_number = "[l%d] " % i
                content.append(self.__get_display_output_from_line(str(host.name), line,'',line_number))
                if line == log:
                    highlight_number = content.__len__() - 1
            if not highlight_number:
                logging.error("Provided log not found in original file: %s" % str(log.raw))
                sys.exit(1)
            else:
                return content, highlight_number

    def _get_frequency_listing(self, label, log, host):
        self.gui.info.line_add(label, (2, 0), "top-left", self.gui.window)
        content = []
        time_slices = []
        num_max = 0
        treshold = 0.7
        time_span = 1000
        if not 'body' in log.data:
            return [], 0
        for line in host.logs:
            if 'body' in line.data:
                sim = difflib.SequenceMatcher(None, line.data['body'], log.data['body']).ratio()
                if sim > treshold: 
                    if len(time_slices) == 0:
                        time_slices.append([line.date, 1, str(line.verbose_date() if line.verbose_date() else line.date)])
                        continue
                    if line.date - time_slices[-1][0] < time_span:
                        time_slices[-1][1] += 1    
                        if time_slices[-1][1] > num_max:
                            num_max = time_slices[-1][1]
                    else:
                        time_slices.append([line.date, 1, str(line.verbose_date() if line.verbose_date() else line.date)])
        for result in time_slices:
            content.append('[' + result[2] + '] ' + str(result[1]))
        return content, num_max

    def analyse_gui_req(self, req):
        highlight = None
        num_max = None
        if req.field:
            # flush current log buffer
            self.current_log_buffer = []
            display = LogHistory
            if req.field.name == "interface":
                self.set_selected_interfaces_for_hosts(req.field.input.split(), self.args.standalone)
                if self.cl_support_archive:
                    self.set_selected_interfaces_for_clsupport(req.field.input.split())
                content = self._get_interfaces_history
            elif req.field.name == "grep":
                content = self._get_history('History of grep pattern by host:', self._get_grep_history, req.field.input)
            elif req.field.name == "time":
                content = self._get_history('History at given time by host:', self._get_time_history,
                                            *req.field.input.split('|'))
            elif req.field.name == "ip":
                content = self._get_history('History of ip adresss by host:', self._get_ip_history, req.field.input)
            else:
                display = LogHistory
                content = self._get_history('History by host:')
        elif req.line_number >= 0:
            # see log line in its original file
            log = self.current_log_buffer[req.line_number][0]
            host = self.current_log_buffer[req.line_number][1]
            if req.operation == "origin":
                display = OriginFile
                content, highlight = self._get_origin_file('Log line in its original File:', log, host)
            elif req.operation == "frequency":
                logging.debug("User requested frequency of log line")
                display = LogFrequency
                content, num_max = self._get_frequency_listing("Frequency for < %s >:" % log.data['raw'], log, host)
            else:
                logging.error("Error Unknown operation in Request %s" % req.operation)
                sys.exit(0)
        else:
            display = LogHistory
            content = self._get_history('History by host:')
        if len(content) >= 1:
            return Output(display).fill_content_from_strings(content).set_highlighted_line(highlight).set_max_frequency(num_max)
        else:
            return None

    def clean(self):
        if self.cl_support:
            self.cl_support.clean()
        #clean temp directory
        dir_path = "/var/log/pyjeet_temp"
        if os.path.exists(dir_path):
            os.system("rm -rf %s" % dir_path)
	if self.gui:
	    self.gui.leave(self.normalized_logs, self.num_chunks)
        self.num_chunks = 50
