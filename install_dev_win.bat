SET DIR=%cd%
SET PLUGIN=threedi_models_and_simulations
SET SRC=%DIR%\threedi_models_and_simulations
SET DEST=%UserProfile%\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins
SET DEST_PLUGIN=%DEST%\%PLUGIN%
rd %DEST_PLUGIN% /s /q
xcopy %SRC% %DEST_PLUGIN% /s/i/h/e/k/f/c
