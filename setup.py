#!/usr/bin/env python
import sys
import os
from setuptools import setup, find_packages
import tomodachi.__version__

install_requires = [
    'aioamqp>=0.10.0, <0.11.0',
    'ujson>=1.35',
    'uvloop>=0.8.1',
    'aiobotocore>=0.6.0, <0.7.0',
    'tzlocal>=1.4',
    'aiohttp>=3.0.5, <3.1.0',
    'yarl>=1.1.0',
    'colorama>=0.3.9, <0.4.0'
]

PY_VER = sys.version_info

if not PY_VER >= (3, 5, 3):
    raise RuntimeError("tomodachi doesn't support Python earlier than 3.5.3")


def read(f: str) -> str:
    return str(open(os.path.join(os.path.dirname(__file__), f)).read().strip())


classifiers = [
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3 :: Only',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'License :: OSI Approved :: MIT License',
    'Development Status :: 2 - Pre-Alpha',
    'Topic :: Software Development :: Libraries :: Application Frameworks',
    'Topic :: Software Development :: Libraries :: Python Modules'
]

setup(name='tomodachi',
      version=tomodachi.__version__,
      description=('Python 3 microservice library / framework using asyncio with HTTP, '
                   'websockets, RabbitMQ / AMQP and AWS SNS+SQS support.'),
      long_description='\n\n'.join((read('README.rst'), read('CHANGES.rst'))),
      classifiers=classifiers,
      author='Carl Oscar Aaro',
      author_email='hello@carloscar.com',
      url='https://github.com/kalaspuff/tomodachi',
      download_url='https://pypi.python.org/pypi/tomodachi',
      license='MIT',
      entry_points={
          'console_scripts': [
              'tomodachi = tomodachi.cli:cli_entrypoint'
          ]
      },
      install_requires=install_requires,
      keywords=('tomodachi, microservice, microservices, framework, library, asyncio, '
                'aws, sns, sqs, amqp, rabbitmq, http, websockets, easy, fast, python 3'),
      zip_safe=False,
      packages=find_packages(),
      platforms='any',
      include_package_data=True
      )
