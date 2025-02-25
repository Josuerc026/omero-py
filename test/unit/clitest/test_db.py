#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
   Test of the omero db control.

   Copyright 2009-2013 Glencoe Software, Inc. All rights reserved.
   Use is subject to license terms supplied in LICENSE.txt

"""

from future import standard_library
standard_library.install_aliases()
from builtins import str
from builtins import object
import pytest
import os
from omero_ext.path import path
from omero.plugins.db import DatabaseControl
from omero.util.temp_files import create_path
from omero.cli import NonZeroReturnCode
from omero.cli import CLI
import getpass
import builtins

OMERODIR = False
if 'OMERODIR' in os.environ:
    OMERODIR = os.environ.get('OMERODIR')

hash_map = {
    ('0', ''): 'PJueOtwuTPHB8Nq/1rFVxg==',
    ('0', '--no-salt'): 'vvFwuczAmpyoRC0Nsv8FCw==',
    ('1', ''): 'pvL5Tyr9tCD2esF938sHEQ==',
    ('1', '--no-salt'): 'vvFwuczAmpyoRC0Nsv8FCw==',
}


class TestDatabase(object):

    def setup_method(self, method):
        self.cli = CLI()
        self.cli.register("db", DatabaseControl, "TEST")
        self.args = ["db"]
        self.data = {}

        # FIXME: Use a different approach to get omero.db.version etc
        # No-longer stored in "omero.properties"
        if OMERODIR:
            dir = path(OMERODIR).abspath()
            cfg = dir / "etc" / "omero.properties"
            cfg = cfg.abspath()
            self.cli.dir = dir

            for line in cfg.text().split("\n"):
                line = line.strip()
                for x in ("version", "patch"):
                    key = "omero.db." + x
                    if line.startswith(key):
                        self.data[x] = line[len(key)+1:]

        self.file = create_path()
        self.script_file = ""
        if "version" in self.data and "patch" in self.data:
            self.script_file = "%(version)s__%(patch)s.sql" % self.data
        if os.path.isfile(self.script_file):
            os.rename(self.script_file, self.script_file + '.bak')
        assert not os.path.isfile(self.script_file)

    def teardown_method(self, method):
        self.file.remove()
        if os.path.isfile(self.script_file):
            os.remove(self.script_file)
        if os.path.isfile(self.script_file + '.bak'):
            os.rename(self.script_file + '.bak', self.script_file)

    def password(self, string, strict=True):
        self.cli.invoke("db password " + string % self.data, strict=strict)

    def testHelp(self):
        self.args += ["-h"]
        self.cli.invoke(self.args, strict=True)

    @pytest.mark.parametrize(
        'subcommand', DatabaseControl().get_subcommands())
    def testSubcommandHelp(self, subcommand):
        self.args += [subcommand, "-h"]
        self.cli.invoke(self.args, strict=True)

    @pytest.mark.skipif(OMERODIR is False, reason="Needs omero.db.profile")
    def testBadVersionDies(self):
        with pytest.raises(NonZeroReturnCode):
            self.cli.invoke("db script NONE NONE pw", strict=True)

    @pytest.mark.skipif(OMERODIR is False, reason="self.password('') fails")
    def testPasswordIsAskedForAgainIfDiffer(self, mocker):
        mock_get_pass = mocker.patch('getpass.getpass')
        mock_get_pass.side_effect = ["ome", "bad", "ome", "ome"]
        self.password("")
        expected_calls = [
            mocker.call('Please enter password for OMERO root user: '),
            mocker.call('Please re-enter password for OMERO root user: '),
            mocker.call('Please enter password for OMERO root user: '),
            mocker.call('Please re-enter password for OMERO root user: ')
        ]
        mock_get_pass.assert_has_calls(expected_calls)

    @pytest.mark.skipif(OMERODIR is False, reason="self.password('') fails")
    def testPasswordIsAskedForAgainIfEmpty(self, mocker):
        mock_get_pass = mocker.patch('getpass.getpass')
        mock_get_pass.side_effect = ["", "ome", "ome"]
        self.password("")
        expected_calls = [
            mocker.call('Please enter password for OMERO root user: '),
            mocker.call('Please enter password for OMERO root user: '),
            mocker.call('Please re-enter password for OMERO root user: ')
        ]
        mock_get_pass.assert_has_calls(expected_calls)

    @pytest.mark.skipif(OMERODIR is False, reason="self.password() fails")
    @pytest.mark.parametrize('no_salt', ['', '--no-salt'])
    @pytest.mark.parametrize('user_id', ['', '0', '1'])
    @pytest.mark.parametrize('password', ['', 'ome'])
    def testPassword(self, user_id, password, no_salt, capsys, mocker):
        args = ""
        if user_id:
            args += "--user-id=%s " % user_id
        if no_salt:
            args += "%s " % no_salt
        if password:
            args += "%s" % password
        else:
            mock_get_pass = mocker.patch('getpass.getpass')
            mock_get_pass.return_value = "ome"
        self.password(args)
        out, err = capsys.readouterr()
        assert out.strip() == self.password_output(user_id, no_salt)
        if not password:
            if user_id != '' and user_id != '0':
                expected_calls = [
                    mocker.call(f'Please enter password for OMERO user {user_id}: '),
                    mocker.call(f'Please re-enter password for OMERO user {user_id}: ')
                ]
            else:
                expected_calls = [
                    mocker.call('Please enter password for OMERO root user: '),
                    mocker.call('Please re-enter password for OMERO root user: ')
                ]
            mock_get_pass.assert_has_calls(expected_calls)

    @pytest.mark.skip(reason="Can't read omero.db.version")
    @pytest.mark.parametrize('file_arg', ['', '-f', '--file'])
    @pytest.mark.parametrize('no_salt', ['', '--no-salt'])
    @pytest.mark.parametrize('password', ['', '--password ome'])
    def testScript(self, no_salt, file_arg, password, capsys, mocker):
        """
        Recommended usage of db script
        """
        args = "db script " + password
        if no_salt:
            args += " %s" % no_salt
        if file_arg:
            args += " %s %s" % (file_arg, str(self.file))
            output = self.file
        else:
            output = self.script_file

        if not password:
            mock_get_pass = mocker.patch('getpass.getpass')
            mock_get_pass.return_value = "ome"

        self.cli.invoke(args, strict=True)

        out, err = capsys.readouterr()
        assert 'Using %s for version' % self.data['version'] in err
        assert 'Using %s for patch' % self.data['patch'] in err
        if password:
            assert 'Using password from commandline' in err

        with open(output) as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith('insert into password values (0'):
                    assert line.strip() == self.script_output(no_salt)

    @pytest.mark.skipif(OMERODIR is False, reason="Needs omero.db.profile")
    @pytest.mark.parametrize('file_arg', ['', '-f', '--file'])
    @pytest.mark.parametrize('no_salt', ['', '--no-salt'])
    @pytest.mark.parametrize('pos_args', [
        '%s %s %s', '--version %s --patch %s --password %s'])
    def testScriptDeveloperArgs(self, pos_args, no_salt, file_arg, capsys):
        """
        Deprecated and developer usage of db script
        """
        arg_values = ('VERSION', 'PATCH', 'PASSWORD')
        args = "db script " + pos_args % arg_values
        if no_salt:
            args += " %s" % no_salt
        if file_arg:
            args += " %s %s" % (file_arg, str(self.file))
            self.file
        else:
            self.script_file

        with pytest.raises(NonZeroReturnCode):
            self.cli.invoke(args, strict=True)

        out, err = capsys.readouterr()

        assert 'Using %s for version' % (arg_values[0]) in err
        assert 'Using %s for patch' % (arg_values[1]) in err
        assert 'Using password from commandline' in err
        assert 'Invalid Database version/patch' in err

    def password_output(self, user_id, no_salt):
        update_msg = "UPDATE password SET hash = \'%s\'" \
            " WHERE experimenter_id = %s;"
        if not user_id:
            user_id = "0"
        return update_msg % (hash_map[(user_id, no_salt)], user_id)

    def script_output(self, no_salt):
        root_password_msg = "insert into password values (0,\'%s\');"
        return root_password_msg % (hash_map[("0", no_salt)])
