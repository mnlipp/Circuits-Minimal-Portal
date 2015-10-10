import os
from setuptools import setup, find_packages
from imp import new_module
from os import path
from posix import getcwd

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

version = new_module("version")

exec(
    compile(
        open(
            path.join(
                path.dirname(
                    globals().get(
                        "__file__",
                        path.join(getcwd(), "circuits_minpor")
                    )
                ),
                "circuits_minpor/version.py"
            ),
            "r"
        ).read(),
        "circuits_minpor/version.py", "exec"
    ),
    version.__dict__
)

setup(
    name = "circuits-minpor",
    version = version.version,
    author = "Michael N. Lipp",
    author_email = "mnl@mnl.de",
    description = ("A minimal portal based on the circuits component library."),
    license = "GPL",
    keywords = "circuits portal",
    url = "http://packages.python.org/circuits-minpor",
    long_description=read('pypi-overview.rst'),
    data_files=[('', ['pypi-overview.rst'])],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU General Public License (GPL)",
    ],
    packages=find_packages("."),
    package_data={'circuits_minpor': ['static/*',
                                      'templates/*.properties', 
                                      'templates/*.pyhtml',
                                      'templates/themes/default/*'],
                  'circuits_minpor.portlets': ['templates/*.properties', 
                                               'templates/*.pyhtml',
                                               'templates/themes/default/*']},
    install_requires = ['Tenjin', 'rbtranslations', 'circuits-bricks==0.4',
                        'circuits==3.1'],
)