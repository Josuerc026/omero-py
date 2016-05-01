#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2009-2014 Glencoe Software, Inc. All Rights Reserved.
# Use is subject to license terms supplied in LICENSE.txt
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

"""
   Startup plugin for command-line importer.

"""

import os
import csv
import sys
import shlex
import fileinput

from omero.cli import BaseControl, CLI
import omero.java
from omero_ext.argparse import SUPPRESS
from path import path

START_CLASS = "ome.formats.importer.cli.CommandLineImporter"
TEST_CLASS = "ome.formats.test.util.TestEngine"

HELP = """Run the Java-based command-line importer

This is a Python wrapper around the Java importer. Login is handled by Python
OMERO.cli. To see more options, use "--javahelp".

Options marked with "**" are passed strictly to Java. If they interfere with
any of the Python arguments, you may need to end precede your arguments with a
"--".
"""
EXAMPLES = """
Examples:

  # Display help
  $ bin/omero import -h
  # Import foo.tiff using current login
  $ bin/omero import ~/Data/my_file.dv
  # Import foo.tiff using input credentials
  $ bin/omero import -s localhost -u user -w password foo.tiff
  # Set Java debugging level to ALL
  $ bin/omero import foo.tiff -- --debug=ALL
  # Display used files for importing foo.tiff
  $ bin/omero import foo.tiff -f
  # Limit debugging output
  $ bin/omero import -- --debug=ERROR foo.tiff

For additional information, see:
http://www.openmicroscopy.org/site/support/omero5.2/users/cli/import.html
Report bugs to <ome-users@lists.openmicroscopy.org.uk>
"""
TESTHELP = """Run the Importer TestEngine suite (devs-only)"""
DEBUG_CHOICES = ["ALL", "DEBUG", "ERROR", "FATAL", "INFO", "TRACE", "WARN"]
OUTPUT_CHOICES = ["legacy", "yaml"]
SKIP_CHOICES = ['all', 'checksum', 'minmax', 'thumbnails', 'upgrade']


