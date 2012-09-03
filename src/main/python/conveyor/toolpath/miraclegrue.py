# vim:ai:et:ff=unix:fileencoding=utf-8:sw=4:ts=4:
# conveyor/src/main/python/conveyor/toolpath/miraclegrue.py
#
# conveyor - Printing dispatch engine for 3D objects and their friends.
# Copyright © 2012 Matthew W. Samsonoff <matthew.samsonoff@makerbot.com>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from __future__ import (absolute_import, print_function, unicode_literals)

import logging
import os
import subprocess
import sys
import threading
import tempfile
import traceback

import conveyor.event

class MiracleGrueConfiguration(object):
    def __init__(self):
        self.miraclegruepath = None
        self.miracleconfigpath = None

class MiracleGrueToolpath(object):
    def __init__(self, configuration):
        self._configuration = configuration
        self._log = logging.getLogger(self.__class__.__name__)

    def slice(self, profile, inputpath, outputpath, with_start_end, task):
        self._log.info('slicing with Miracle Grue')
        try:
            with tempfile.NamedTemporaryFile(suffix='.gcode', delete=False) as startfp:
                if with_start_end:
                    for line in profile.values['print_start_sequence']:
                        print(line, file=startfp)
            startpath = startfp.name
            with tempfile.NamedTemporaryFile(suffix='.gcode', delete=False) as endfp:
                if with_start_end:
                    for line in profile.values['print_end_sequence']:
                        print(line, file=endfp)
            endpath = endfp.name
            arguments = list(
                self._getarguments(
                    inputpath, outputpath, startpath, endpath))
            self._log.debug('arguments=%r', arguments)
            popen = subprocess.Popen(
                arguments, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
            def cancelcallback(task):
                popen.terminate()
            task.cancelevent.attach(cancelcallback)
            popen.poll()
            while None is popen.returncode:
                line = popen.stdout.readline()
                if '' == line:
                    break
                else:
                    self._log.debug('miracle-grue: %s', line)
                    popen.poll()
            code = popen.wait()
            self._log.debug(
                'Miracle Grue terminated with status code %d', code)
            if 0 == code:
                os.unlink(startpath)
                os.unlink(endpath)
            else:
                raise Exception(code)
        except Exception as e:
            self._log.exception('unhandled exception')
            task.fail(e)
            raise
        else:
            task.end(None)

    def _getarguments(self, inputpath, outputpath, startpath, endpath):
        for method in (
            self._getarguments_executable,
            self._getarguments_miraclegrue,
            ):
                for iterable in method(inputpath, outputpath, startpath, endpath):
                    for value in iterable:
                        yield value

    def _getarguments_executable(self, inputpath, outputpath, startpath, endpath):
        yield (self._configuration.miraclegruepath,)

    def _getarguments_miraclegrue(self, inputpath, outputpath, startpath, endpath):
        yield ('-c', self._configuration.miracleconfigpath,)
        yield ('-o', outputpath,)
        yield ('-s', startpath,)
        yield ('-e', endpath,)
        yield (inputpath,)
