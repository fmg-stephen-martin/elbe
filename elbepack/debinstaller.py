# ELBE - Debian Based Embedded Rootfilesystem Builder
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2018 Linutronix GmbH

import os
import re
import sys
from shutil import copyfile
from urllib.request import urlopen

from elbepack.egpg import OverallStatus, check_signature
from elbepack.filesystem import TmpdirFilesystem
from elbepack.hashes import HashValidationFailed, HashValidator
from elbepack.shellhelper import CommandError, system

from gpg import core
from gpg.constants import PROTOCOL_OpenPGP


class InvalidSignature(Exception):
    pass


class NoKinitrdException(Exception):
    pass


class ReleaseFile(HashValidator):
    def __init__(self, base_url, fname, fname_list):

        HashValidator.__init__(self, base_url)

        header_re = re.compile(r'(\w+):(.*)')
        hash_re = re.compile(r' ([0-9a-f]+)\s+([0-9]+)\s+(\S+)')
        current_header = ''

        with open(fname, 'r') as fp:
            for lic in fp.readlines():
                m = header_re.match(lic)
                if m:
                    # line contains an rfc822 Header,
                    # remember it.
                    current_header = m.group(1)
                    continue

                m = hash_re.match(lic)
                if m:
                    # line contains a hash entry.
                    # check filename, whether we are interested in it
                    if m.group(3) in fname_list:
                        self.insert_fname_hash(current_header,
                                               m.group(3),
                                               m.group(1))


class SHA256SUMSFile(HashValidator):
    def __init__(self, base_url, fname, fname_list):

        HashValidator.__init__(self, base_url)

        hash_re = re.compile(r'([0-9a-f]+)\s+(\S+)')

        with open(fname, 'r') as fp:
            for lic in fp.readlines():
                m = hash_re.match(lic)
                if m:
                    # line contains a hash entry.
                    # check filename, whether we are interested in it
                    if m.group(2) in fname_list:
                        self.insert_fname_hash('SHA256',
                                               m.group(2),
                                               m.group(1))


def setup_apt_keyring(gpg_home, keyring_fname):
    ring_path = os.path.join(gpg_home, keyring_fname)
    if not os.path.isdir('/etc/apt/trusted.gpg.d'):
        print("/etc/apt/trusted.gpg.d doesn't exist")
        print('apt-get install debian-archive-keyring may '
              'fix this problem')
        sys.exit(115)

    if os.path.exists('/etc/apt/trusted.gpg'):
        system(f'cp /etc/apt/trusted.gpg "{ring_path}"')

    gpg_options = f'--keyring "{ring_path}" --no-auto-check-trustdb ' \
                  '--trust-model always --no-default-keyring ' \
                  '--batch ' \
                  f'--homedir "{gpg_home}"'

    trustkeys = os.listdir('/etc/apt/trusted.gpg.d')
    for key in trustkeys:
        print(f'Import {key}: ')
        try:
            system(
                f'gpg {gpg_options} '
                f'--import "{os.path.join("/etc/apt/trusted.gpg.d", key)}"')
        except CommandError:
            print(f'adding keyring "{key}" to keyring "{ring_path}" failed')


def download(url, local_fname):
    try:
        system(f'wget -O "{local_fname}" "{url}"')
    except CommandError:
        raise NoKinitrdException(f'Failed to download {url}')


def verify_release(tmp, base_url):

    # setup gpg context, for verifying
    # the Release.gpg signature.
    ctx = core.Context()
    ctx.set_engine_info(PROTOCOL_OpenPGP,
                        None,
                        tmp.fname('/'))

    # validate signature.
    # open downloaded plaintext file, and
    # use the urlopen object of the Release.gpg
    # directly.
    sig = urlopen(base_url + 'Release.gpg', None, 10)
    try:
        with tmp.open('Release', 'r') as signed:

            overall_status = OverallStatus()

            # verify detached signature
            det_sign = core.Data(sig.read())
            signed_data = core.Data(signed.read())
            ctx.op_verify(det_sign, signed_data, None)
            vres = ctx.op_verify_result()

            for s in vres.signatures:
                status = check_signature(ctx, s)
                overall_status.add(status)

            if overall_status.to_exitcode():
                raise InvalidSignature('Failed to verify Release file')

    finally:
        sig.close()


def download_kinitrd(tmp, suite, mirror, skip_signature=False):
    base_url = f"{mirror.replace('LOCALMACHINE', 'localhost')}/dists/{suite}/"
    installer_path = 'main/installer-amd64/current/images/'

    setup_apt_keyring(tmp.fname('/'), 'pubring.gpg')

    # download release file
    download(base_url + 'Release', tmp.fname('Release'))
    if not skip_signature:
        verify_release(tmp, base_url)

    # parse Release file, and remember hashvalues
    # we are interested in
    interesting = [installer_path + 'SHA256SUMS']
    release_file = ReleaseFile(base_url, tmp.fname('Release'), interesting)

    # now download and validate SHA256SUMS
    release_file.download_and_validate_file(
            installer_path + 'SHA256SUMS',
            tmp.fname('SHA256SUMS'))

    # now we have a valid SHA256SUMS file
    # parse it
    interesting = ['./cdrom/initrd.gz',
                   './cdrom/vmlinuz',
                   './netboot/debian-installer/amd64/initrd.gz',
                   './netboot/debian-installer/amd64/linux']
    sha256_sums = SHA256SUMSFile(
            base_url + installer_path,
            tmp.fname('SHA256SUMS'),
            interesting)

    # and then download the files we actually want
    for p, ln in zip(interesting, ['initrd-cdrom.gz',
                                   'linux-cdrom',
                                   'initrd.gz',
                                   'vmlinuz']):
        sha256_sums.download_and_validate_file(
                p,
                tmp.fname(ln))


def get_primary_mirror(prj):
    if prj.has('mirror/primary_host'):
        m = prj.node('mirror')

        mirror = m.text('primary_proto') + '://'
        mirror += (
            f"{m.text('primary_host')}/{m.text('primary_path')}"
            .replace('//', '/'))
    else:
        raise NoKinitrdException('Broken xml file: '
                                 'no cdrom and no primary host')

    return mirror


def copy_kinitrd(prj, target_dir):

    suite = prj.text('suite')

    try:
        tmp = TmpdirFilesystem()
        if prj.has('mirror/cdrom'):
            system(
                f'7z x -o{tmp.fname("/")} "{prj.text("mirror/cdrom")}" '
                'initrd-cdrom.gz vmlinuz')

            # initrd.gz needs to be cdrom version !
            copyfile(tmp.fname('initrd-cdrom.gz'),
                     os.path.join(target_dir, 'initrd.gz'))
        else:
            mirror = get_primary_mirror(prj)
            download_kinitrd(tmp, suite, mirror, prj.has('noauth'))

            copyfile(tmp.fname('initrd.gz'),
                     os.path.join(target_dir, 'initrd.gz'))

        copyfile(tmp.fname('initrd-cdrom.gz'),
                 os.path.join(target_dir, 'initrd-cdrom.gz'))

        copyfile(tmp.fname('vmlinuz'),
                 os.path.join(target_dir, 'vmlinuz'))

    except IOError as e:
        raise NoKinitrdException(f'IoError {e}')
    except InvalidSignature as e:
        raise NoKinitrdException(f'InvalidSignature {e}')
    except HashValidationFailed as e:
        raise NoKinitrdException(f'HashValidationFailed {e}')
