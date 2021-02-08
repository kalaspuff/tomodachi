if __name__ == "__main__":
    import sys  # noqa  # isort:skip
    from tomodachi.cli import CLI  # noqa  # isort:skip

    CLI().run_command(sys.argv[1:])
