Contributing
============

Instructions for contributors
-----------------------------

Please help out to add features in the library that are missing or
prepare pull requests with solutions to any bug you may encounter
during execution.

If you're already using ``poetry``
(`poetry @ pypi <https://pypi.org/project/poetry/>`_, then please do
so since it's the preferred way of handling the dependencies of this
library. ``poetry`` can also be configured to handle virtualenvs
automatically.

Clone the repo and install the required dependencies.

.. code:: bash

    local ~/code$ git clone git@github.com:kalaspuff/tomodachi
    local ~/code$ cd tomodachi

    # Using poetry
    local ~/code/tomodachi$ poetry install

    # or alternatively with pip
    local ~/code/tomodachi$ pip install -U .

    # Verify that the tomodachi CLI is installed
    local ~/code/tomodachi$ tomodachi --version
    local ~/code/tomodachi$ python -m tomodachi --version

    # If you prefer to not use the CLI entrypoint there's a script available
    # as tomodachi.py
    local ~/code/tomodachi$ python tomodachi.py --version

    # Finally to start services
    local ~/code/tomodachi$ tomodachi run examples/basic_examples/http_simple_service.py


To add a PR, for the repository, commit your changes to your own clone
and make a PR on GitHub for your clone against master branch.

There are GitHub actions enabled to automate most test cases, linting,
type hinting, etc. You can also run them on your own, see ``Makefile``
for a helping hand.

The code must conform to the ``black`` code style and
imports must be sorted alphabetically, and automatically separated into
sections and by type. Use the following ``make`` commands to automate
this:

.. code:: bash

    local ~/code/tomodachi$ make black
    # Runs: black setup.py tomodachi.py tomodachi/ examples/ tests/

    local ~/code/tomodachi$ make isort
    # Runs: isort setup.py tomodachi.py tomodachi/ examples/ tests/


.. _GitHub: https://github.com/kalaspuff/tomodachi
