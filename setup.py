"""setup.py module for natcap.invest

InVEST - Integrated Valuation of Ecosystem Services and Tradeoffs

Common functionality provided by setup.py:
    build_sphinx

For other commands, try `python setup.py --help-commands`
"""

import os
import sys

from setuptools.command.build_ext import build_ext
from setuptools.extension import Extension
from setuptools import setup

import numpy
import natcap.versioner

# Monkeypatch os.link to prevent hard lnks from being formed.  Useful when
# running tests across filesystems, like in our test docker containers.
# Only an issue pre python 2.7.9.
# See http://bugs.python.org/issue8876
PY_VERSION = sys.version_info[0:3]
if PY_VERSION[0] == 2 and PY_VERSION[1] <= 7 and PY_VERSION[2] < 9:
    try:
        del os.link
    except AttributeError:
        pass

# Try to import cython modules, if they don't import assume that Cython is
# not installed and the .c and .cpp files are distributed along with the
# package.
CMDCLASS = {}
try:
    # Overrides the existing build_ext if we can use the cython version.
    from Cython.Distutils import build_ext
    USE_CYTHON = True
except ImportError:
    USE_CYTHON = False

readme = open('README.rst').read()
history = open('HISTORY.rst').read().replace('.. :changelog:', '')
LICENSE = open('LICENSE.txt').read()


def no_cythonize(extensions, **_):
    """Replaces instances of .pyx to .c or .cpp depending on the language
        extension."""

    for extension in extensions:
        sources = []
        for sfile in extension.sources:
            path, ext = os.path.splitext(sfile)
            if ext in ('.pyx', '.py'):
                if extension.language == 'c++':
                    ext = '.cpp'
                else:
                    ext = '.c'
                sfile = path + ext
            sources.append(sfile)
        extension.sources[:] = sources
    return extensions

class ExtraCompilerFlagsBuilder(build_ext):
    """
    Subclass of build_ext for adding specific compiler flags required
    for compilation on some platforms.  If we're using GNU compilers, we
    want to statically link libgcc and libstdc++ so that we don't need to
    package shared objects/dynamically linked libraries with this python
    package.

    Trying to statically link these two libraries on unix (mac) will crash, so
    this is only for windows ports of GNU GCC compilers.
    """
    def build_extensions(self):
        compiler_type = self.compiler.compiler_type
        if compiler_type in ['mingw32', 'cygwin']:
            for ext in self.extensions:
                ext.extra_link_args = [
                    '-static-libgcc',
                    '-static-libstdc++',
                ]
        build_ext.build_extensions(self)

CMDCLASS['build_ext'] = ExtraCompilerFlagsBuilder

EXTENSION_LIST = ([
    Extension(
        name="scenic_quality_cython_core",
        sources=[
        'src/natcap/invest/scenic_quality/scenic_quality_cython_core.pyx'],
        include_dirs=[numpy.get_include()]),
    Extension(
        name="ndr_core",
        sources=['src/natcap/invest/ndr/ndr_core.pyx'],
        language="c++",
        include_dirs=[numpy.get_include()]),
    Extension(
        name="seasonal_water_yield_core",
        sources=['src/natcap/invest/seasonal_water_yield/seasonal_water_yield_core.pyx'],
        language="c++",
        include_dirs=[numpy.get_include()]),
    ])

if not USE_CYTHON:
    EXTENSION_LIST = no_cythonize(EXTENSION_LIST)

setup(
    name='natcap.invest',
    description="InVEST Ecosystem Service models",
    long_description=readme + '\n\n' + history,
    maintainer='James Douglass',
    maintainer_email='jdouglass@stanford.edu',
    url='http://bitbucket.org/natcap/invest',
    namespace_packages=['natcap'],
    packages=[
        'natcap',
        'natcap.invest',
        'natcap.invest.crop_production',
        'natcap.invest.blue_carbon',
        'natcap.invest.carbon',
        'natcap.invest.coastal_vulnerability',
        'natcap.invest.dbfpy',
        'natcap.invest.finfish_aquaculture',
        'natcap.invest.fisheries',
        'natcap.invest.globio',
        'natcap.invest.habitat_quality',
        'natcap.invest.habitat_risk_assessment',
        'natcap.invest.habitat_suitability',
        'natcap.invest.hydropower',
        'natcap.invest.iui',
        'natcap.invest.iui.dbfpy',
        'natcap.invest.marine_water_quality',
        'natcap.invest.ndr',
        'natcap.invest.nearshore_wave_and_erosion',
        'natcap.invest.nutrient',
        'natcap.invest.optimization',
        'natcap.invest.overlap_analysis',
        'natcap.invest.pollination',
        'natcap.invest.recreation',
        'natcap.invest.reporting',
        'natcap.invest.routing',
        'natcap.invest.scenario_generator',
        'natcap.invest.scenic_quality',
        'natcap.invest.sdr',
        'natcap.invest.seasonal_water_yield',
        'natcap.invest.testing',
        'natcap.invest.timber',
        'natcap.invest.wave_energy',
        'natcap.invest.wind_energy',
    ],
    package_dir={
        'natcap': 'src/natcap'
    },
    version=natcap.versioner.parse_version(),
    natcap_version='src/natcap/invest/version.py',
    include_package_data=True,
    install_requires=open('requirements.txt').read().split('\n'),
    include_dirs=[numpy.get_include()],
    setup_requires=['nose>=1.0'],
    license=LICENSE,
    zip_safe=True,
    keywords='invest',
    classifiers=[
        'Intended Audience :: Developers',
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2 :: Only',
        'Topic :: Scientific/Engineering :: GIS'
    ],
    ext_modules=EXTENSION_LIST,
    entry_points={
        'console_scripts': [
            'invest = natcap.invest.iui.cli:main'
        ],
    },
    cmdclass=CMDCLASS,
    package_data={
        'natcap.invest.iui': [
            '*.png',
            '*.json',
            'iui_resources/resources.json',
            'iui_resources/images/*.png',
        ],
        'natcap.invest.reporting': [
            'reporting_data/*.js',
            'reporting_data/*.css',
        ],
        'natcap.invest.scenario_generator': [
            '*.js',
        ],
        'natcap.invest.recreation': [
            '*.php',
            '*.r',
            '*.json',
        ],
        'natcap.invest.wave_energy': [
            'wave_energy_scripts/*.sh',
            'wave_energy_scripts/*.txt'
        ],
    }
)