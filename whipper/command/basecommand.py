# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

import argparse
import os
import sys

from whipper.common import (
    drive, config
)

import logging
logger = logging.getLogger(__name__)

# Q: What about argparse.add_subparsers(), you ask?
# A: Unfortunately add_subparsers() does not support specifying the
# formatter_class of subparsers, nor does it support epilogs, so
# it does not quite fit our use case.

# Q: Why not subclass ArgumentParser and extend/replace the relevant
# methods?
# A: If this can be done in a simpler fashion than this current
# implementation, by all means submit a patch.

# Q: Why not argparse.parse_known_args()?
# A: The prefix matching prevents passing '-h' (and possibly other
# options) to the child command.


class BaseCommand():
    """A base command class for whipper commands.

    Creates an argparse.ArgumentParser.
    Override add_arguments() and handle_arguments() to register
    and process arguments before & after argparse.parse_args().

    Provides self.epilog() formatting command for argparse.

    device_option = True adds -d / --device option to current command
    no_add_help = True removes -h / --help option from current command

    Overriding formatter_class sets the argparse formatter class.

    If the 'subcommands' dictionary is set, __init__ searches the
    arguments for subcommands.keys() and instantiates the class
    implementing the subcommand as self.cmd, passing all non-understood
    arguments, the current options namespace, and the full command path
    name.
    """

    device_option = False
    no_add_help = False  # for rip.main.Whipper
    formatter_class = argparse.RawDescriptionHelpFormatter
    config = config.Config()
    config_section = None

    def __init__(self, argv, prog_name, opts):
        self.opts = opts  # for Rip.add_arguments()
        self.prog_name = prog_name

        self.init_parser()
        self.add_arguments()

        if hasattr(self, 'subcommands'):
            self.parser.add_argument('remainder',
                                     nargs=argparse.REMAINDER,
                                     help=argparse.SUPPRESS)

        if self.device_option:
            # pick the first drive as default
            drives = drive.getAllDevicePaths()
            if not drives:
                msg = 'No CD-DA drives found!'
                logger.critical(msg)
                # whipper exited with return code 3 here
                raise IOError(msg)
            self.parser.add_argument('-d', '--device',
                                     action="store",
                                     dest="device",
                                     default=drives[0],
                                     help="CD-DA device")

        self.options = self.parser.parse_args(argv, namespace=opts)

        if self.device_option:
            # this can be a symlink to another device
            self.options.device = os.path.realpath(self.options.device)
            if not os.path.exists(self.options.device):
                msg = 'CD-DA device %s not found!' % self.options.device
                logger.critical(msg)
                raise IOError(msg)

        self.handle_arguments()

        if hasattr(self, 'subcommands'):
            if not self.options.remainder:
                self.parser.print_help()
                sys.exit(0)
            if not self.options.remainder[0] in self.subcommands:
                logger.critical("incorrect subcommand: %s",
                                self.options.remainder[0])
                sys.exit(1)
            self.cmd = self.subcommands[self.options.remainder[0]](
                self.options.remainder[1:],
                prog_name + " " + self.options.remainder[0],
                self.options
            )

    def init_parser(self):
        kw = {
            'prog': self.prog_name,
            'description': self.description,
            'formatter_class': self.formatter_class,
        }
        if hasattr(self, 'subcommands'):
            kw['epilog'] = self.epilog()
        if self.no_add_help:
            kw['add_help'] = False
        self.parser = argparse.ArgumentParser(**kw)

    def add_arguments(self):
        pass

    def handle_arguments(self):
        pass

    def do(self):
        return self.cmd.do()

    def epilog(self):
        s = "commands:\n"
        for com in sorted(self.subcommands.keys()):
            s += "  %s %s\n" % (com.ljust(8), self.subcommands[com].summary)
        return s

    # Wrapper around ArgumentParser.add_argument to add config file support.
    # We prioritise these settings in the following order:
    # command-line arg. > config file setting > default value (in code)
    def add_argument_and_config(self, *args, **kwargs):
        section = None
        if ("section" in kwargs):
            # Section name argument was passed.
            section = kwargs["section"]
            kwargs.pop("section")
        else:
            # Use the current sub-command's default config section name.
            if (self.config_section is None):
                section = "main"
            else:
                section = self.config_section

        # Don't pass the default value to the argument parser.
        # Use it only if the config value isn't found.
        default = None
        if ("default" in kwargs):
            default = kwargs["default"]
            kwargs.pop("default")

        # We use the same key to identify both the argument destination
        # and the config file key.
        key = None
        if ("dest" in kwargs):
            key = kwargs["dest"]
        else:
            raise SyntaxError("parser requires a 'dest' argument")

        # Defaults to string if not specified.
        typesuffix = ''
        if ("type" in kwargs):
            if kwargs["type"] in (int, float):
                typesuffix = kwargs["type"].__name__
            else if kwargs["type"] = bool:
                typesuffix = "boolean"

        # Add the argument.
        # We have 2 levels of default value. When an option is not set on the
        # command line, we default to using the value from the config file. If
        # that doesn't exist, we use the default as passed by the caller.
        self.parser.add_argument(default=self.config.getter_or_default(
                                 typesuffix,
                                 section,
                                 key,
                                 default),
                                 *args, **kwargs)
