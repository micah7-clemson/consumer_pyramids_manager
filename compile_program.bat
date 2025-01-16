@echo off
rmdir /s /q build dist
pyinstaller build_windows.spec
7z a CPM_W11.7z ".\dist\ConsumerPyramidsManager.exe"