# vim: tabstop=4 shiftwidth=4 softtabstop=4

#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
import os.path

from Exceptions import (NoTraceException)
from Util import (rcf8222date)
from Shell import (touch_file, append_file,
                    joinpths, load_file, mkdirslist,
                    isfile)

TRACE_FMT = "%s - %s\n"
TRACE_EXT = ".trace"

#common trace actions
CFG_WRITING_FILE = "CFG_WRITING_FILE"
PKG_INSTALL = "PKG_INSTALL"
PYTHON_INSTALL = "PYTHON_INSTALL"
DIR_MADE = "DIR_MADE"
FILE_TOUCHED = "FILE_TOUCHED"
DOWNLOADED = "DOWNLOADED"
AP_STARTED = "AP_STARTED"
PIP_INSTALL = 'PIP_INSTALL'

#trace file types
PY_TRACE = "python"
IN_TRACE = "install"
START_TRACE = "start"

#used to note version of trace
TRACE_VERSION = "TRACE_VERSION"
TRACE_VER = 0x1


class Trace():
    def __init__(self, tracefn):
        self.tracefn = tracefn

    def fn(self):
        return self.tracefn

    def trace(self, cmd, action=None):
        if(action == None):
            action = rcf8222date()
        line = TRACE_FMT % (cmd, action)
        append_file(self.tracefn, line)


class TraceWriter():
    def __init__(self, root, name):
        self.tracer = None
        self.root = root
        self.name = name
        self.started = False

    def _start(self):
        if(self.started):
            return
        else:
            dirs = mkdirslist(self.root)
            self.fn = touch_trace(self.root, self.name)
            self.tracer = Trace(self.fn)
            self.tracer.trace(TRACE_VERSION, str(TRACE_VER))
            if(len(dirs)):
                for d in dirs:
                    self.tracer.trace(DIR_MADE, d)
            self.started = True

    def py_install(self, where):
        self._start()
        self.tracer.trace(PYTHON_INSTALL, where)

    def cfg_write(self, cfgfile):
        self._start()
        self.tracer.trace(CFG_WRITING_FILE, cfgfile)

    def downloaded(self, tgt, fromwhere):
        self._start()
        what = dict()
        what['target'] = tgt
        what['from'] = fromwhere
        self.tracer.trace(DOWNLOADED, json.dumps(what))

    def pip_install(self, name, pip_info):
        self._start()
        what = dict()
        what['name'] = name
        what['pip_meta'] = pip_info
        self.tracer.trace(PIP_INSTALL, json.dumps(what))

    def dir_made(self, *dirs):
        self._start()
        for d in dirs:
            self.tracer.trace(DIR_MADE, d)

    def file_touched(self, fn):
        self._start()
        self.tracer.trace(FILE_TOUCHED, fn)

    def package_install(self, name, pkg_info):
        self._start()
        what = dict()
        what['name'] = name
        what['pkg_meta'] = pkg_info
        self.tracer.trace(PKG_INSTALL, json.dumps(what))

    def started_info(self, name, info_fn):
        self._start()
        data = dict()
        data['name'] = name
        data['trace_fn'] = info_fn
        self.tracer.trace(AP_STARTED, json.dumps(data))


class TraceReader():
    def __init__(self, root, name):
        self.root = root
        self.name = name
        self.trace_fn = trace_fn(root, name)

    def _readpy(self):
        lines = self._read()
        pyfn = None
        pylines = list()
        for (cmd, action) in lines:
            if(cmd == PYTHON_INSTALL and len(action)):
                pyfn = action
                break
        if(pyfn != None):
            lines = load_file(pyfn).splitlines()
            pylines = lines
        return pylines

    def _read(self):
        return parse_name(self.root, self.name)

    def py_listing(self):
        return self._readpy()

    def files_touched(self):
        lines = self._read()
        files = list()
        for (cmd, action) in lines:
            if(cmd == FILE_TOUCHED and len(action)):
                files.append(action)
        files = list(set(files))
        files.sort()
        return files

    def dirs_made(self):
        lines = self._read()
        dirs = list()
        for (cmd, action) in lines:
            if(cmd == DIR_MADE and len(action)):
                dirs.append(action)
        #ensure in ok order (ie /tmp is before /)
        dirs = list(set(dirs))
        dirs.sort()
        dirs.reverse()
        return dirs

    def apps_started(self):
        lines = self._read()
        files = list()
        for (cmd, action) in lines:
            if(cmd == AP_STARTED and len(action)):
                jdec = json.loads(action)
                if(type(jdec) is dict):
                    files.append(jdec)
        return files

    def files_configured(self):
        lines = self._read()
        files = list()
        for (cmd, action) in lines:
            if(cmd == CFG_WRITING_FILE and len(action)):
                files.append(action)
        files = list(set(files))
        files.sort()
        return files

    def pips_installed(self):
        lines = self._read()
        pipsinstalled = dict()
        pip_list = list()
        for (cmd, action) in lines:
            if(cmd == PIP_INSTALL and len(action)):
                pip_list.append(action)
        for pdata in pip_list:
            pip_info_full = json.loads(pdata)
            if(type(pip_info_full) is dict):
                name = pip_info_full.get('name')
                if(name and len(name)):
                    pipsinstalled[name] = pip_info_full.get('pip_meta')
        return pipsinstalled

    def packages_installed(self):
        lines = self._read()
        pkgsinstalled = dict()
        pkg_list = list()
        for (cmd, action) in lines:
            if(cmd == PKG_INSTALL and len(action)):
                pkg_list.append(action)
        for pdata in pkg_list:
            pkg_info = json.loads(pdata)
            if(type(pkg_info) is dict):
                name = pkg_info.get('name')
                if(name and len(name)):
                    pkgsinstalled[name] = pkg_info.get('pkg_meta')
        return pkgsinstalled


def trace_fn(rootdir, name):
    fullname = name + TRACE_EXT
    return joinpths(rootdir, fullname)


def touch_trace(rootdir, name):
    tracefn = trace_fn(rootdir, name)
    touch_file(tracefn)
    return tracefn


def split_line(line):
    pieces = line.split("-", 1)
    if(len(pieces) == 2):
        cmd = pieces[0].rstrip()
        action = pieces[1].lstrip()
        return (cmd, action)
    else:
        return None


def read(rootdir, name):
    pth = trace_fn(rootdir, name)
    contents = load_file(pth)
    lines = contents.splitlines()
    return lines


def parse_fn(fn):
    if(not isfile(fn)):
        msg = "No trace found at filename %s" % (fn)
        raise NoTraceException(msg)
    contents = load_file(fn)
    lines = contents.splitlines()
    accum = list()
    for line in lines:
        ep = split_line(line)
        if(ep == None):
            continue
        accum.append(tuple(ep))
    return accum


def parse_name(rootdir, name):
    fn = trace_fn(rootdir, name)
    return parse_fn(fn)
