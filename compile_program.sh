#!/bin/bash
rm -rf build dist && pyinstaller build.spec
#7z a CPM.7z "./dist/Consumer Pyramids Manager.app"