#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""tomodachi.py: microservice framework"""

import sys

if __name__ == "__main__":
    if not sys.version_info >= (3, 7):
        print("tomodachi doesn't support Python earlier than 3.7")
        sys.exit(1)

    import tomodachi.cli

    tomodachi.cli.cli_entrypoint()
