import os
import sys
from setuptools import setup, find_packages

if sys.argv[-1] == 'publish':
    os.system('python setup.py sdist upload')
    sys.exit()

setup(
    name='simcronomicon',
    version='0.1.0',
    description='Event-driven agent-based spread simulation framework for modeling disease spread in realistic spatial environments using geographical data from OpenStreetMap.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Warisa Roongaraya',
    author_email='compund555@gmail.com',
    url='https://github.com/warisa-r/simcronomicon',
    packages=find_packages(),
    package_dir={'simcronomicon': 'simcronomicon'},
    include_package_data=True,
    install_requires=[],  # Empty since dependencies are handled by conda environment
    python_requires='>=3.12',
    license='MIT',
    zip_safe=False,
    keywords=['epidemiology', 'agent-based-modeling', 'disease-spread', 'simulation', 'openstreetmap'],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.12',
        'Topic :: Scientific/Engineering :: Medical Science Apps.',
        'Topic :: Scientific/Engineering :: Information Analysis',
    ],
)