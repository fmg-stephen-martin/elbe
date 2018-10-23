# ELBE - Debian Based Embedded Rootfilesystem Builder
# Copyright (c) 2017 Torben Hohn <torben.hohn@linutronix.de>
# Copyright (c) 2017 Manuel Traut <manut@linutronix.de>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from shutil import copyfile

from npyscreen import TitleText

from elbepack.directories import mako_template_dir
from elbepack.debianize.base import DebianizeBase, template


class BareBox (DebianizeBase):

    # pylint: disable=too-many-ancestors

    name = "barebox"
    files = ['Kbuild', 'Kconfig', 'README', 'TODO']

    def __init__(self):
        self.defconfig = None
        self.imgname = None
        self.cross = None
        self.k_version = None

        DebianizeBase.__init__(self)

    def gui(self):
        self.defconfig = self.add_widget_intelligent(
            TitleText, name="defconfig:", value="imx_v7_defconfig")

        self.imgname = self.add_widget_intelligent(
            TitleText,
            name="Imagename:",
            value="barebox-phytec-phycore-imx6dl-som-nand-256mb.img")

        self.cross = self.add_widget_intelligent(
            TitleText, name="CROSS_COMPILE:", value="arm-linux-gnueabihf-")

        self.k_version = self.add_widget_intelligent(
            TitleText, name="BareboxVersion:", value="2016.10")

    def debianize(self):
        self.deb['k_arch'] = self.get_k_arch()

        self.deb['defconfig'] = self.defconfig.get_value()
        self.deb['cross_compile'] = self.cross.get_value()
        self.deb['k_version'] = self.k_version.get_value()
        self.deb['imgname'] = self.imgname.get_value()

        self.tmpl_dir = os.path.join(mako_template_dir, 'debianize/barebox')
        pkg_name = self.deb['p_name'] + '-' + self.deb['k_version']

        for tmpl in ['control', 'rules']:
            with open(os.path.join('debian/', tmpl), 'w') as f:
                mako = os.path.join(self.tmpl_dir, tmpl + '.mako')
                f.write(template(mako, self.deb))

        cmd = 'dch --package barebox-' + pkg_name + \
            ' -v ' + self.deb['p_version'] + \
            ' --create -M -D ' + self.deb['release'] + \
            ' "generated by elbe debianize"'
        os.system(cmd)

        copyfile(os.path.join(self.tmpl_dir, 'barebox-image.install'),
                 'debian/barebox-image-' + pkg_name + '.install')
        copyfile(os.path.join(self.tmpl_dir, 'barebox-tools.install'),
                 'debian/barebox-tools-' + pkg_name + '.install')

        self.hint = "use 'dpkg-buildpackage -a%s' to build the package" % (
                self.deb['p_arch'])


DebianizeBase.register(BareBox)
