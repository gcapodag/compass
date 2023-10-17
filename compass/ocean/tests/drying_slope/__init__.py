from compass.ocean.tests.drying_slope.decomp import Decomp
from compass.ocean.tests.drying_slope.default import Default
from compass.ocean.tests.drying_slope.loglaw import LogLaw
from compass.ocean.tests.drying_slope.ramp import Ramp
from compass.testgroup import TestGroup


class DryingSlope(TestGroup):
    """
    A test group for drying slope (wetting-and-drying) test cases
    """

    def __init__(self, mpas_core):
        """
        mpas_core : compass.MpasCore
            the MPAS core that this test group belongs to
        """
        super().__init__(mpas_core=mpas_core, name='drying_slope')

        use_lts = False
        for resolution in [0.25, 1.]:
            for coord_type in ['sigma', 'single_layer']:
                if coord_type == 'single_layer':
                    use_lts = True
                self.add_test_case(
                    Default(test_group=self, resolution=resolution,
                            coord_type=coord_type, use_lts=use_lts))
                self.add_test_case(
                    Decomp(test_group=self, resolution=resolution,
                           coord_type=coord_type))
                self.add_test_case(
                    Ramp(test_group=self, resolution=resolution,
                         coord_type=coord_type, use_lts=use_lts))
                self.add_test_case(
                    LogLaw(test_group=self, resolution=resolution,
                           coord_type=coord_type, use_lts=use_lts))
