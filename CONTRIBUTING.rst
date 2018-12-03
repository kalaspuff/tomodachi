Contributing
============

Instructions for contributors
-----------------------------

Please help out to add features that you deem are missing and/or fix
bugs in the repo.

Clone the repo and install the required dependencies, preferably in a
virtualenv or similar solution.

.. code:: bash

    (venv) local ~$ git clone git@github.com:kalaspuff/tomodachi
    (venv) local ~$ cd tomodachi

    (venv) local ~/tomodachi$ make test

    # Start example service
    (venv) local ~/tomodachi$ python tomodachi.py run examples/basic_examples/http_simple_service.py


To add a PR, for the repository, commit your changes to your own clone 
and make a PR on GitHub for your clone against master branch.

.. _GitHub: https://github.com/kalaspuff/tomodachi
