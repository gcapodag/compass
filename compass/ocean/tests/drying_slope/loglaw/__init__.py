from compass.ocean.tests.drying_slope.forward import Forward
from compass.ocean.tests.drying_slope.initial_state import InitialState
from compass.ocean.tests.drying_slope.lts.lts_regions import LTSRegions
from compass.ocean.tests.drying_slope.viz import Viz
from compass.testcase import TestCase
from compass.validate import compare_variables


class LogLaw(TestCase):
    """
    The drying_slope test case with log-law drag

    Attributes
    ----------
    resolution : float
        The resolution of the test case in km

    coord_type : str
        The type of vertical coordinate (``sigma``, ``single_layer``, etc.)

    use_lts : bool
        Whether local time-stepping is used
    """

    def __init__(self, test_group, resolution, coord_type, use_lts):
        """
        Create the test case

        Parameters
        ----------
        test_group : compass.ocean.tests.drying_slope.DryingSlope
            The test group that this test case belongs to

        resolution : float
            The resolution of the test case in km

        coord_type : str
            The type of vertical coordinate (``sigma``, ``single_layer``)

        use_lts : bool
            Whether local time-stepping is used
        """
        self.resolution = resolution
        self.coord_type = coord_type
        self.use_lts = use_lts

        if use_lts:
            name = 'loglaw_lts'
        else:
            name = 'loglaw'

        if resolution < 1.:
            res_name = f'{int(resolution*1e3)}m'
        else:
            res_name = f'{int(resolution)}km'
        subdir = f'{res_name}/{coord_type}/{name}'
        super().__init__(test_group=test_group, name=name,
                         subdir=subdir)
        init_step = InitialState(test_case=self, coord_type=coord_type)
        self.add_step(init_step)

        if use_lts:
            self.add_step(LTSRegions(test_case=self, init_step=init_step))

        forward_step = Forward(test_case=self, resolution=resolution,
                               use_lts=use_lts,
                               ntasks=4, openmp_threads=1,
                               coord_type=coord_type)
        forward_step.add_namelist_options(
            {'config_implicit_bottom_drag_type': "'loglaw'"})
        self.add_step(forward_step)
        self.add_step(Viz(test_case=self, damping_coeffs=None))

    def configure(self):
        """
        Modify the configuration options for this test case.
        """

        resolution = self.resolution
        config = self.config
        ny = round(28 / resolution)
        if resolution < 1.:
            ny += 2
        dc = 1e3 * resolution

        config.set('drying_slope', 'ny', f'{ny}', comment='the number of '
                   'mesh cells in the y direction')
        config.set('drying_slope', 'dc', f'{dc}', comment='the distance '
                   'between adjacent cell centers')

    def validate(self):
        """
        Validate variables against a baseline
        """
        variables = ['layerThickness', 'normalVelocity']
        compare_variables(test_case=self, variables=variables,
                          filename1='forward/output.nc')
