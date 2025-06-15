import os
import sys
import yaml

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

def get_conda_pip_dependencies():
    with open('environment.yml') as f:
        env_yaml = yaml.safe_load(f)
    
    # Get pip dependencies from environment.yml
    pip_deps = []
    if 'dependencies' in env_yaml:
        for dep in env_yaml['dependencies']:
            if isinstance(dep, dict) and 'pip' in dep:
                # Extract just the package names without versions
                for pip_dep in dep['pip']:
                    # Remove version specifiers for setup.py
                    package = pip_dep.split('==')[0].split('>=')[0].split('<=')[0]
                    if package and not package.startswith('-e'):
                        pip_deps.append(package)
    return pip_deps


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
    install_requires=get_conda_pip_dependencies(),
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