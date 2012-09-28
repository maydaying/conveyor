# vim:ai:et:ff=unix:fileencoding=utf-8:sw=4:ts=4:
# conveyor/src/main/python/conveyor/address.py
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

# Class Hierarchy of Addresses, Listeners, and Connections
# object
#   + Address
#   |   + _AbstractPipeAddress
#   |   |   - _PosixPipeAddress
#   |   |   - _Win32PipeAddress
#   |   - TcpAddress
#   + Listener
#   |   + _AbstractSocketListener
#   |   |   - _PosixPipeListener
#   |   |   + TcpListener
#   |   - _Win32PipeListener
#   + Connection
#       + _AbstractSocketConnection
#       |   - _PosixSocketConnection
#       |   - _Win32SocketConnection
#       - _Win32PipeConnection
#
# Table of Platform-specific Class Aliases
# +------------------+----------+------------------------+
# | Alias            | Platform | Class                  |
# +------------------+----------+------------------------+
# | PipeAddress      | posix    | _PosixPipeAddress      |
# | PipeAddress      | win32    | _Win32PipeAddress      |
# +------------------+----------+------------------------+
# | PipeListener     | posix    | _PosixPipeListener     |
# | PipeListener     | win32    | _Win32PipeListener     |
# +------------------+----------+------------------------+
# | PipeConnection   | posix    | _PosixSocketConnection |
# | PipeConnection   | win32    | _Win32PipeConnection   |
# +------------------+----------+------------------------+
# | SocketConnection | posix    | _PosixSocketConnection |
# | SocketConnection | win32    | _Win32SocketConnection |
# +------------------+----------+------------------------+
#
# Table of Addresses, Listeners, and Connections by Platform
# +------+----------+-------------------+---------------------+------------------------+
# | Kind | Platform | Address           | Listener            | Connection             |
# +------+----------+-------------------+---------------------+------------------------+
# | pipe | posix    | _PosixPipeAddress | _PosixPipeListener  | _PosixSocketConnection |
# | tcp  | posix    | TcpAddress        | TcpListener         | _PosixSocketConnection |
# | pipe | win32    | _Win32PipeAddress | _Win32PipeListener  | _Win32PipeConnection   |
# | tcp  | win32    | TcpAddress        | TcpListener         | _Win32SocketConnection |
# +------+----------+-------------------+---------------------+------------------------+

import os
import socket

import conveyor.connection
import conveyor.listener

class Address(object):
    @staticmethod
    def parse(s):
        split = s.split(':', 1)
        if 'pipe' == split[0]:
            address = _AbstractPipeAddress._parse(s, split)
        elif 'tcp' == split[0]:
            address = TcpAddress._parse(s, split)
        else:
            raise UnknownProtocolException(s, split[0])
        return address

    def listen(self):
        raise NotImplementedError

    def connect(self):
        raise NotImplementedError

class _AbstractPipeAddress(Address):
    @staticmethod
    def _parse(s, split):
        protocol = split[0]
        assert 'pipe' == protocol
        if 2 != len(split):
            raise MissingPathException(s)
        else:
            path = split[1]
            if 0 == len(path):
                raise MissingPathException(s)
            else:
                address = PipeAddress(path)
                return address

    def __init__(self, path):
        self._path = path

if 'nt' != os.name:
    class _PosixPipeAddress(_AbstractPipeAddress):
        def listen(self):
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.bind(self._path)
            os.chmod(self._path, 0666)
            s.listen(socket.SOMAXCONN)
            listener = conveyor.listener.PipeListener(self._path, s)
            return listener

        def connect(self):
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self._path)
            connection = conveyor.connection.SocketConnection(s, None)
            return connection

    PipeAddress = _PosixPipeAddress

else:
    import win32file
    import win32pipe

    class _Win32PipeAddress(_AbstractPipeAddress):
        def listen(self):
            listener = conveyor.listener.PipeListener(self._path)
            return listener

        def connect(self):
            handle = win32file.CreateFile(
                self._path,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                win32file.FILE_FLAG_OVERLAPPED,
                None)
            win32pipe.SetNamedPipeHandleState(
                handle,
                win32pipe.PIPE_READMODE_MESSAGE,
                None,
                None)
            connection = conveyor.connection.PipeConnection.create(handle)
            return connection

    PipeAddress = _Win32PipeAddress

class TcpAddress(Address):
    @staticmethod
    def _parse(s, split):
        protocol = split[0]
        assert 'tcp' == protocol
        if 2 != len(split):
            raise MissingHostException(s)
        else:
            hostport = split[1].split(':', 1)
            if 2 != len(hostport):
                raise MissingPortException(s)
            else:
                host = hostport[0]
                if 0 == len(host):
                    raise MissingHostException(s)
                else:
                    try:
                        port = int(hostport[1])
                    except ValueError:
                        raise InvalidPortException(s, hostport[1])
                    else:
                        address = TcpAddress(host, port)
                        return address

    def __init__(self, host, port):
        self._host = host
        self._port = port

    def listen(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self._host, self._port))
        s.listen(socket.SOMAXCONN)
        listener = conveyor.listener.TcpListener(s)
        return listener

    def connect(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self._host, self._port))
        connection = conveyor.connection.SocketConnection(s, None)
        return connection

class UnknownProtocolException(Exception):
    def __init__(self, value, protocol):
        Exception.__init__(self, value, protocol)
        self.value = value
        self.protocol = protocol

class MissingHostException(Exception):
    def __init__(self, value):
        Exception.__init__(self, value)
        self.value = value

class MissingPortException(Exception):
    def __init__(self, value):
        Exception.__init__(self, value)
        self.value = value

class InvalidPortException(Exception):
    def __init__(self, value, port):
        Exception.__init__(self, value, port)
        self.value = value
        self.port = port

class MissingPathException(Exception):
    def __init__(self, value):
        Exception.__init__(self, value)
        self.value = value
