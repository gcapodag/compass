.. _landice_ensemble_generator:

ensemble_generator
==================

The ``landice/ensemble_generator`` test group creates ensemble of MALI
simulations with different parameter values.  The ensemble framework
sets up a user-defined number of simulations with parameter values selected
from a space-filling Sobol sequence.

A test case in this test group consists of a number of ensemble members,
and one ensemble manager.
Each ensemble member is a step of the test case, and can be run separately
or as part of the complete ensemble.  Ensemble members are identified by a
three digit run number, starting with 000.
A config file specifies the run numbers to set up, as well as some common
information about the run configuration.

The test case can be generated multiple times to set up and run additional
runs with a different range of run numbers after being run initially. This
allows one to perform a small ensemble (e.g. 2-10 runs) to make sure results
look as expected before spending time on a larger ensemble. This also allows
one to add more ensemble members from the Sobol sequence later if UQ analysis
indicates the original sample size was insufficient.

Individual test cases will define which parameters are being sampled and
over what ranges.  Currently these parameters are supported:

* basal friction power law exponent

* von Mises threshold stress for calving

* calving rate speed limit

* gamma0 melt sensitivity parameter in ISMIP6-AIS ice-shelf basal melting
  parameterization

* deltaT thermal forcing bias adjustment parameter in ISMIP6-AIS ice-shelf
  basal melting parameterization

Additional parameters can be easily added in the future.
The test group currently includes a file of unit parameter values for two
parameters with 100 samples using a Sobol sequence.  The parameter
dimensionality or sample size can be increased by modifying this file and
its usage.  It also would be possible to modify the sampling strategy to
perform uniform parameter sensitivity tests.

``compass setup`` will set up the simulations and the ensemble manager.
``compass run`` from the test case work directory will submit each run as a
separate slurm job.
Individual runs can be run independently through ``compass run`` executed in the
run directory.  (E.g., if you want to test or debug a run without running the
entire ensemble.)

.. note::

   Due to the requirement that ``compass run`` is only executed
   on a compute node, this operation has to be submitted via a batch script or
   interactive job, or compass framework code can be modified by an expert user
   to lift this restriction. (This may be addressed in the future.) 

Simulation output can be analyzed with the ``plot_ensemble.py`` visualization
script, which generates plots of basic quantities of interest as a function
of parameter values, as well as identifies runs that did not reach the
target year.

Future improvements may include:

* enabling the ensemble manager to identify runs that need to be restarted
  so the restarts do not need to be managed manually

* safety checks or warnings before submitting ensembles that will use large
  amounts of computing resources

* more flexibility in customizing ensembles without needing to modify test
  case files

The test group includes a single test case that creates an ensemble of Thwaites
Glacier simulations.

config options
--------------
Test cases in this test group have the following common config options.

A config file specifies the location of the input file, the basal friction
exponent used in the input file, the name of the parameter vector file to
use, and the start and end run numbers to set up.
This test group is intended for expert users, and it is expected that it
will typically be run with a customized cfg file.  Note the default run
numbers create a small ensemble, but uncertainty quantification applications
will typically need dozens or more simulations.


The test-case-specific config options are:

