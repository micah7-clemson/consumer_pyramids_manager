#!/bin/bash
rm -rf build dist && pyinstaller build_mac.spec
7z a CPM.7z "./dist/Consumer Pyramids Manager.app"