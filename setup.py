#-*- coding:utf-8 -*-
#
# Copyright (C) 2010 - Brantley Harris <brantley.harris@gmail.com>
#
# Distributed under the MIT license, see LICENSE.txt

import os
from setuptools import setup, find_packages

setup(
    name='minister',
    version = 'dev',
    description = 'Next generation webserver and manager.',
    classifiers = [
        'Development Status :: 3 - Alpha',
    ],
    keywords = 'web server webserver',
    author = 'Brantley Harris',
    author_email = 'deadwisdom@gmail.com',
    url = '',
    license = 'MIT',
    packages = find_packages(exclude=['libs', 'old', 'tests']),
    zip_safe = False,
    install_requires = [
        'eventlet',
        'simplejson',
    ],
    entry_points = {
        'console_scripts': [
            'minister = minister.manager:run',
        ],
    })