.. code-block:: cfg

   # config options for setting up an ensemble
   [ensemble]

   # start and end numbers for runs to set up and run
   # Additional runs can be added and run to an existing ensemble
   # without affecting existing runs, but trying to set up a run
   # that already exists may result in unexpected behavior.
   # Run numbers should be zero-based
   # These values do not affect viz/analysis, which will include any
   # runs it finds.
   start_run = 0
   end_run = 3

   # the name of the parameter vector file to use, included in the
   # compass repository.  Currently there is only one option, but additional
   # parameter vectors may be added in the future, or entirely replaced with
   # code to generate parameter vectors as needed.
   param_vector_filename = Sobol_Initializations_seed_4_samples_100.csv

   # Path to the initial condition input file.
   # User has to supply.
   # Eventually this could be hard-coded to use files on the input data
   # server, but initially we want flexibility to experiment with different
   # inputs and forcings
   input_file_path = /global/cfs/cdirs/fanssie/MALI_projects/Thwaites_UQ/Thwaites_4to20km_r02_20230126/relaxation/Thwaites_4to20km_r02_20230126_withStiffness_10yrRelax.nc

   # the value of the friction exponent used for the calculation of muFriction
   # in the input file
   orig_fric_exp = 0.2

   # Path to ISMIP6 ice-shelf basal melt parameter input file.
   # User has to supply.
   basal_melt_param_file_path = /global/cfs/cdirs/fanssie/MALI_projects/Thwaites_UQ/Thwaites_4to20km_r02_20230126/forcing/basal_melt/parameterizations/Thwaites_4to20km_r02_20230126_basin_and_coeff_gamma0_DeltaT_quadratic_non_local_median.nc

   # number of tasks that each ensemble member should be run with
   # Eventually, compass could determine this, but we want explicit control for now
   # ntasks=32 for cori
   ntasks = 32

A user should copy the default config file to a user-defined config file
before setting up the test case and any necessary adjustments made.
Importantly, the user-defined config should be modified
to also include the following options that will be used for submitting the
jobs for each ensemble member.

.. code-block:: cfg

   [parallel]
   account = ALLOCATION_NAME_HERE
   qos = regular

   [job]
   wall_time = 1:30:00

thwaites
--------

``landice/ensemble_generator/thwaites`` uses the ensemble framework to create
and ensemble of 4 km resolution Thwaites Glacier simulations integrated from
2000 to 2100 with two parameters varying:

* basal friction power law exponent: range [0.1, 0.333]

* von Mises threshold stress for calving: range [100, 300] kPa

The initial condition file is specified in the ``ensemble_generator.cfg`` file
or a user modification of it.  The forcing files for the simulation are
hard-coded in the test case streams file  and are located on the NERSC
filesystem.  
The model configuration uses:

* first-order velocity solver

* power law basal friction

* evolving temperature

* von Mises calving

* ISMIP6 surface mass balance and sub-ice-shelf melting using climatological
  mean forcing

Steps for setting up and running a Thwaites ensmble
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. With a compass conda environment set up, run, e.g.,
   ``compass setup -t landice/ensemble_generator/thwaites_ensemble -w WORK_DIR_PATH -f USER.cfg``
   where ``WORK_DIR_PATH`` is a location that can store the whole
   ensemble (typically a scratch drive) and ``USER.cfg`` is the
   user-defined config described in the previous section that includes
   options for ``[parallel]`` and ``[job]``, as well as any required
   modifications to the ``[ensemble]`` section.  Likely, the only changes
   one would need to make to the ``[ensemble]`` section are the
   ``start_run`` and ``end_run`` values.

2. After ``compass setup`` completes and all runs are set up, go to the
   ``WORK_DIR_PATH`` and change to the
   ``landice/ensemble_generator/thwaites-uq`` subdirectory.
   From there you will see subdirectories for each run, a subdirectory for the
   ``ensemble_manager`` and symlink to the visualization script.

3. To submit jobs for the entire ensemble, change to the ``ensemble_manager``
   subdirectory and execute ``compass run``.  Note, as stated above, this
   currently will fail on a login node and has to be performed from a
   interactive job or batch script.  This will be addressed in the future.

4. Each run will have its own batch job that can be monitored with ``squeue``
   or similar commands.

5. When the ensemble has completed, you can assess the result through the
   basic visualization script ``plot_ensemble.py``.  The script will skip runs
   that are incomplete or failed, so you can run it while an ensemble is
   still running to assess progress.

6. If you want to add additional ensemble members, adjust
   ``start_run`` and ``end_run`` in your config file and redo steps 1-5.
   The ensemble_manager will always be set to run the most recent run
   numbers defined in the config when ``compass setup`` was run.
   The visualization script is independent of the run manager and will
   process all runs it finds.

It is also possible to run an individual run manually by changing to the run
directory and submitting the job script yourself with ``sbatch``.
