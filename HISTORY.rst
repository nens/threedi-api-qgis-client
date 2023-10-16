History
=======

3.6.1 (2023-10-16)
------------------

- Overviews GUI improvements.
- Updated threedi-api-client version to 4.1.4.
- Updated threedi-modelchecker version to 2.4.0.
- Updated threedi-schema version to 0.217.11.
- Fixed issues: #439, #498.


3.6.0 (2023-09-21)
------------------

- Fixed issues #474, #481, #483, #484.
- Implemented #263, #452, #473.


3.5.2 (2023-06-30)
------------------

-  Fix for the issue #478.


3.5.1 (2023-06-23)
------------------

- Fix for the issue #470.


3.5.0 (2023-06-16)
------------------

- Added handling of multiple boundary conditions with the same ID. (#468)
- Compatibility with schema 217 (#462).
- Added handling of the Vegetation drag settings rasters. (#460)
- Fixed issue #461


3.4.5 (2023-04-26)
------------------

- Compatibility with schema 216 (#451).
- Improved simulation progress tracking to avoid request throttling (#408).

3.4.4 (2023-04-11)
------------------

- Fixed issue #447
- Fixed issue #454
- Added downloading gridadmin file in the GeoPackage format #438

3.4.3 (2023-03-10)
------------------

- Fixed issue #409
- Sorted imports


3.4.2 (2023-02-08)
------------------

- Release number fix.


3.4.1 (2023-02-08)
------------------

- Fix for the running simulation with basic post-processing only.


3.4 (2023-02-06)
----------------

- Simulation wizard runner refactoring (#407)
- Added handling of the models limits per organisation. (#410)
- Fix for the issue #416.
- Changed friction velocity default value.
- Model deletion fixes.
- Updated threedi-api-client version to 4.1.1
- Structure controls handling (#427)
- Changed the way of showing progress of the simulation wizard. (#424)
- Increased default upload timeout to the 900 seconds.
- Fix for the issue #428.
- Added boundary conditions wizard page. (#430)
- Refactoring new simulation init options dialog. (#431)
- Moved post-processing in Lizard to the separate simulation wizard page. (#432)
- Fix for the issue #418. (#436)
- Updated schematisation checker to version 1.0.0 and removed raster checker section (#413)
- Added handling (partial) additional forcing options from the simulation template.


3.3 (2022-11-28)
----------------

- Local init water level (#388).
- Added discharge coefficients and max breach depth to the breach tab.
- Fix for the issue #385, #402, #403. (#404)
- Breaches simulation tab fixes.
- Initial conditions simulation tab fixes.
- Breaches tab labels font size change.
- Fixed an initial water level raster names in the simulation wizard combobox.
- Fixed breach label font size.
- Default max breach depth fix.
- Fixed setting correct 'max_breach_depth' value from template.
- Compatibility with schema 208 (#401).
- Use constant for max_angle_1d_advection.
- Workaround for the issue #153.
- Stopped loading the "cells" layer to the map canvas during running simulation.
- Updated minimal schema version to 209.


3.2 (2022-07-08)
----------------

- Simplified schema migration workflow.
- Improved authorization.


3.1 (2022-06-14)
----------------

- Prepared for release.


3.0.3 (2022-03-10)
------------------

- Added threedi-api-client compatibility check.

- Server workers fix.


3.0.2 (2022-02-15)
------------------

- Added some missing files.


3.0.1 (2022-02-15)
------------------

- Release fix, the plugin directory is now also named
  `threedi_models_and_simulations`.


3.0.0 (2022-02-15)
------------------

- Renamed to "3di models and simulations", but only as plugin name. The
  plugin directory is still `threedi_models_and_simulations`.


2.5.0 (2021-09-01)
------------------

- Added Dry Weather Flow when running a simulation
- Support for tags when adding a simulation
- Specify initial 2D waterlevels (Mean, mix, max dropdown)
- Added the possibility to upload lateral files
- Added interpolate flag to time series
- Added the possibility to upload netcdf file for rainfall
- Model search is now case insensitive
- Simplified breach selection
- Add wind to a simulation
- Accept different time-units for laterals
- Various Bugfixes


2.4.1 (2021-05-21)
------------------

- Fixed throttling issue when you had access to lots of repositories.


2.4.0 (2021-03-04)
------------------

- Unknown.


0.1.0 (2020-02-20)
------------------

- First release.
