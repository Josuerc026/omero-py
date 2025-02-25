#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Read text-based dictionary file formats such as YAML and JSON
"""

#
#  Copyright (C) 2016 University of Dundee. All rights reserved.
#
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

from past.builtins import basestring
import os
import json
import re
from omero.rtypes import unwrap
from future.utils import bytes_to_native_str
import yaml


def get_supported_formats():
    """
    Return the supported formats
    """
    return ('json', 'yaml')


def load(fileobj, filetype=None, single=True, session=None):
    """
    Try and load a file in a format that is convertible to a Python dictionary

    :param fileobj: Either a single json object string, file-path, or OriginalFile:ID
    :param single: If True file should only contain a single document, otherwise a
        list of documents will always be returned. Multiple documents are not
        supported for JSON strings.
    :param session: If fileobj is an OriginalFile:ID a valid session is required
    """

    if not isinstance(fileobj, basestring):
        raise Exception(
            'Invalid type: fileobj must be a filename or json string')

    try:
        data = json.loads(fileobj)
        if isinstance(data, dict):
            if single:
                return data
            return [data]
    except ValueError:
        pass

    m = re.match(r'originalfile:(\d+)$', fileobj, re.I)
    if m:
        rawdata, filetype = get_format_originalfileid(
            int(m.group(1)), filetype, session)
    else:
        rawdata, filetype = get_format_filename(fileobj, filetype)

    if filetype == 'yaml':
        data = list(yaml.safe_load_all(rawdata))
        if single:
            if len(data) != 1:
                raise Exception(
                    "Expected YAML file with one document, found %d" %
                    len(data))
            return data[0]
        return data

    if filetype == 'json':
        try:
            data = json.loads(rawdata)
        except TypeError:
            # for Python 3.5
            data = json.loads(bytes_to_native_str(rawdata))
        if single:
            return data
        return [data]


def dump(data, formattype):
    """
    Convert a python object to a string in the requested format

    :param data: A python object (most likely a dictionary)
    :param formattype: The output format
    """

    if formattype == 'yaml':
        return yaml.dump(data)

    if formattype == 'json':
        return json.dumps(data)

    raise ValueError('Unknown format: %s' % formattype)


def _format_from_name(filename):
    # splitext includes the dot on the extension
    ext = os.path.splitext(filename)[1].lower()[1:]
    if ext in ('yml', 'yaml'):
        return 'yaml'
    if ext in ('js', 'json'):
        return 'json'


def get_format_filename(filename, filetype):
    """Returns bytes from the named json or yaml file."""
    if not filetype:
        filetype = _format_from_name(filename)
    if filetype not in ('json', 'yaml'):
        raise ValueError('Unknown file format: %s' % filename)
    with open(filename, 'rb') as f:
        rawdata = f.read()
    return rawdata, filetype


def get_format_originalfileid(originalfileid, filetype, session):
    if not session:
        raise ValueError(
            'OMERO session required: OriginalFile:%d' % originalfileid)
    f = session.getQueryService().get('OriginalFile', originalfileid)
    if not filetype:
        try:
            mt = unwrap(f.getMimetype()).lower()
        except AttributeError:
            mt = ''
        if mt == 'application/x-yaml':
            filetype = 'yaml'
        if mt == 'application/json':
            filetype = 'json'
    if not filetype:
        filetype = _format_from_name(unwrap(f.getName()))
    if filetype not in ('json', 'yaml'):
        raise ValueError(
            'Unknown file format: OriginalFile:%d' % originalfileid)

    rfs = session.createRawFileStore()
    try:
        rfs.setFileId(originalfileid)
        rawdata = rfs.read(0, rfs.size())
        return rawdata, filetype
    finally:
        rfs.close()
