import os

import mpas_tools.io
import xarray
from geometric_features import (
    FeatureCollection,
    GeometricFeatures,
    read_feature_collection,
)
from mpas_tools.io import write_netcdf
from mpas_tools.logging import LoggingContext, check_call
from mpas_tools.mesh.conversion import cull
from mpas_tools.mesh.mask import compute_mpas_flood_fill_mask
from mpas_tools.ocean import inject_bathymetry
from mpas_tools.ocean.coastline_alteration import (
    add_critical_land_blockages,
    add_land_locked_cells_to_mask,
    widen_transect_edge_masks,
)
from mpas_tools.viz.paraview_extractor import extract_vtk

from compass.step import Step


class CullMeshStep(Step):
    """
    A step for culling a global MPAS-Ocean mesh

    Attributes
    ----------
    base_mesh_step : compass.mesh.spherical.SphericalBaseStep
        The base mesh step containing input files to this step

    with_ice_shelf_cavities : bool
        Whether the mesh includes ice-shelf cavities

    do_inject_bathymetry : bool
        Whether to interpolate bathymetry from a data file so it
        can be used as a culling criteria

    preserve_floodplain : bool
        Whether to leave land cells in the mesh based on bathymetry
        specified by do_inject_bathymetry
    """

    def __init__(self, test_case, base_mesh_step, with_ice_shelf_cavities,
                 name='cull_mesh', subdir=None, do_inject_bathymetry=False,
                 preserve_floodplain=False):
        """
        Create a new step

        Parameters
        ----------
        test_case : compass.ocean.tests.global_ocean.mesh.Mesh
            The test case this step belongs to

        base_mesh_step : compass.mesh.spherical.SphericalBaseStep
            The base mesh step containing input files to this step

        with_ice_shelf_cavities : bool
            Whether the mesh includes ice-shelf cavities

        name : str, optional
            the name of the step

        subdir : str, optional
            the subdirectory for the step.  The default is ``name``

        do_inject_bathymetry : bool, optional
            Whether to interpolate bathymetry from a data file so it
            can be used as a culling criteria

        preserve_floodplain : bool, optional
            Whether to leave land cells in the mesh based on bathymetry
            specified by do_inject_bathymetry
        """
        super().__init__(test_case, name=name, subdir=subdir,
                         cpus_per_task=None, min_cpus_per_task=None)
        self.base_mesh_step = base_mesh_step

        for file in ['culled_mesh.nc', 'culled_graph.info',
                     'critical_passages_mask_final.nc']:
            self.add_output_file(filename=file)

        if with_ice_shelf_cavities:
            self.add_output_file(filename='land_ice_mask.nc')

        self.with_ice_shelf_cavities = with_ice_shelf_cavities
        self.do_inject_bathymetry = do_inject_bathymetry
        self.preserve_floodplain = preserve_floodplain

    def setup(self):
        """
        Set up the test case in the work directory, including downloading any
        dependencies.
        """
        super().setup()
        if self.do_inject_bathymetry:
            self.add_input_file(
                filename='earth_relief_15s.nc',
                target='SRTM15_plus_earth_relief_15s.nc',
                database='bathymetry_database')

        # get the these properties from the config options
        config = self.config
        # todo: move to constrain_resources()
        self.cpus_per_task = config.getint('spherical_mesh',
                                           'cull_mesh_cpus_per_task')
        self.min_cpus_per_task = config.getint('spherical_mesh',
                                               'cull_mesh_min_cpus_per_task')

        base_path = self.base_mesh_step.path
        base_filename = self.base_mesh_step.config.get(
            'spherical_mesh', 'mpas_mesh_filename')
        target = os.path.join(base_path, base_filename)
        self.add_input_file(filename='base_mesh.nc', work_dir_target=target)

    def run(self):
        """
        Run this step of the test case
        """
        with_ice_shelf_cavities = self.with_ice_shelf_cavities
        logger = self.logger

        # only use progress bars if we're not writing to a log file
        use_progress_bar = self.log_filename is None

        do_inject_bathymetry = self.do_inject_bathymetry
        preserve_floodplain = self.preserve_floodplain

        cull_mesh(with_critical_passages=True, logger=logger,
                  use_progress_bar=use_progress_bar,
                  preserve_floodplain=preserve_floodplain,
                  with_cavities=with_ice_shelf_cavities,
                  process_count=self.cpus_per_task)

        if do_inject_bathymetry:
            inject_bathymetry(mesh_file='culled_mesh.nc')


