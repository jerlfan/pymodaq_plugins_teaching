from pymodaq.utils.data import DataFromPlugins, Axis, DataToExport
from pymodaq.control_modules.viewer_utility_classes import main
from pymodaq_plugins_mockexamples.daq_viewer_plugins.plugins_2D.daq_2Dviewer_BSCamera import DAQ_2DViewer_BSCamera
import laserbeamsize as lbs
import numpy as np

class DAQ_2DViewer_BeamProfiler(DAQ_2DViewer_BSCamera):
    pass

    def grab_data(self, Naverage=1, **kwargs):

        data_array = self.controller.get_camera_data()
        x, y , dx, dy, phi = lbs.beam_size(data_array)
        dwa = DataFromPlugins(name='profile', data = [data_array], labels=['camera raw'],
                              axes=[Axis(data=self.controller.camera.x_axis/100, label='avion', index=1),
                                    Axis(data=self.controller.camera.x_axis/100, label='bateau', index=0),],
                                    do_plot=False,
                                    do_save=True,
        )

        dwa_position = DataFromPlugins('position',
                                       data = [np.array([x]),
                                               np.array([y]),
                                               ],
                                       labels=['X',
                                               'Y'],
                                       do_plot=True,
                                       do_save=False,)
        dte = DataToExport('profiler',
                           data = [
                               dwa,
                               dwa_position])
        self.dte_signal.emit(dte)

if __name__ == '__main__':
    main(__file__)