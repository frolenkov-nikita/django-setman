#!/usr/bin/env python

import os

from distutils.core import setup


DIRNAME = os.path.dirname(__file__)

readme = open(os.path.join(DIRNAME, 'README.rst'), 'r')
README = readme.read()
readme.close()

version = __import__('setman').get_version()


setup(
    name='django-setman',
    version=version,
    description='Django settings manager. Another.',
    long_description=README,
    author='Igor Davydenko',
    author_email='playpauseandstop@gmail.com',
    maintainer='Igor Davydenko',
    maintainer_email='playpauseandstop@gmail.com',
    url='https://github.com/odeskps/django-setman',
    packages=[
        'setman',
        'setman.management',
        'setman.management.commands',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'License :: OSI Approved :: BSD License',
    ],
    keywords='django settings manager',
    license='BSD License',
    requires='expiringdict',
)