def cull_mesh(with_cavities=False, with_critical_passages=False,
              custom_critical_passages=None, custom_land_blockages=None,
              preserve_floodplain=False, logger=None, use_progress_bar=True,
              process_count=1):
    """
    First step of initializing the global ocean:

      1. combining Natural Earth land coverage north of 60S with Antarctic
         ice coverage or grounded ice coverage from BedMachineAntarctica

      2. combining transects defining critical passages (if
         ``with_critical_passages=True``)

      3. combining points used to seed a flood fill of the global ocean.

      4. create masks from land coverage

      5. add land-locked cells to land coverage mask.

      6. create masks from transects (if
         ``with_critical_passages=True``)

      7. cull cells based on land coverage but with transects present

      8. create flood-fill mask based on seeds

      9. cull cells based on flood-fill mask

      10. create masks from transects on the final culled mesh (if
          ``with_critical_passages=True``)

    Parameters
    ----------
    with_cavities : bool, optional
        Whether the mesh should include Antarctic ice-shelf cavities from
        BedMachine Antarctica

    with_critical_passages : bool, optional
        Whether the mesh should open the standard critical passages and close
        land blockages from geometric_features

    custom_critical_passages : str, optional
        The name of geojson file with critical passages to open.  This file may
         be supplied in addition to or instead of the default passages
         (``with_critical_passages=True``)

    custom_land_blockages : str, optional
        The name of a geojson file with critical land blockages to close. This
        file may be supplied in addition to or instead of the default blockages
        (``with_critical_passages=True``)

    preserve_floodplain : bool, optional
        Whether to use the ``cellSeedMask`` field in the base mesh to preserve
        a floodplain at elevations above z=0

    logger : logging.Logger, optional
        A logger for the output if not stdout

    use_progress_bar : bool, optional
        Whether to display progress bars (problematic in logging to a file)

    process_count : int, optional
        The number of cores to use to create masks (``None`` to use all
        available cores)
    """
    with LoggingContext(name=__name__, logger=logger) as logger:
        _cull_mesh_with_logging(
            logger, with_cavities, with_critical_passages,
            custom_critical_passages, custom_land_blockages,
            preserve_floodplain, use_progress_bar, process_count)


