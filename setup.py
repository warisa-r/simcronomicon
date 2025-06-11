#!/usr/bin/env python

import os
import sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

def parse_requirements(filename):
    with open(filename) as f:
        lines = f.readlines()
    # Remove comments and empty lines
    reqs = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
    return reqs

requirements = parse_requirements('requirements.txt')


if sys.argv[-1] == 'publish':
    os.system('python setup.py sdist upload')
    sys.exit()


setup(
    name='simcronomicon',
    version='0.1.0',
    description='A simulation for ... well ..',
    author='Warisa Roongaraya',
    author_email='compund555@gmail.com',
    url='https://github.com/warisa-r/simcronomicon',
    packages=[
        'simcronomicon',
    ],
    package_dir={'simcronomicon': 'simcronomicon'},
    include_package_data=True,
    install_requires=requirements,
    license='MIT',
    zip_safe=False,
    keywords='simcronomicon',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
)
