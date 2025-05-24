# Standard Library Imports
import os
import sys
import re
import atexit
import time
import subprocess
from datetime import datetime
from threading import Thread, Event

# Third-party Library Imports
import numpy as np
import requests
import rawpy
import shutil
from scipy.ndimage import shift
from flask import Flask, request
from flask_socketio import SocketIO, emit
import socketio
from PyQt5 import QtWidgets, uic, QtGui, QtCore
from PyQt5.QtWidgets import QApplication, QMessageBox, QStackedWidget, QLabel
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QPixmap, QImage

# Hardware-related Imports
import board
import adafruit_dotstar as dotstar
import RPi.GPIO as GPIO
from picamera2 import Picamera2, Preview
from picamera2.previews.qt import QGlPicamera2

# Custom Library Imports
import OpenLMlib as PSR

# Flask Setup
app = Flask(__name__)
serverpi = SocketIO(app)

# PyQt Setup
app_path = os.path.abspath(__file__)
app_directory = os.path.dirname(app_path)
ui_file_path = app_directory + '/OpenLM_GUI_RP.ui'

Ui_Form, QtBaseClass = uic.loadUiType(ui_file_path)

connected_clients = {}
TL_message = False

shutdown_event = Event()

# Flask Shutdown Route
@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Shuts down the Flask server when POST is called."""
    print("Shutting down Flask server...")
    func = request.environ.get('werkzeug.server.shutdown')
    if func:
        func()
    return 'Server shutting down...', 200

@serverpi.on('connect')
def handle_connect():
    client_ip = request.remote_addr
    print(f"Client connected with IP: {client_ip}")
    connected_clients[client_ip] = True
    print(f"Current connected clients: {connected_clients}")
    
@serverpi.on('disconnect')
def handle_disconnect():
    client_ip = request.remote_addr
    print(f"Client disconnected with IP: {client_ip}")
    if client_ip in connected_clients:
        del connected_clients[client_ip]
    print(f"Current connected clients: {connected_clients}")

class MainThreadCommunicate(QObject):
    update_image_label = pyqtSignal(str, str)

class MainWindow(QtWidgets.QMainWindow, Ui_Form):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)
        self.setWindowTitle("OpenLM")
        self.folderText.setText("/home/labpi")
        self.communicate = MainThreadCommunicate()
        self.communicate.update_image_label.connect(self.update_screen)
        self.TLtimer = QTimer(self)
        self.TLtimer.timeout.connect(self.send_TLmessage)
        
        self.dots = dotstar.DotStar(board.SCK, board.MOSI, 64, brightness=1)
        self.dots[35] = (0, 255, 0)
        
        self.picam2 = Picamera2()
        
        self.stacked_widget = self.findChild(QStackedWidget, "viewWindow")
        self.preview_window = QGlPicamera2(self.picam2, keep_ar=False)
        self.imageview_window = self.findChild(QLabel, 'display')
        self.stacked_widget.addWidget(self.preview_window)
        self.stacked_widget.addWidget(self.imageview_window)
        self.stacked_widget.setCurrentWidget(self.preview_window)
        self.picam2.stop()
        
        self.switchButton.clicked.connect(self.led_switch)
        self.previewButton.clicked.connect(self.start_preview)
        self.captureButton.clicked.connect(self.capture_image)
        self.captureHRButton.clicked.connect(self.capture_HRimage)
        self.timeLapseButton.clicked.connect(self.capture_TLimage)
        
        self.clientBox.stateChanged.connect(self.check_client)
        
        self.preview_status_code = 0
        self.picam2_status_code = 1
        
        @serverpi.on('responseLR')
        def handle_response(msg):

            focus = msg.get('focusLR', 'No focus provided')
            self.focusText.setText(str(focus))
            self.applicationStatus.setText("Capture Completed")
            Jimg_path = self.folderText.text() + "/" + str(self.fileText.text()) + ".jpg"
            self.display_Jimg(Jimg_path)
            QApplication.processEvents()    
            self.captureButton.setEnabled(True)
            
        @serverpi.on('responseHR')
        def handle_response(msg):
            
            focus = msg.get('focusHR', 'No focus provided')
            focus_z = focus
            self.focusText.setText(str(focus_z))
            self.applicationStatus.setText("HR Capture Completed")
            Jimg_path = self.folderText.text() + "/HR_reconstructed.jpg"
            self.display_Jimg(Jimg_path)
            QApplication.processEvents()    
            self.captureHRButton.setEnabled(True)
        
        @serverpi.on('responseTL')
        def handle_response(msg):

            global TL_message
            
            TL_message = False
            folder_number = msg.get('folderTL', 'No folder number provided')
            if folder_number == "file: 404":
                self.send_warning("No Shift Map Found")
                self.timeLapseButton.setEnabled(True)
            else: 
                folder_n = folder_number
                interval_time = self.intervalText.text()
                current_time = int(interval_time)*int(folder_n)
                msg = "Image Time: " + str(current_time) + " min"
                Jimg_path = self.folderText.text() + "/" + str(folder_n) +"/HR_reconstructed.jpg"
                self.communicate.update_image_label.emit(msg, Jimg_path)
                self.display_Jimg(Jimg_path)
                QApplication.processEvents()
                
        @serverpi.on('responseFTL')
        def handle_response(msg):
            
            folder_number = msg.get('msgFTL', 'No message provided')
            self.timeLapseButton.setEnabled(True)
            self.applicationStatus.setText("Time Lapse Completed")
            QApplication.processEvents()
        
        @serverpi.on('captureLR')
        def handle_response(msg):

            capture_info = msg.get('folderLR', 'No message provided')
            pathLED_exposure = re.split(r'(\d+)$', capture_info)
            pathLED = pathLED_exposure[0][:-1]
            exposure = int(pathLED_exposure[1])
            path_LED = re.split(r'(\d+)$', pathLED)
            Jpath = self.folderText.text() + path_LED[0]
            path = self.folderText.text() + path_LED[0][:-3] + 'dng'
            led_number = int(path_LED[1])
            self.dots.fill((0, 0, 0))
            QApplication.processEvents()
            self.dots[led_number] = (0, 255, 0)
            
            if self.picam2_status_code == 1:
                self.picam2.stop()
                self.picam2.close()
                self.picam2_status_code = 0
                
            rpicam2 = Picamera2()
            rcapture_config = rpicam2.create_still_configuration(raw={}, display=None)
            rpicam2.configure(rcapture_config)
            rpicam2.set_controls({"ExposureTime": exposure})
            rpicam2.start()
            
            r = rpicam2.capture_request()
            r.save("main", Jpath)
            r.save_dng(path)
            r.release()
            #self.dots.fill((0, 0, 0))
            rpicam2.stop()
            rpicam2.close()
            
            serverpi.emit('processLR', {'completedLR': 'Capture Done'})
            
        @serverpi.on('captureHR')
        def handle_response(msg):
            capture_info = msg.get('folderHR', 'No message provided')
            path_exposure = re.split(r'(\d+)$', capture_info)
            folder = self.folderText.text() + path_exposure[0]
            exposure = int(path_exposure[1])
            
            self.dots.fill((0, 0, 0))
            RGB_value = (0,255,0)
            led_number = list(range(0, 64))
            focus = self.focusText.text()
            
            if self.picam2_status_code == 1:
                self.picam2.stop()
                self.picam2.close()
                self.picam2_status_code = 0
                
            rpicam2 = Picamera2()
            rcapture_config = rpicam2.create_still_configuration(raw={}, display=None)
            rpicam2.configure(rcapture_config)
            rpicam2.set_controls({"ExposureTime": exposure})
            rpicam2.start()
            
            for led in led_number:
                progress = "HR: " + str(led) + '/' + str(63) 
                self.applicationStatus.setText(progress)
                QApplication.processEvents()
                self.dots[led] = RGB_value
                time.sleep(1)
                self.jimg_path = folder + "/" + str(led) + ".jpg"
                self.img_path = folder + "/" + str(led) + ".dng"
                r = rpicam2.capture_request()
                r.save("main", self.jimg_path)
                r.save_dng(self.img_path)
                r.release()
                self.dots.fill((0, 0, 0))
                serverpi.emit('processHR', {'completedHR': str(led)})
            rpicam2.stop()
            rpicam2.close()
            
            serverpi.emit('processHR', {'completedHR': 'Capture Done'})
            
        @serverpi.on('captureTL')
        def handle_response(msg):
            capture_info = msg.get('folderTL', 'No message provided')
            path = capture_info[0]
            exposure = capture_info[1]
            total_time = int(capture_info[2])*60
            interval_time = int(capture_info[3])
            
            num_set = round(total_time / interval_time)
        
            self.dots.fill((0, 0, 0))
            RGB_value = (0,255,0)
            led_number = list(np.arange(14,22))+list(np.arange(25,30))+\
                         list(np.arange(33,38))+list(np.arange(41,46))+\
                         list(np.arange(49,54))
            focus = self.focusText.text()
            
            if self.picam2_status_code == 1:
                self.picam2.stop()
                self.picam2.close()
                self.picam2_status_code = 0
            rpicam2 = Picamera2()
            rcapture_config = rpicam2.create_still_configuration(raw={}, display=None)
            rpicam2.configure(rcapture_config)
            rpicam2.set_controls({"ExposureTime": int(self.exposureText.text())})
            rpicam2.start()
            for n in range(num_set+1):
                status_text = 'TL: ' + str(n) + '/' + str(num_set)
                self.applicationStatus.setText(status_text)
                QApplication.processEvents()
                current_time_start = datetime.now()  # Get current time as a datetime object
                subfolder = self.folderText.text() + path + str(n)  # Use os.path.join for compatibility
                self.check_and_create_folder(subfolder)
   
                for led in led_number:
                    self.dots[led] = RGB_value
                    time.sleep(1)
                    self.jimg_path = subfolder + "/" + str(led) + ".jpg"
                    self.img_path = subfolder + "/" + str(led) + ".dng"
                    rpi_request = rpicam2.capture_request()
                    rpi_request.save("main", self.jimg_path)
                    rpi_request.save_dng(self.img_path)
                    rpi_request.release()
                    self.dots.fill((0, 0, 0))
                     
                self.current_subfolder = str(n)
                serverpi.emit('processTL', {'completedTL': str(n)})
                current_time_end = datetime.now()
                if n < num_set:
                    time_difference = (current_time_end - current_time_start).total_seconds()
                    time_to_sleep = max(0, interval_time * 60 - time_difference)
                    time.sleep(time_to_sleep)
            rpicam2.stop()
            rpicam2.close()
            serverpi.emit('processTL', {'completedTL': 'Capture Done'})
        
    def led_switch(self):
        
        self.dots.fill((0, 0, 0))
        QApplication.processEvents()
        led_number = int(self.LEDValue.text())
        self.dots[led_number] = (0, 255, 0)
    
    def start_preview(self):
        
        if self.picam2_status_code == 0:
            self.picam2 = Picamera2()
            self.preview_window = QGlPicamera2(self.picam2, keep_ar=False)
            self.stacked_widget.addWidget(self.preview_window)
            self.stacked_widget.setCurrentWidget(self.preview_window)
            self.picam2_status_code = 1
            
        if self.preview_status_code == 0:
            self.applicationStatus.setText("Preview Mode")
            self.stacked_widget.setCurrentWidget(self.preview_window)
            self.picam2.configure(self.picam2.create_preview_configuration({"size": (1640, 1232)}))
            self.picam2.start()
            self.preview_status_code = 1
            self.previewButton.setText("Stop Preview")
        else:
            self.picam2.stop()
            self.applicationStatus.setText("Preview Stopped")
            self.stacked_widget.setCurrentWidget(self.imageview_window)
            self.previewButton.setText("Preview")
            self.preview_status_code = 0
            
    def capture_image(self):
        
        self.applicationStatus.setText("Capture Mode")
        QApplication.processEvents()
        self.captureButton.setEnabled(False)
        self.stacked_widget.setCurrentWidget(self.imageview_window)
        
        folder = self.folderText.text()
        self.check_and_create_folder(folder)
        if not os.access(folder, os.W_OK):
            self.show_warning("Folder Access Permission Denied.")
            self.applicationStatus.setText("Capture Failed")
            QApplication.processEvents()    
            self.captureButton.setEnabled(True)
            return
        
        file_name = self.fileText.text()
        if not file_name:
            self.show_warning("Give A File Name")
            self.captureButton.setEnabled(True)
            return
        self.jimg_path = folder + "/" + str(file_name) + ".jpg"
        self.img_path = folder + "/" + str(file_name) + ".dng"
        
        if self.picam2_status_code == 0:
            self.picam2 = Picamera2()
            self.picam2_status_code = 1
        
        capture_config = self.picam2.create_still_configuration(raw={}, display=None)
        self.picam2.configure(capture_config)
        self.picam2.set_controls({"ExposureTime": int(self.exposureText.text())})
        self.picam2.start()
        
        if self.focusBox.isChecked():
            self.applicationStatus.setText("Focusing......")
            QApplication.processEvents()
            
            if self.clientBox.isChecked():
                self.picam2.capture_request(wait = False, signal_function = self.capture_done_single_focus_client)        
            else:
                self.picam2.capture_request(wait = False, signal_function = self.capture_done_single_focus)
        else:
            self.picam2.capture_request(wait = False, signal_function = self.capture_done_single)

    def capture_HRimage(self):
        
        self.applicationStatus.setText("Capture HR Mode")
        QApplication.processEvents()
        self.captureHRButton.setEnabled(False)        
        self.stacked_widget.setCurrentWidget(self.imageview_window)
        
        folder = self.folderText.text()
        self.check_and_create_folder(folder)
        if not os.access(folder, os.W_OK):
            self.show_warning("Folder Access Permission Denied.")
            self.applicationStatus.setText("Capture Failed")
            QApplication.processEvents()    
            self.captureHRButton.setEnabled(True)
            return
        
        self.dots.fill((0, 0, 0))
        RGB_value = (0,255,0)
        led_number = list(range(0, 64))
        
        if self.picam2_status_code == 1:
            self.picam2.stop()
            self.picam2.close()
            self.picam2_status_code = 0
        
        rpicam2 = Picamera2()
        rcapture_config = rpicam2.create_still_configuration(raw={}, display=None)
        rpicam2.configure(rcapture_config)
        rpicam2.set_controls({"ExposureTime": int(self.exposureText.text())})
        rpicam2.start()
        
        for led in led_number:
            progress = "HR: " + str(led) + '/' + str(63) 
            self.applicationStatus.setText(progress)
            QApplication.processEvents()
            self.dots[led] = RGB_value
            time.sleep(1)
            self.jimg_path = folder + "/" + str(led) + ".jpg"
            self.img_path = folder + "/" + str(led) + ".dng"
            r = rpicam2.capture_request()
            r.save("main", self.jimg_path)
            r.save_dng(self.img_path)
            r.release()
            self.dots.fill((0, 0, 0))
        rpicam2.stop()
        rpicam2.close()
        
        if self.clientBox.isChecked():
            if self.PSRBox.isChecked():
                self.applicationStatus.setText("HR: Client Processing...")
                QApplication.processEvents()
                focus = self.focusText.text()
                sub_folder = self.shared_folder_path(folder)
                sub_file_path = sub_folder + focus
                serverpi.emit('messageHR', {'HRpath': sub_file_path})
            else:
                self.applicationStatus.setText("HR Capture Completed")
                QApplication.processEvents() 
                self.captureHRButton.setEnabled(True)
        else:   
            self.applicationStatus.setText("HR Capture Completed")
            QApplication.processEvents() 
            self.captureHRButton.setEnabled(True)
    
    def capture_TLimage(self):
        
        self.applicationStatus.setText("Capture TL Mode")
        QApplication.processEvents()
        self.timeLapseButton.setEnabled(False)        
        self.stacked_widget.setCurrentWidget(self.imageview_window)
        
        folder = self.folderText.text()
        self.check_and_create_folder(folder)
        if not os.access(folder, os.W_OK):
            self.show_warning("Folder Access Permission Denied.")
            self.applicationStatus.setText("Capture Failed")
            QApplication.processEvents()    
            self.captureTLButton.setEnabled(True)
            return
        
        total_time = int(self.totalText.text()) * 60 # total time in minutes
        interval_time = int(self.intervalText.text())  # interval time in minutes 
        num_set = round(total_time / interval_time)
        
        desired_disk = round((num_set*28*15)/1024)
        total, used, free = shutil.disk_usage(folder)
        total_gb = free/(2**30)
        if total_gb < desired_disk:
            self.show_warning("Current Disk Has Not Enough Space")
            self.applicationStatus.setText("Capture Failed")
            QApplication.processEvents()    
            self.timeLapseButton.setEnabled(True)
            return
        
        self.dots.fill((0, 0, 0))
        RGB_value = (0,255,0)
        led_number = list(np.arange(14,22))+list(np.arange(25,30))+\
                     list(np.arange(33,38))+list(np.arange(41,46))+\
                     list(np.arange(49,54))
        focus = self.focusText.text()
        
        if self.picam2_status_code == 1:
            self.picam2.stop()
            self.picam2.close()
            self.picam2_status_code = 0
        
        rpicam2 = Picamera2()
        rcapture_config = rpicam2.create_still_configuration(raw={}, display=None)
        rpicam2.configure(rcapture_config)
        rpicam2.set_controls({"ExposureTime": int(self.exposureText.text())})
        rpicam2.start()
        
        if self.PSRBox.isChecked():
            if self.clientBox.isChecked():
                for n in range(num_set+1):
                    status_text = 'TL: ' + str(n) + '/' + str(num_set)
                    self.applicationStatus.setText(status_text)
                    QApplication.processEvents()
                    current_time_start = datetime.now()  # Get current time as a datetime object
                    subfolder = folder + '/' + str(n)  # Use os.path.join for compatibility
                    self.check_and_create_folder(subfolder)
                    
                    for led in led_number:
                        self.dots[led] = RGB_value
                        time.sleep(1)
                        self.jimg_path = subfolder + "/" + str(led) + ".jpg"
                        self.img_path = subfolder + "/" + str(led) + ".dng"
                        rpi_request = rpicam2.capture_request()
                        rpi_request.save("main", self.jimg_path)
                        rpi_request.save_dng(self.img_path)
                        rpi_request.release()
                        self.dots.fill((0, 0, 0))
                     
                    self.current_subfolder = str(n)
                    if self.current_subfolder == "0":
                        self.send_TLmessage()
                    current_time_end = datetime.now()
                    if n < num_set:
                        time_difference = (current_time_end - current_time_start).total_seconds() 
                        time_to_sleep = max(0, interval_time * 60 - time_difference)
                        self.TLtimer.start(int(round(time_to_sleep*1000)))
                rpicam2.stop()
                rpicam2.close()
                self.applicationStatus.setText("TL Final Processing")
                QApplication.processEvents()
                sub_folder = self.shared_folder_path(folder)
                num_folder_path = sub_folder + str(num_set) + "/" + focus
                serverpi.emit('messageFTL', {'FTLpath': num_folder_path})
                    
            else:
                self.show_warning("Raspberry Pi Won't Be Able To Run The Algorithm. Check 'Client' For Processing.")
                self.applicationStatus.setText("Capture Failed")
                QApplication.processEvents()    
                self.timeLapseButton.setEnabled(True)
        else:
            for n in range(num_set+1):
                status_text = 'TL: ' + str(n) + '/' + str(num_set)
                self.applicationStatus.setText(status_text)
                QApplication.processEvents()
                current_time_start = datetime.now()  # Get current time as a datetime object
                subfolder = folder + '/' + str(n)  # Use os.path.join for compatibility
                self.check_and_create_folder(subfolder)
                
                for led in led_number:
                    self.dots[led] = RGB_value
                    time.sleep(1)
                    self.jimg_path = subfolder + "/" + str(led) + ".jpg"
                    self.img_path = subfolder + "/" + str(led) + ".dng"
                    rpi_request = rpicam2.capture_request()
                    rpi_request.save("main", self.jimg_path)
                    rpi_request.save_dng(self.img_path)
                    rpi_request.release()
                    self.dots.fill((0, 0, 0))
                if n < num_set:
                    current_time_end = datetime.now()
                    time_difference = (current_time_end - current_time_start).total_seconds() 
                    time_to_sleep = max(0, interval_time * 60 - time_difference) 
                    time.sleep(time_to_sleep)
            
            rpicam2.stop()
            rpicam2.close()
            self.timeLapseButton.setEnabled(True)
            self.applicationStatus.setText("Time Lapse Completed")
            QApplication.processEvents()
                
    def capture_done_single(self,job):
        picam_request = self.picam2.wait(job)
        picam_request.save_dng(self.img_path)
        picam_request.save("main", self.jimg_path)
        picam_request.release()
        self.picam2.stop()
        self.display_Jimg(self.jimg_path)
        self.applicationStatus.setText("Capture Completed")
        QApplication.processEvents() 
        self.captureButton.setEnabled(True)
    
    def capture_done_single_focus(self,job):
        picam_request = self.picam2.wait(job)
        picam_request.save_dng(self.img_path)
        picam_request.save("main", self.jimg_path)
        picam_request.release()
        self.picam2.stop()
        
        field_of_view = PSR.largest_FOV(self.img_path)
        focus = self.focusText.text()        
        if not focus:
            reconstructed_image, optimized_zs = PSR.imageReconstruction_unknownZ(field_of_view)
            focus_nimg_path = self.folderText.text() + "/" + str(self.fileText.text()) + "_focused.npy"
            focus_jimg_path = self.folderText.text() + "/" + str(self.fileText.text()) + "_focused.jpg"
            np.save(focus_nimg_path, reconstructed_image)
            jpg_img = PSR.npy2jpg(reconstructed_image)
            jpg_img.save(focus_jimg_path)
            self.focusText.setText(str(int(round(optimized_zs*10**6))))
        else:
            reconstructed_image, ToG, optimized_zs = PSR.imageReconstruction(field_of_view,int(focus)*10**-6,0,1)
            focus_nimg_path = self.folderText.text() + "/" + str(self.fileText.text()) + "_focused.npy"
            focus_jimg_path = self.folderText.text() + "/" + str(self.fileText.text()) + "_focused.jpg"
            np.save(focus_nimg_path, reconstructed_image)
            jpg_img = PSR.npy2jpg(reconstructed_image)
            jpg_img.save(focus_jimg_path)
            
        self.display_Jimg(focus_jimg_path)
        self.applicationStatus.setText("Capture Completed")
        QApplication.processEvents() 
        self.captureButton.setEnabled(True)
    
    def capture_done_single_focus_client(self,job):
        picam_request = self.picam2.wait(job)
        picam_request.save_dng(self.img_path)
        picam_request.save("main", self.jimg_path)
        picam_request.release()
        self.picam2.stop()
        focus = self.focusText.text()
        folder = self.folderText.text()
        file_name = self.fileText.text()
        sub_folder = self.shared_folder_path(folder)
        sub_file_path = sub_folder + str(file_name) + ".dng" + focus
        serverpi.emit('messageLR', {'LRpath': sub_file_path})
    
    def check_and_create_folder(self,folder_path):
        if not os.path.exists(folder_path):
            cmd = f'sudo mkdir -p "{folder_path}"'
            result = os.system(cmd)
    
    def shared_folder_path(self,path):
        folders = path.split('/')
        if len(folders) > 4:
            return '/'+'/'.join(folders[4:])+'/'
        else:
            return '/'
        
    def send_TLmessage(self):
        
        global TL_message
        
        if not TL_message:
            folder = self.folderText.text()
            sub_folder = self.shared_folder_path(folder)
            focus = self.focusText.text()
            sub_file_path = sub_folder + self.current_subfolder +"/" + focus
            TL_message = True
            serverpi.emit('messageTL', {'TLpath': sub_file_path})
        else:
            self.TLtimer.stop()
            
        
    def display_Jimg(self,path):
        q_image = QImage(path)
        pixmap = QPixmap.fromImage(q_image)
        self.display.setPixmap(pixmap)
        self.display.setScaledContents(True)
        
    def check_client(self):
        
        if self.clientBox.isChecked():
            if not connected_clients:
                self.show_warning("No Client Connection")
        
    def update_screen(self, msg, path):
        self.imageTimeLabel.setText(msg)
        self.display_Jimg(path)
        
    def show_warning(self,warning):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Warning")
        msg.setText("This is a warning message!")
        msg.setInformativeText(str(warning))
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        
    def switch_off(self):
        self.dots.deinit()
        self.picam2.stop()
    
    def closeEvent(self, event):
        """Handle the close event to shutdown Flask and close the app."""
        reply = QMessageBox.question(self, 'Shutdown', 'Do you want to stop the server and exit?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            # Trigger Flask shutdown via a POST request
            self.switch_off()
            self.shutdown_flask()
            event.accept()  # Proceed with closing the window
        else:
            event.ignore()

    def shutdown_flask(self):
        """Send a POST request to Flask to shut it down."""
        try:
            response = requests.post('http://127.0.0.1:5000/shutdown')  # Trigger the Flask shutdown route
            print(f"Flask shutdown response: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error during shutdown request: {e}")
        shutdown_event.set()  # Indicate Flask thread should shutdown

# Run Flask App in a separate thread
def run_flask_app():
    app.run(host='0.0.0.0', port=5000, use_reloader=False)

if __name__ == "__main__":
    # Start Flask app in a separate thread
    thread = Thread(target=run_flask_app)
    thread.daemon = True  # Ensures the thread will exit when the main program ends
    thread.start()

    # Start PyQt application
    pyqt_app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    sys.exit(pyqt_app.exec_())

