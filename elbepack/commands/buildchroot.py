#!/usr/bin/env python
#
# ELBE - Debian Based Embedded Rootfilesystem Builder
# Copyright (C) 2013  Linutronix GmbH
#
# This file is part of ELBE.
#
# ELBE is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ELBE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ELBE.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function

from optparse import OptionParser
import sys

from elbepack.shellhelper import CommandError
from elbepack.elbeproject import ElbeProject
from elbepack.elbexml import ValidationError
from elbepack.db import ElbeDB
from elbepack.cdroms import CDROM_SIZE
from sqlalchemy.exc import OperationalError


def run_command( argv ):
    oparser = OptionParser(usage="usage: %prog buildchroot [options] <xmlfile>")

    oparser.add_option( "-t", "--target", dest="target",
                        help="directoryname of target" )

    oparser.add_option( "-o", "--output", dest="output",
                        help="name of logfile" )

    oparser.add_option( "-n", "--name", dest="name",
                        help="name of the project (included in the report)" )

    oparser.add_option( "--skip-pbuild", action="store_true",
                        dest="skip_pbuild", default=False,
                        help="skip building packages from <pbuilder> list" )

    oparser.add_option( "--build-bin", action="store_true",
                        dest="build_bin", default=False,
                        help="Build Binary Repository CDROM, for exact Reproduction" )

    oparser.add_option( "--build-sources", action="store_true",
                        dest="build_sources", default=False,
                        help="Build Source CD" )

    oparser.add_option( "--proxy", dest="proxy",
                        help="Override the http proxy" )

    oparser.add_option( "--debug", action="store_true", dest="debug",
                        default=False,
                        help="Enable various features to debug the build" )

    oparser.add_option( "--buildtype", dest="buildtype",
                        help="Override the buildtype" )

    oparser.add_option( "--cdrom-size", action="store",
                        dest="cdrom_size", default=CDROM_SIZE, help="ISO CD size in MB" )

    oparser.add_option( "--skip-validation", action="store_true",
                        dest="skip_validation", default=False,
                        help="Skip xml schema validation" )

    oparser.add_option( "--skip-debootstrap", action="store_true",
                        dest="skip_debootstrap", default=False,
                        help="Skip debootstrap" )

    oparser.add_option( "--skip-pkglist", action="store_true",
                        dest="skip_pkglist", default=False,
                        help="ignore changes of the package list" )

    oparser.add_option( "--skip-cdrom", action="store_true",
                        dest="skip_cdrom", default=False,
                        help="(now obsolete) Skip cdrom iso generation" )

    (opt,args) = oparser.parse_args(argv)

    if len(args) != 1:
        print("wrong number of arguments")
        oparser.print_help()
        sys.exit(20)

    if not opt.target:
        print("No target specified")
        sys.exit(20)

    if opt.skip_cdrom:
        print("WARNING: Skip CDROMS is now the default, use --build-bin to build binary CDROM")

    try:
        project = ElbeProject( opt.target, args[0], opt.output, opt.name,
                opt.buildtype, opt.skip_validation )
    except ValidationError as e:
        print((str(e)))
        print("xml validation failed. Bailing out")
        sys.exit(20)

    try:
        project.build( opt.skip_debootstrap, opt.build_bin,
                opt.build_sources, opt.cdrom_size, opt.debug, opt.skip_pkglist,
                opt.skip_pbuild )
    except CommandError as ce:
        print(("command in project build failed: %s" % ce.cmd))
        sys.exit(20)

    try:
        db = ElbeDB()
        db.save_project (project)
    except OperationalError:
        print("failed to save project in database")
        sys.exit(20)
