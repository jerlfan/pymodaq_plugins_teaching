from collections import OrderedDict
import datetime
import numpy as np

from pymodaq.utils.logger import set_logger, get_module_name
from pymodaq.utils.gui_utils.custom_app import CustomApp
from pymodaq.utils.gui_utils.dock import DockArea, Dock
from  pymodaq.utils.gui_utils.file_io import select_file
from pymodaq.utils.config import Config



from qtpy import QtWidgets
from qtpy.QtCore import Slot, QDate, QThread

from pymodaq.utils import daq_utils as utils
from pymodaq.utils.parameter import ioxml
from pymodaq.control_modules.daq_viewer import DAQ_Viewer
from pymodaq.utils.plotting.data_viewers.viewer2D import Viewer2D
from pymodaq.utils.gui_utils.widgets.lcd import LCD

from pymodaq.utils.h5modules.browsing import H5Browser
from pymodaq.utils.h5modules.saving import H5Saver
from pymodaq.utils.h5modules.data_saving import DataToExportSaver
from pymodaq.utils.data import DataToExport, DataFromPlugins, Axis

import laserbeamsize as lbs
import numpy as np

config = Config()
logger = set_logger(get_module_name(__file__))

EXTENSION_NAME = 'Beam_Profiler'
CLASS_NAME = 'BeamProfiler'
class BeamProfiler(CustomApp):

    # list of dicts enabling the settings tree on the user interface
    params = [
        {'title': 'Main settings:', 'name': 'main_settings', 'type': 'group', 'children': [
            {'title': 'Save base path:', 'name': 'base_path', 'type': 'browsepath',
             'value': config('data_saving', 'h5file', 'save_path')},
            {'title': 'File name:', 'name': 'target_filename', 'type': 'str', 'value': "", 'readonly': True},
            {'title': 'Date:', 'name': 'date', 'type': 'date', 'value': QDate.currentDate()},
            {'title': 'Do something, such as showing data:', 'name': 'do_something', 'type': 'bool', 'value': False},
            {'title': 'Something done:', 'name': 'something_done', 'type': 'led', 'value': False, 'readonly': True},
            {'title': 'Infos:', 'name': 'info', 'type': 'text', 'value': ""},
            {'title': 'push:', 'name': 'push', 'type': 'bool_push', 'value': False}
        ]},
        {'title': 'Other settings:', 'name': 'other_settings', 'type': 'group', 'children': [
            {'title': 'List of stuffs:', 'name': 'list_stuff', 'type': 'list', 'value': 'first',
                'limits': ['first', 'second', 'third'], 'tip': 'choose a stuff from the list'},
            {'title': 'List of integers:', 'name': 'list_int', 'type': 'list', 'value': 0,
                'limits': [0, 256, 512], 'tip': 'choose a stuff from this int list'},
            {'title': 'one integer:', 'name': 'an_integer', 'type': 'int', 'value': 500, },
            {'title': 'one float:', 'name': 'a_float', 'type': 'float', 'value': 2.7, },
        ]},
    ]

    def __init__(self, dockarea,dashboard):

        super().__init__(dockarea,dashboard)

        # init the object parameters
        self.raw_data: DataToExport = None
        self.detector = self.dashboard.modules_manager.detectors_all[0]
        self.setup_ui()

    def setup_actions(self):
        '''
        subclass method from ActionManager
        '''
        logger.debug('setting actions')
        self.add_action('quit', 'Quit', 'close2', "Quit program", toolbar=self.toolbar)
        self.add_action('grab', 'Grab', 'camera', "Grab from camera", checkable=True, toolbar=self.toolbar)
        self.add_action('load', 'Load', 'Open', "Load target file (.h5, .png, .jpg) or data from camera",
                        checkable=False, toolbar=self.toolbar)
        self.add_action('save', 'Save', 'SaveAs', "Save current data", checkable=False, toolbar=self.toolbar)
        self.add_action('show', 'Show/hide', 'read2', "Show Hide DAQViewer", checkable=True, toolbar=self.toolbar)
        self.add_action('browser','h5browser','Open','Open the h5browser', checkable=False, toolbar=self.toolbar)

        logger.debug('actions set')

    def setup_docks(self):
        '''
        subclass method from CustomApp
        '''
        logger.debug(('setting docks'))
        # create a dock containing a viewer object, could be 0D, 1D or 2D depending what kind of data one want to plot here a 0D

        dock_Viewer2D = Dock('Viewer dock', size=(350, 350))
        self.dockarea.addDock(dock_Viewer2D, 'left')
        target_widget = QtWidgets.QWidget()
        self.target_viewer = Viewer2D(target_widget)
        dock_Viewer2D.addWidget(target_widget)

        dock_lcd_position = Dock('Beam position', size=(350, 350))
        self.dockarea.addDock(dock_lcd_position)
        lcd_widget_position = QtWidgets.QWidget()
        dock_lcd_position.addWidget(lcd_widget_position)#, 'digits':3,'Nvals':2)
        self.lcd_position = LCD(lcd_widget_position, digits=6, Nvals=4, labels=['X','dX','Y','dY',])

        self.daq_viewer_area = DockArea()




        logger.debug('docks are set')




    def connect_things(self):
        '''
        subclass method from CustomApp
        '''
        logger.debug('connecting things')
        self.log_signal[str].connect(self.add_log)  # connect together this custom signal with the add_log method

        self.detector.grab_done_signal.connect(self.data_done)
        self.connect_action('quit', self.quit_function)
        self.connect_action('load', self.load_file)
        self.connect_action('save', self.save_data)

        self.connect_action('grab', self.detector.grab)
        self.connect_action('show', self.show_detector)
        self.connect_action('browser',self.open_browser)
        logger.debug('connecting done')

    def show_detector(self, status):
        self.dashboard.dockarea.setVisible(status)

    def open_browser(self, ):
        win = QtWidgets.QMainWindow()
        prog = H5Browser(win)
        win.show()



    def setup_menu(self):
        '''
        subclass method from CustomApp
        '''
        logger.debug('settings menu')
        file_menu = self.mainwindow.menuBar().addMenu('File')
        self.affect_to('quit', file_menu)
        file_menu.addSeparator()
        self.affect_to('load', file_menu)
        self.affect_to('save', file_menu)

        self.affect_to('quit', file_menu)

        logger.debug('menu set')

    def value_changed(self, param):
        logger.debug(f'calling value_changed with param {param.name()}')
        if param.name() == 'do_something':
            if param.value():
                self.log_signal.emit('Do something')
                self.detector.grab_done_signal.connect(self.show_data)
                self.raw_data = []  # init the data to be finally saved
                self.settings.child('main_settings', 'something_done').setValue(True)
            else:
                self.log_signal.emit('Stop Doing something')
                self.detector.grab_done_signal.disconnect()
                self.settings.child('main_settings', 'something_done').setValue(False)

        logger.debug(f'Value change applied')

    def data_done(self, dte: DataToExport):
        # print(data)
        dte2D = dte.get_data_from_dim('Data2D')
        dwa_2D=dte2D.get_data_from_name('BSCamera')
        self.target_viewer.show_data(dwa_2D)

        x, y, dx, dy, phi = lbs.beam_size(dwa_2D[0])

        self.lcd_position.setvalues([np.array([dx]),np.array([dx]),np.array([y]),np.array([dy])])

        dwa_position = DataFromPlugins('position',
                                       data=[np.array([x,y,dx,dy]),
                                             ],
                                       labels=['beam parameters',
                                               ], )
        self.raw_data= DataToExport('profiler',
                           data=[
                               dwa_2D,
                               dwa_position])




    def show_data(self, data: DataToExport):
        """
        do stuff with data from the detector if its grab_done_signal has been connected
        Parameters
        ----------
        data: DataToExport
        """
        self.raw_data = data
        data0D = data.get_data_from_dim('Data0D')

        self.target_viewer.show_data(data0D.data[0])

    def load_file(self):
        # init the data browser module
        widg = QtWidgets.QWidget()
        self.data_browser = H5Browser(widg)
        widg.show()

    def quit_function(self):
        # close all stuff that need to be
        self.detector.quit_fun()
        QtWidgets.QApplication.processEvents()
        self.mainwindow.close()

    def run_detector(self):
        self.detector.ui.grab_pb.click()

    def save_data(self):
        try:
            path = select_file(start_path=self.settings.child('main_settings', 'base_path').value(), save=True,
                                                                   ext='h5')
            if path is not None:
                # init the file object with an addhoc name given by the user
                h5saver = H5Saver(save_type='custom')
                h5saver.init_file(update_h5=True, addhoc_file_path=path)
                datasaver = DataToExportSaver(h5saver)


                # save all metadata
                settings_str = ioxml.parameter_to_xml_string(self.settings)
                settings_str = b'<All_settings>' + settings_str
                settings_str += ioxml.parameter_to_xml_string(self.detector.settings) + ioxml.parameter_to_xml_string(
                    h5saver.settings) + b'</All_settings>'

                datasaver.add_data(h5saver.root(), self.raw_data, settings_as_xml=settings_str)

                h5saver.close_file()

                st = 'file {:s} has been saved'.format(str(path))
                self.add_log(st)
                self.settings.child('main_settings', 'info').setValue(st)

        except Exception as e:
            logger.exception(str(e))

    @Slot(str)
    def add_log(self, txt):
        """
            Add a log to the logger list from the given text log and the current time

            ================ ========= ======================
            **Parameters**   **Type**   **Description**

             *txt*             string    the log to be added
            ================ ========= ======================

        """
        now = datetime.datetime.now()
        new_item = QtWidgets.QListWidgetItem(str(now) + ": " + txt)
        self.logger_list.addItem(new_item)
        logger.info(txt)


def main():
    from pymodaq.dashboard import DashBoard
    from pathlib import Path
    import sys

    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    area = DockArea()
    win.setCentralWidget(area)
    win.resize(1000, 500)
    win.setWindowTitle('PyMoDAQ Dashboard')

    dashboard = DashBoard(area)
    daq_scan = None
    file = Path(r"C:\ProgramData\.pymodaq\preset_configs\BSform.xml")
    if file.exists():
        dashboard.set_preset_mode(file)
        daq_scan = dashboard.load_extension_from_name(EXTENSION_NAME)
    else:
        msgBox = QtWidgets.QMessageBox()
        msgBox.setText(f"The default file specified in the configuration file does not exists!\n"
                       f"{file}\n"
                       f"Impossible to load the DAQScan Module")
        msgBox.setStandardButtons(msgBox.Ok)
        ret = msgBox.exec()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
