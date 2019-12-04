#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2015 University of Dundee & Open Microscopy Environment.
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


from __future__ import unicode_literals
from builtins import object
import pytest
import os
from omero.cli import CLI

cli = CLI()
cli.loadplugins()
commands = list(cli.controls.keys())
topics = list(cli.topics.keys())
OMERODIR = os.environ.get('OMERODIR', False)


class TestBasics(object):

    def testHelp(self):
        self.args = ["help", "-h"]
        cli.invoke(self.args, strict=True)

    @pytest.mark.parametrize('recursive', [None, "--recursive"])
    def testHelpAll(self, recursive):
        self.args = ["help", "--all"]
        if recursive:
            self.args.append(recursive)
        cli.invoke(self.args, strict=True)

    @pytest.mark.parametrize('recursive', [None, "--recursive"])
    @pytest.mark.parametrize('command', commands)
    def testHelpCommand(self, command, recursive):
        self.args = ["help", command]
        if recursive:
            self.args.append(recursive)
        cli.invoke(self.args, strict=True)

    @pytest.mark.parametrize('topic', topics)
    def testHelpTopic(self, topic):
        self.args = ["help", topic, "-h"]
        cli.invoke(self.args, strict=True)

    def testHelpList(self):
        self.args = ["help", "list"]
        cli.invoke(self.args, strict=True)

    def testQuit(object):
        cli.invoke(["quit"], strict=True)

    def testVersion(object):
        cli.invoke(["version"], strict=True)

    @pytest.mark.skipif(OMERODIR is False, reason="We need $OMERODIR")
    def testLoadGlob(object, tmp_path, capsys):
        for i in 'abc':
            (tmp_path / (i + 'a.omero')).write_text(
                'config set {i} {i}'.format(i=i))
        cli.invoke(["load", "--glob", str(tmp_path / '*.omero')], strict=True)
        cli.invoke(["config", "get"], strict=True)
        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        for i in 'abc':
            assert '{i}={i}'.format(i=i) in lines