class ImportControl(BaseControl):

    COMMAND = [START_CLASS]

    def _configure(self, parser):
        parser.add_login_arguments()

        parser.add_argument(
            "--javahelp", "--java-help",
            action="store_true", help="Show the Java help text")
        parser.add_argument(
            "--advanced-help", action="store_true", dest="java_advanced_help",
            help="Show the advanced help text")

        parser.add_argument(
            "---bulk", nargs="?",
            help="Bulk YAML file for driving multiple imports")
        parser.add_argument(
            "---logprefix", nargs="?",
            help="Directory or file prefix to prepend to ---file and ---errs")
        parser.add_argument(
            "---file", nargs="?",
            help="File for storing the standard out of the Java process")
        parser.add_argument(
            "---errs", nargs="?",
            help="File for storing the standard err of the Java process")

        parser.add_argument(
            "--clientdir", type=str,
            help="Path to the directory containing the client JARs. "
            " Default: lib/client")
        parser.add_argument(
            "--logback", type=str,
            help="Path to a logback xml file. "
            " Default: etc/logback-cli.xml")

        # The following arguments are strictly passed to Java
        name_group = parser.add_argument_group(
            'Naming arguments', 'Optional arguments passed strictly to Java.')
        name_group.add_argument(
            "-n", "--name", dest="java_name",
            help="Image or plate name to use (**)",
            metavar="NAME")
        name_group.add_argument(
            "-x", "--description", dest="java_description",
            help="Image or plate description to use (**)",
            metavar="DESCRIPTION")
        # Deprecated naming arguments
        name_group.add_argument(
            "--plate_name", dest="java_plate_name",
            help=SUPPRESS)
        name_group.add_argument(
            "--plate_description", dest="java_plate_description",
            help=SUPPRESS)

        # Feedback options
        feedback_group = parser.add_argument_group(
            'Feedback arguments',
            'Optional arguments passed strictly to Java allowing to report'
            ' errors to the OME team.')
        feedback_group.add_argument(
            "--report", action="store_true", dest="java_report",
            help="Report errors to the OME team (**)")
        feedback_group.add_argument(
            "--upload", action="store_true", dest="java_upload",
            help=("Upload broken files and log file (if any) with report."
                  " Required --report (**)"))
        feedback_group.add_argument(
            "--logs", action="store_true", dest="java_logs",
            help=("Upload log file (if any) with report."
                  " Required --report (**)"))
        feedback_group.add_argument(
            "--email", dest="java_email",
            help="Email for reported errors. Required --report (**)",
            metavar="EMAIL")
        feedback_group.add_argument(
            "--qa-baseurl", dest="java_qa_baseurl",
            help=SUPPRESS)

        # Annotation options
        annotation_group = parser.add_argument_group(
            'Annotation arguments',
            'Optional arguments passed strictly to Java allowing to annotate'
            ' imports.')
        annotation_group.add_argument(
            "--annotation-ns", dest="java_ns", metavar="ANNOTATION_NS",
            help="Namespace to use for subsequent annotation (**)")
        annotation_group.add_argument(
            "--annotation-text", dest="java_text", metavar="ANNOTATION_TEXT",
            help="Content for a text annotation (requires namespace) (**)")
        annotation_group.add_argument(
            "--annotation-link", dest="java_link",
            metavar="ANNOTATION_LINK",
            help="Comment annotation ID to link all images to (**)")
        annotation_group.add_argument(
            "--annotation_ns", dest="java_ns", metavar="ANNOTATION_NS",
            help=SUPPRESS)
        annotation_group.add_argument(
            "--annotation_text", dest="java_text", metavar="ANNOTATION_TEXT",
            help=SUPPRESS)
        annotation_group.add_argument(
            "--annotation_link", dest="java_link", metavar="ANNOTATION_LINK",
            help=SUPPRESS)

        java_group = parser.add_argument_group(
            'Java arguments', 'Optional arguments passed strictly to Java')
        java_group.add_argument(
            "-f", dest="java_f", action="store_true",
            help="Display the used files and exit (**)")
        java_group.add_argument(
            "-c", dest="java_c", action="store_true",
            help="Continue importing after errors (**)")
        java_group.add_argument(
            "-l", dest="java_l",
            help="Use the list of readers rather than the default (**)",
            metavar="READER_FILE")
        java_group.add_argument(
            "-d", dest="java_d",
            help="OMERO dataset ID to import image into (**)",
            metavar="DATASET_ID")
        java_group.add_argument(
            "-r", dest="java_r",
            help="OMERO screen ID to import plate into (**)",
            metavar="SCREEN_ID")
        java_group.add_argument(
            "-T", "--target", dest="java_target",
            help="OMERO target specification (**)",
            metavar="TARGET")
        java_group.add_argument(
            "--debug", choices=DEBUG_CHOICES, dest="java_debug",
            help="Turn debug logging on (**)",
            metavar="LEVEL")
        java_group.add_argument(
            "--output", choices=OUTPUT_CHOICES, dest="java_output",
            help="Set an alternative output style",
            metavar="TYPE")

        parser.add_argument(
            "--depth", default=4, type=int,
            help="Number of directories to scan down for files")
        parser.add_argument(
            "--skip", type=str, choices=SKIP_CHOICES, action='append',
            help="Optional step to skip during import")
        parser.add_argument(
            "path", nargs="*",
            help="Path to be passed to the Java process")

        parser.set_defaults(func=self.importer)

    def set_login_arguments(self, args):
        """Set the connection arguments"""

        # Connection is required unless help arguments or -f is passed
        connection_required = ("-h" not in self.command_args and
                               not args.java_f and
                               not args.java_advanced_help)
        if connection_required:
            client = self.ctx.conn(args)
            self.command_args.extend(["-s", client.getProperty("omero.host")])
            self.command_args.extend(["-p", client.getProperty("omero.port")])
            self.command_args.extend(["-k", client.getSessionId()])

    def set_skip_arguments(self, args):
        """Set the arguments to skip steps during import"""
        if not args.skip:
            return

        if ('all' in args.skip or 'checksum' in args.skip):
            self.command_args.append("--checksum-algorithm=File-Size-64")
        if ('all' in args.skip or 'thumbnails' in args.skip):
            self.command_args.append("--no-thumbnails")
        if ('all' in args.skip or 'minmax' in args.skip):
            self.command_args.append("--no-stats-info")
        if ('all' in args.skip or 'upgrade' in args.skip):
            self.command_args.append("--no-upgrade-check")

    def set_java_arguments(self, args):
        """Set the arguments passed to Java"""
        # Due to the use of "--" some of these like debug
        # will never be filled out. But for completeness
        # sake, we include them here.
        java_args = {
            "java_f": "-f",
            "java_c": "-c",
            "java_l": "-l",
            "java_d": "-d",
            "java_r": "-r",
            "java_target": ("--target",),
            "java_name": ("--name",),
            "java_description": ("--description",),
            "java_plate_name": ("--plate_name",),
            "java_plate_description": ("--plate_description",),
            "java_report": ("--report"),
            "java_upload": ("--upload"),
            "java_logs": ("--logs"),
            "java_email": ("--email"),
            "java_debug": ("--debug",),
            "java_output": ("--output",),
            "java_qa_baseurl": ("--qa-baseurl",),
            "java_ns": "--annotation-ns",
            "java_text": "--annotation-text",
            "java_link": "--annotation-link",
            "java_advanced_help": "--advanced-help",
            }

        for attr_name, arg_name in java_args.items():
            arg_value = getattr(args, attr_name)
            if arg_value:
                if isinstance(arg_name, tuple):
                    arg_name = arg_name[0]
                    self.command_args.append(
                        "%s=%s" % (arg_name, arg_value))
                else:
                    self.command_args.append(arg_name)
                    if isinstance(arg_value, (str, unicode)):
                        self.command_args.append(arg_value)

    def importer(self, args):

        if args.clientdir:
            client_dir = path(args.clientdir)
        else:
            client_dir = self.ctx.dir / "lib" / "client"
        etc_dir = self.ctx.dir / "etc"
        if args.logback:
            xml_file = path(args.logback)
        else:
            xml_file = etc_dir / "logback-cli.xml"
        logback = "-Dlogback.configurationFile=%s" % xml_file

        try:
            classpath = [file.abspath() for file in client_dir.files("*.jar")]
        except OSError as e:
            self.ctx.die(102, "Cannot get JAR files from '%s' (%s)"
                         % (client_dir, e.strerror))
        if not classpath:
            self.ctx.die(103, "No JAR files found under '%s'" % client_dir)

        xargs = [logback, "-Xmx1024M", "-cp", os.pathsep.join(classpath)]

        # Create import command to be passed to Java
        self.command_args = []
        if args.javahelp:
            self.command_args.append("-h")
        self.set_login_arguments(args)
        self.set_skip_arguments(args)
        self.set_java_arguments(args)
        xargs.append("-Domero.import.depth=%s" % args.depth)

        if args.bulk and args.path:
            self.ctx.die(104, "When using bulk import, omit paths")
        elif args.bulk:
            self.bulk_import(args, xargs)
        else:
            self.do_import(args, xargs)

    def do_import(self, args, xargs):
        out = err = None
        try:
            import_command = self.COMMAND + self.command_args + args.path
            # Open file handles for stdout/stderr if applicable
            out = self.open_log(args.file, args.logprefix)
            err = self.open_log(args.errs, args.logprefix)

            p = omero.java.popen(
                import_command, debug=False, xargs=xargs,
                stdout=out, stderr=err)

            self.ctx.rv = p.wait()

        finally:
            # Make sure file handles are closed
            if out:
                out.close()
            if err:
                err.close()

    def bulk_import(self, args, xargs):

        try:
            from yaml import safe_load
        except ImportError:
            self.ctx.die(105, "yaml is unsupported")

        old_pwd = os.getcwd()
        try:

            # Walk the .yml graph looking for includes
            # and load them all so that the top parent
            # values can be overwritten.
            contents = list()
            bulkfile = args.bulk
            while bulkfile:
                bulkfile = os.path.abspath(bulkfile)
                parent = os.path.dirname(bulkfile)
                with open(bulkfile, "r") as f:
                    data = safe_load(f)
                    contents.append((bulkfile, parent, data))
                    bulkfile = data.get("include")
                    os.chdir(parent)
                    # TODO: include file are updated based on the including file
                    # but other file paths aren't!

            bulk = dict()
            for bulkfile, parent, data in reversed(contents):
                bulk.update(data)
                os.chdir(parent)

            self.optionally_add(args, bulk, "name")
            # TODO: need better mapping
            self.optionally_add(args, bulk, "continue", "java_c")

            for step in self.parse_bulk(bulk, args):
                self.do_import(args, xargs)
                if self.ctx.rv:
                    if args.java_c:
                        self.ctx.err("Import failed with error code: %s. Continuing" % self.ctx.rv)
                    else:
                        self.ctx.die(106, "Import failed. Use -c to continue after errors")
        finally:
            os.chdir(old_pwd)

    def optionally_add(self, args, bulk, key, dest=None):
        if dest is None:
            dest = "java_" + key
        if key in bulk:
            setattr(args, dest, bulk[key])

    def parse_bulk(self, bulk, args):
        path = bulk["path"]
        cols = bulk.get("columns")

        if not cols:
            # No parsing necessary
            args.path = [line]

        else:
            function = self.parse_text
            if path.endswith(".tsv"):
                function = lambda x: self.parse_csv(x, delimiter="\t")
            elif path.endswith(".csv"):
                function = self.parse_csv

            for parts in function(path):
                for idx, col in enumerate(cols):
                    if col == "path":
                        args.path = [parts[idx]]
                    elif hasattr(args, "java_%s" % col):
                        setattr(args, "java_%s" % col, parts[idx])
                    else:
                        setattr(args, col, parts[idx])
                yield parts

    def parse_text(self, path):
        for line in fileinput.input([path]):
            line = line.strip()
            yield shlex.split(line)

    def parse_csv(self, path, delimiter=","):
        with open(path, "r") as data:
            for line in csv.reader(data, delimiter=delimiter):
                yield line

    def open_log(self, file, prefix=None):
        if not file:
            return None
        if prefix:
            file = os.path.sep.join([prefix, file])
        dir = os.path.dirname(file)
        if not os.path.exists(dir):
            os.makedirs(dir)
        return open(file, "w")


class TestEngine(ImportControl):
    COMMAND = [TEST_CLASS]

try:
    register("import", ImportControl, HELP, epilog=EXAMPLES)
    register("testengine", TestEngine, TESTHELP)
except NameError:
    if __name__ == "__main__":
        cli = CLI()
        cli.register("import", ImportControl, HELP, epilog=EXAMPLES)
        cli.register("testengine", TestEngine, TESTHELP)
        cli.invoke(sys.argv[1:])
