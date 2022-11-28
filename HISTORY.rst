History
=======

3.3 (unreleased)
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