def _cull_mesh_with_logging(logger, with_cavities, with_critical_passages,
                            custom_critical_passages, custom_land_blockages,
                            preserve_floodplain, use_progress_bar,
                            process_count):
    """ Cull the mesh once the logger is defined for sure """

    critical_passages = with_critical_passages or \
        (custom_critical_passages is not None)

    land_blockages = with_critical_passages or \
        (custom_land_blockages is not None)

    gf = GeometricFeatures()

    # start with the land coverage from Natural Earth
    fcLandCoverage = gf.read(componentName='natural_earth',
                             objectType='region',
                             featureNames=['Land Coverage'])

    # remove the region south of 60S so we can replace it based on ice-sheet
    # topography
    fcSouthMask = gf.read(componentName='ocean', objectType='region',
                          featureNames=['Global Ocean 90S to 60S'])

    fcLandCoverage = fcLandCoverage.difference(fcSouthMask)

    # Add "land" coverage from either the full ice sheet or just the grounded
    # part
    if with_cavities:
        fcAntarcticLand = gf.read(
            componentName='bedmachine', objectType='region',
            featureNames=['AntarcticGroundedIceCoverage'])
    else:
        fcAntarcticLand = gf.read(
            componentName='bedmachine', objectType='region',
            featureNames=['AntarcticIceCoverage'])

    fcLandCoverage.merge(fcAntarcticLand)

    # save the feature collection to a geojson file
    fcLandCoverage.to_geojson('land_coverage.geojson')

    # these defaults may have been updated from config options -- pass them
    # along to the subprocess
    netcdf_format = mpas_tools.io.default_format
    netcdf_engine = mpas_tools.io.default_engine

    # Create the land mask based on the land coverage, i.e. coastline data
    args = ['compute_mpas_region_masks',
            '-m', 'base_mesh.nc',
            '-g', 'land_coverage.geojson',
            '-o', 'land_mask.nc',
            '-t', 'cell',
            '--process_count', '{}'.format(process_count),
            '--format', netcdf_format,
            '--engine', netcdf_engine]
    check_call(args, logger=logger)

    dsBaseMesh = xarray.open_dataset('base_mesh.nc')
    dsLandMask = xarray.open_dataset('land_mask.nc')
    dsLandMask = add_land_locked_cells_to_mask(dsLandMask, dsBaseMesh,
                                               latitude_threshold=43.0,
                                               nSweeps=20)
    write_netcdf(dsLandMask, 'land_mask_with_land_locked_cells.nc')

    # create seed points for a flood fill of the ocean
    # use all points in the ocean directory, on the assumption that they are,
    # in fact, in the ocean
    fcSeed = gf.read(componentName='ocean', objectType='point',
                     tags=['seed_point'])

    if land_blockages:
        if with_critical_passages:
            # merge transects for critical land blockages into
            # critical_land_blockages.geojson
            fcCritBlockages = gf.read(
                componentName='ocean', objectType='transect',
                tags=['Critical_Land_Blockage'])
        else:
            fcCritBlockages = FeatureCollection()

        if custom_land_blockages is not None:
            fcCritBlockages.merge(read_feature_collection(
                custom_land_blockages))

        # create masks from the transects
        fcCritBlockages.to_geojson('critical_blockages.geojson')
        args = ['compute_mpas_transect_masks',
                '-m', 'base_mesh.nc',
                '-g', 'critical_blockages.geojson',
                '-o', 'critical_blockages.nc',
                '-t', 'cell',
                '-s', '10e3',
                '--process_count', '{}'.format(process_count),
                '--format', netcdf_format,
                '--engine', netcdf_engine]
        check_call(args, logger=logger)
        dsCritBlockMask = xarray.open_dataset('critical_blockages.nc')

        dsLandMask = add_critical_land_blockages(dsLandMask, dsCritBlockMask)

    fcCritPassages = FeatureCollection()
    dsPreserve = []

    if critical_passages:
        if with_critical_passages:
            # merge transects for critical passages into fcCritPassages
            fcCritPassages.merge(gf.read(componentName='ocean',
                                         objectType='transect',
                                         tags=['Critical_Passage']))

        if custom_critical_passages is not None:
            fcCritPassages.merge(read_feature_collection(
                custom_critical_passages))

        # create masks from the transects
        fcCritPassages.to_geojson('critical_passages.geojson')
        args = ['compute_mpas_transect_masks',
                '-m', 'base_mesh.nc',
                '-g', 'critical_passages.geojson',
                '-o', 'critical_passages.nc',
                '-t', 'cell', 'edge',
                '-s', '10e3',
                '--process_count', '{}'.format(process_count),
                '--format', netcdf_format,
                '--engine', netcdf_engine]
        check_call(args, logger=logger)
        dsCritPassMask = xarray.open_dataset('critical_passages.nc')

        # Alter critical passages to be at least two cells wide, to avoid sea
        # ice blockage
        dsCritPassMask = widen_transect_edge_masks(dsCritPassMask, dsBaseMesh,
                                                   latitude_threshold=43.0)

        dsPreserve.append(dsCritPassMask)

    if preserve_floodplain:
        dsPreserve.append(dsBaseMesh)

    # cull the mesh based on the land mask
    dsCulledMesh = cull(dsBaseMesh, dsMask=dsLandMask,
                        dsPreserve=dsPreserve, logger=logger)

    # create a mask for the flood fill seed points
    dsSeedMask = compute_mpas_flood_fill_mask(dsMesh=dsCulledMesh,
                                              fcSeed=fcSeed,
                                              logger=logger)

    # cull the mesh a second time using a flood fill from the seed points
    dsCulledMesh = cull(dsCulledMesh, dsInverse=dsSeedMask,
                        graphInfoFileName='culled_graph.info', logger=logger)
    write_netcdf(dsCulledMesh, 'culled_mesh.nc')

    if critical_passages:
        # make a new version of the critical passages mask on the culled mesh
        fcCritPassages.to_geojson('critical_passages.geojson')
        args = ['compute_mpas_transect_masks',
                '-m', 'culled_mesh.nc',
                '-g', 'critical_passages.geojson',
                '-o', 'critical_passages_mask_final.nc',
                '-t', 'cell',
                '-s', '10e3',
                '--process_count', '{}'.format(process_count),
                '--format', netcdf_format,
                '--engine', netcdf_engine]
        check_call(args, logger=logger)

    if with_cavities:
        fcAntarcticIce = gf.read(
            componentName='bedmachine', objectType='region',
            featureNames=['AntarcticIceCoverage'])

        fcAntarcticIce.to_geojson('ice_coverage.geojson')
        args = ['compute_mpas_region_masks',
                '-m', 'culled_mesh.nc',
                '-g', 'ice_coverage.geojson',
                '-o', 'ice_coverage.nc',
                '-t', 'cell',
                '--process_count', '{}'.format(process_count),
                '--format', netcdf_format,
                '--engine', netcdf_engine]
        check_call(args, logger=logger)
        dsMask = xarray.open_dataset('ice_coverage.nc')

        landIceMask = dsMask.regionCellMasks.isel(nRegions=0)
        dsLandIceMask = xarray.Dataset()
        dsLandIceMask['landIceMask'] = landIceMask

        write_netcdf(dsLandIceMask, 'land_ice_mask.nc')

        dsLandIceCulledMesh = cull(dsCulledMesh, dsMask=dsMask, logger=logger)
        write_netcdf(dsLandIceCulledMesh, 'no_ISC_culled_mesh.nc')

    extract_vtk(ignore_time=True, dimension_list=['maxEdges='],
                variable_list=['allOnCells'],
                filename_pattern='culled_mesh.nc',
                out_dir='culled_mesh_vtk',
                use_progress_bar=use_progress_bar)

    if with_cavities:
        extract_vtk(ignore_time=True, dimension_list=['maxEdges='],
                    variable_list=['allOnCells'],
                    filename_pattern='no_ISC_culled_mesh.nc',
                    out_dir='no_ISC_culled_mesh_vtk',
                    use_progress_bar=use_progress_bar)
