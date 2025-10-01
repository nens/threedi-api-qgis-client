History
=======

3.28 (unreleased)
-----------------

- Nothing changed yet.


3.27 (2025-10-01)
-----------------

- Bumped dependency loader.


3.26 (2025-09-08)
-----------------

- Bumped dependency loader.


3.25 (2025-08-28)
-----------------

- Re-released 3.24


3.24 (2025-08-28)
-----------------

- Bugfix: Allow multiple polygons per substance in the "Simulate with rain zones" processing algorithm
- Prevent N&S Dependency Loader from getting disabled (nens/nens-dependency-loader#19)


3.23 (2025-07-16)
-----------------

- Bump Dependency Loader plugin version to 1.2.1 (nens/nens-dependency-loader#14)


3.22 (2025-06-17)
-----------------

- Fix incorrect filtering and project id retrieval in simulation results.


3.21 (2025-06-16)
-----------------

- Use custom sorting for expiration days in finished simulation results. (#668)
- Added external progress bar option to load_remote_schematisation (nens/rana#1745)


3.20 (2025-06-10)
-----------------

- Add beta processing algorithm *Simulate with rain zones* (#682)
- Add beta processing algorithm *Simulate with DWF labelling* (#683)
- Use separate enum for wind events with "Custom" instead of "From CSV".
- Allow more decimals in wind drag coefficient setting.


3.19 (2025-05-12)
-----------------

- Bumped dependency loader
- Bugfix: correctly set *Calculation point distance 1D* in new schematisations


3.18 (2025-05-07)
-----------------

- Show upgrade warnings in popup and log
- Add additional check to deal with legacy gpkgs created by schematisation editor.
- New schematisation from existing file - move migration logic to after users have clicked Create schematisation (#671)
- Fix upgrading of schematisation before uploading


3.17 (2025-04-02)
-----------------

- Bumped threedi_mi_utils to 0.1.10.


3.16 (2025-04-01)
-----------------

- Adjusting plugin to work with schema version >= 300.
- Fixed schematisation tag setting (#640)
- Simulation wizard: Add water quality settings to settings page (#604)
- Remove "migrate after download" functionality (#666)

3.15.2 (2025-01-10)
-------------------

- Lateral time steps are wrongly converted when adding substance to laterals from template (#639)


3.15.1 (2024-12-12)
-------------------

- Empty list of tags is now properly transfered to backend.


3.15 (2024-11-12)
-----------------

- Load remote schematisation: #626
- Fixes/enhancements: #616, #622
- Setting 1D initial substance concentration (#609)
- Added check for non-ascii characters in substance unit (#621)
- Added user feedback for invalid boundary conditions file. (#624)
- Added substance concentration section in Precipation page. (#537)
- Added diffusion parameter to Substances page. (#602)
- Added option to select previously uploaded 1D initial water level file. (#610)
- Added water quality license GUI restrictions (#625)
- Simulation template name should only be postfixed when multiple simulations are started (#635)


3.14.1 (2024-09-25)
-------------------

- Fix for the 'simulation_user_first_name' KeyError.
- Add new 1D advection options


3.14.0 (2024-09-24)
-------------------

- Fixes/enhancements: #368, #440


3.13.0 (2024-09-12)
-------------------

- Fixes/enhancements: #276, #449, #551.
- Fix error when trying to start a simulation with laterals (#589).
- Updated pyqtgraph to version 0.13.7
- Model selection: fixed bug (numeric and date columns were sorted lexicographically) (#587)
- Simulation template creation: append prefix to saved template name in case of Multiple Simulations (#613)
- GUI: Load parameters from template: not loading substance decay coefficient (#612)
- GUI: Add substance concentrations section to Precipitation page (#537)


3.12.0 (2024-07-17)
-------------------

- Add CSV upload support for 1D initial water level (#575).
- Add initial concentrations to initial conditions page (#580).
- Convert timesteps to correct time units (#585).
- Fixes/enhancements: #238, #391, #480, #493, #496, #526.


3.11.0 (2024-06-21)
-------------------

- Added decay coefficients to substances table (#574).
- Added computational grid checks before an upload (#429).
- Added handling of the 'started_from' Simulation parameter (#556).
- Updated threedi-api-client version to 4.1.7.
- Added simulation name sanitization (#497).
- Changed simulation results directory name (#530).


3.10.2 (2024-06-05)
-------------------

- Add substance concentrations to Boundary Conditions page (#559).
- Use column names i/o column orderings to read CSV uploaded files (#563).
- Add substance concentrations to Laterals page (#553, #557).
- Add substances page to the simulation wizard (#548, #554).
- Simulation wizard: Improve laterals page (#545).
- Improvements for Upload wizard (#541).
- Updated threedi-api-client version to 4.1.6.
- Updated threedi-schema version to 0.219.3.
- Applied models sorting by their revision as an integer (#564).

3.10 (2024-04-12)
-----------------

- Fixes/enhancements: #107, #503, #510, #517
- Fixes/enhancements: #527
- Fixed widget focus for the simulation model selection window.

3.9.1 (2024-03-14)
------------------

- Fixes/enhancements: #528, #533

3.9 (2024-01-16)
----------------

- Fixes/enhancements: #465, #491

3.8 (2024-01-11)
----------------

- Fixes/enhancements: #107, #503, #510, #523


3.7.0 (2023-11-14)
------------------

- Moved handling of the 3Di working directory structure to threedi_mi_utils module.
- Fixes/enhancements: #504, #512


3.6.2 (2023-10-24)
------------------

- Fixes/enhancements: #505


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
