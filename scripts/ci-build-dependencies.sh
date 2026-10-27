#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Shared dependencies for staging tools and the firmware build.
set -euo pipefail

sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc
sudo apt-get clean
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  asciidoc autoconf automake autopoint binutils bison build-essential \
  bzip2 ccache clang cmake cpio curl device-tree-compiler flex gawk \
  gettext git g++-multilib gcc-multilib gperf help2man intltool jq \
  libelf-dev libglib2.0-dev libgmp3-dev libltdl-dev libmpc-dev \
  libmpfr-dev libncurses-dev libpython3-dev libreadline-dev libssl-dev \
  libtool libyaml-dev lld llvm ninja-build p7zip-full patch pkgconf \
  python3 python3-docutils python3-pip python3-ply python3-pyelftools \
  qemu-utils re2c rsync scons squashfs-tools subversion swig texinfo \
  uglifyjs unzip wget xmlto xxd zlib1g-dev zstd
