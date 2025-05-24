import time
import sys
import os
import cv2
import re
import numpy as np
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget
from PyQt5.QtGui import QPixmap, QImage, QColor, QPalette
from PyQt5.QtCore import QCoreApplication, pyqtSignal, QObject, QThread, QMutex
from skimage.registration import phase_cross_correlation
from flask import Flask, request, jsonify
import OpenLMlib as PSR
import logging
import os
from werkzeug.serving import make_server
import threading
import socket
from PIL import Image
import socketio
import socket

flask_app = Flask(__name__)
clientWin = socketio.Client()

app_path = os.path.abspath(__file__)
app_directory = os.path.dirname(app_path)
ui_file_path = app_directory + '/OpenLM_GUI_Win.ui'
Ui_Form, QtBaseClass = uic.loadUiType(ui_file_path)


def get_server_ip(ip_address):
    global server_ip
    server_ip = 'http://' + ip_address + ':5000'

class Communicate(QObject):

    update_image_signal = pyqtSignal(list)

class ImageProcessingThread(QThread):
    processed_image_signal = pyqtSignal(list)

    def __init__(self, info_list, process_callback):
        super().__init__()
        self.subfolder_path = info_list[0]
        self.current_set = info_list[1]
        if len(info_list) > 2:
            self.focus = str(info_list[2])
        else:
            self.focus = False
        self.process_callback = process_callback

    def run(self):
        print(f"Processing image: {self.subfolder_path}")

        scale_factor = 4
        file_name_list = list(np.arange(17, 22)) + list(np.arange(25, 30)) + \
                        list(np.arange(33, 38)) + list(np.arange(41, 46)) + \
                        list(np.arange(49, 54))
        app_path = os.path.abspath(__file__)
        app_directory = os.path.dirname(app_path)
        shift_map_path = app_directory + "/shift_map.npy"
        shift_map = np.load(shift_map_path)
        frames = []
        for i in range(len(file_name_list)):
            file_path = self.subfolder_path + str(file_name_list[i]) + ".dng"
            img = PSR.largest_FOV(file_path)
            frames.append(img)
        frames = np.array(frames)
        frame_size = len(file_name_list)
                                        
        HR_img = PSR.superResolution(frames, shift_map, frame_size, scale_factor)
        HR_path = self.subfolder_path + "HR_raw.npy"
        np.save(HR_path, HR_img)

        if not self.focus:
            reconstructed_image, optimized_zs = PSR.imageReconstruction_unknownZ(frames[12,:,:])
            optimized_zs_HR = optimized_zs*scale_factor**2
            reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,optimized_zs_HR,1,1)
        else:
            if int(self.focus) < 1000:
                optimized_zs_HR = int(self.focus)*10**-6*scale_factor**2
                reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,optimized_zs_HR,1,1)
            else:
                reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,int(self.focus)*10**-6,0,1)

        imgHR_path = self.subfolder_path + "HR_reconstructed.npy"
        np.save(imgHR_path, reconstructed_imageHR)
        Jimg_path = self.subfolder_path + "HR_reconstructed.jpg"
        jpg_img = PSR.npy2jpg(reconstructed_imageHR)
        jpg_img.save(Jimg_path)

        output_info = [Jimg_path, str(round(optimized_zs**10**6)), self.current_set]
        self.processed_image_signal.emit(output_info)

class ClientApp(QtWidgets.QMainWindow, Ui_Form):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle("OpenLM")

        self.communicate = Communicate()
        self.communicate.update_image_signal.connect(self.display_output)

        self.ready_process = True  # Flag to indicate if image processing is ongoing
        self.next_image = []  # Queue to store incoming image paths
        self.mutex = QMutex()  # Mutex for thread safety

        self.connectionLabel.setStyleSheet("background-color: red")

        self.connectButton.clicked.connect(self.connect_server)
        self.captureButton.clicked.connect(self.capture_LR)
        self.captureHRButton.clicked.connect(self.capture_HR)
        self.timelapseButton.clicked.connect(self.capture_TL)
        self.exampleLRButton.clicked.connect(self.show_LR)
        self.exampleHRButton.clicked.connect(self.show_HR)

        self.focusLRButton.clicked.connect(self.focus_LR)
        self.focusHRButton.clicked.connect(self.focus_HR)
        self.allPSRButton.clicked.connect(self.all_PSR)
        self.videoButton.clicked.connect(self.write_Video)

        ip_address = self.ipText.text()
        if ip_address:
            get_server_ip(ip_address)

        #clientWin.connect(server_ip)
        #self.connection_status(clientWin.connected)

        clientWin.on('messageLR', self.messageLR_from_server)
        clientWin.on('messageHR', self.messageHR_from_server)
        clientWin.on('messageTL', self.messageTL_from_server)
        clientWin.on('messageFTL', self.messageFTL_from_server)
        clientWin.on('processLR', self.process_LR_image)
        clientWin.on('processHR', self.process_HR_image)
        clientWin.on('processTL', self.process_TL_image)

    def connect_server(self):

        ip_address = self.ipText.text()
        get_server_ip(ip_address)
        try:
            clientWin.connect(server_ip)
            self.connectionLabel.setStyleSheet("background-color: lightgreen")
            self.connectButton.setEnabled(False)
        except Exception as e:
            print(f"Connection failed: {e}")
            self.connectionLabel.setStyleSheet("background-color: red")

    def capture_LR(self):

        self.statusLabel.setText("Capture Mode")
        self.captureButton.setEnabled(False)
        QApplication.processEvents()
        path = self.folderText.text()
        self.check_and_create_folder(path)
        file_name = self.fileNameText.text()
        led_num = self.LEDText.text()
        exposure_time = self.exposureText.text()
        shared_folder = self.shared_folder_path(path)
        if not file_name:
            self.show_warning("Give A File Name")
        else:
            file_path = shared_folder + file_name + ".jpg" + led_num + "T" + exposure_time
        clientWin.emit('captureLR', {'folderLR':file_path})
    
    def process_LR_image(self,msg):

        info = msg.get('completedLR', 'No info provided')
        self.statusLabel.setText("LR Processing...")
        QApplication.processEvents()
        path = self.folderText.text()
        file_name = self.fileNameText.text()
        file_path = path + "/" + file_name + ".dng"
        focus = self.startZText.text()
        time.sleep(6)
        fov = PSR.largest_FOV(file_path)
        if not focus: 
            reconstructed_image, optimized_zs = PSR.imageReconstruction_unknownZ(fov)
            img_path = file_path[:-3] + "npy"
            Jimg_path = file_path[:-3] + "jpg"
            np.save(img_path, reconstructed_image)
            jpg_img = PSR.npy2jpg(reconstructed_image)
            jpg_img.save(Jimg_path)
            self.startZText.setText(str(round(optimized_zs**10**6)))
        else:
            reconstructed_image, ToG, optimized_zs = PSR.imageReconstruction(fov,int(focus)*10**-6,0,1)
            img_path = file_path[:-3] + "npy"
            Jimg_path = file_path[:-3] + "jpg"
            np.save(img_path, reconstructed_image)
            jpg_img = PSR.npy2jpg(reconstructed_image)
            jpg_img.save(Jimg_path)

        self.display_Jimg(Jimg_path)
        self.captureButton.setEnabled(True)
        self.statusLabel.setText("LR Mode Completed")
        QApplication.processEvents()

    def capture_HR(self):

        self.statusLabel.setText("Capture HR Mode")
        self.captureHRButton.setEnabled(False)
        QApplication.processEvents()
        path = self.folderText.text()
        self.check_and_create_folder(path)
        exposure_time = self.exposureText.text()
        shared_folder = self.shared_folder_path(path)
        folder_path = shared_folder + exposure_time
        clientWin.emit('captureHR', {'folderHR':folder_path})

    def process_HR_image(self,msg):

        info = msg.get('completedHR', 'No info provided')
        if info == "Capture Done":
            if self.PSRBox.isChecked():
                self.statusLabel.setText("HR Processing...")
                QApplication.processEvents()
                path = self.folderText.text()
                focus = self.startZText.text()
                scale_factor = 4
                file_name_list = list(np.arange(17, 22)) + list(np.arange(25, 30)) + \
                                list(np.arange(33, 38)) + list(np.arange(41, 46)) + \
                                list(np.arange(49, 54))
                frames = []
                for i in range(len(file_name_list)):
                    file_path = path + "/" + str(file_name_list[i]) + ".dng"
                    img = PSR.largest_FOV(file_path)
                    frames.append(img)
                frames = np.array(frames)
                frame_size = len(file_name_list)

                app_path = os.path.abspath(__file__)
                app_directory = os.path.dirname(app_path)
                background_path = app_directory + "/background.npy"
                shift_map_path = app_directory + "/shift_map.npy"
                if os.path.exists(shift_map_path):
                    shift_map = np.load(shift_map_path)
                else:
                    shift_map = PSR.shiftMap(frames,frame_size)
                    np.save(shift_map_path,shift_map)
                        
                HR_img = PSR.superResolution(frames, shift_map, frame_size, scale_factor)
                HR_path = path + "/HR_raw.npy"
                np.save(HR_path, HR_img)

                if os.path.exists(background_path):
                    background = np.load(background_path)
                    HR_img -= background

                if not focus:
                    reconstructed_image, optimized_zs = PSR.imageReconstruction_unknownZ(frames[12,:,:])
                    optimized_zs_HR = optimized_zs*scale_factor**2
                    reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,optimized_zs_HR,1,1)
                    self.startZText.setText(str(round(optimized_zs**10**6)))
                else:
                    if int(focus) < 1000:
                        optimized_zs_HR = int(focus)*10**-6*scale_factor**2
                        reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,optimized_zs_HR,1,1)
                        self.startZText.setText(str(round(optimized_zs**10**6)))
                    else:
                        reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,int(focus)*10**-6,0,1)

                imgHR_path = path + "/HR_reconstructed.npy"
                np.save(imgHR_path, reconstructed_imageHR)
                Jimg_path = path + "/HR_reconstructed.jpg"
                jpg_img = PSR.npy2jpg(reconstructed_imageHR)
                jpg_img.save(Jimg_path)

                self.display_Jimg(Jimg_path)
                self.captureHRButton.setEnabled(True)
                self.statusLabel.setText("HR Mode Completed")
                QApplication.processEvents()
            else:
                self.captureHRButton.setEnabled(True)
                self.statusLabel.setText("HR Mode Completed")
                QApplication.processEvents()
        else:
            progress = "HR: " + info + "/63"
            self.statusLabel.setText(progress)
            QApplication.processEvents()
    
    def capture_TL(self):

        self.statusLabel.setText("Capture TL Mode")
        self.timelapseButton.setEnabled(False)
        QApplication.processEvents()
        path = self.folderText.text()
        self.check_and_create_folder(path)
        exposure_time = self.exposureText.text()
        shared_folder = self.shared_folder_path(path)
        total_time = self.totalText.text()
        interval_time = self.intervalText.text()
        information = [shared_folder, exposure_time, total_time, interval_time]
        if self.PSRBox.isChecked():
            app_path = os.path.abspath(__file__)
            app_directory = os.path.dirname(app_path)
            shift_map_path = app_directory + "/shift_map.npy"
            if not os.path.exists(shift_map_path):
                self.show_warning("Use 'Capture HR Image' To Obtain a Shift Map")
                self.timelapseButton.setEnabled(True)
                QApplication.processEvents()
                return
        clientWin.emit('captureTL', {'folderTL':information})

    def process_TL_image(self,msg):

        info = msg.get('completedTL', 'No info provided')
        total_time = int(self.totalText.text())*60
        interval_time = int(self.intervalText.text())
        num_set = round(total_time/interval_time)
        if info == "Capture Done":
            if self.PSRBox.isChecked():
                self.statusLabel.setText("TL Final Processing...")
                QApplication.processEvents()
                scale_factor = 4
                file_name_list = list(np.arange(17, 22)) + list(np.arange(25, 30)) + \
                                list(np.arange(33, 38)) + list(np.arange(41, 46)) + \
                                list(np.arange(49, 54))
                app_path = os.path.abspath(__file__)
                app_directory = os.path.dirname(app_path)
                shift_map_path = app_directory + "/shift_map.npy"
                shift_map = np.load(shift_map_path)
                focus = self.startZText.text()
                for n in range(num_set+1):
                    HR_raw_path = self.folderText.text() + '/' + str(n) + '/HR_raw.npy'
                    if not os.path.exists(HR_raw_path):                
                        frames = []
                        for i in range(len(file_name_list)):
                            file_path = self.folderText.text() + '/' + str(n) + '/' + str(file_name_list[i]) + ".dng"
                            img = PSR.largest_FOV(file_path)
                            frames.append(img)
                        frames = np.array(frames)
                        frame_size = len(file_name_list)
                                    
                        HR_img = PSR.superResolution(frames, shift_map, frame_size, scale_factor)
                        HR_path = self.folderText.text() + '/' + str(n) + '/' + "HR_raw.npy"
                        np.save(HR_path, HR_img)

                        background_path = self.folderText.text()  + "/0/HR_raw.npy"
                        background = np.load(background_path)
                        HR_img -= background

                        if not focus:
                            reconstructed_image, optimized_zs = PSR.imageReconstruction_unknownZ(frames[12,:,:])
                            optimized_zs_HR = optimized_zs*scale_factor**2
                            reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,optimized_zs_HR,1,1)
                            self.startZText.setText(str(round(optimized_zs**10**6)))
                        else:
                            if int(focus) < 1000:
                                optimized_zs_HR = int(focus)*10**-6*scale_factor**2
                                reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,optimized_zs_HR,1,1)
                                self.startZText.setText(str(round(optimized_zs**10**6)))
                            else:
                                reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,int(focus)*10**-6,0,1)

                        imgHR_path = self.folderText.text() + str(n) + "/HR_reconstructed.npy"
                        np.save(imgHR_path, reconstructed_imageHR)
                        Jimg_path = self.folderText.text() + str(n) + "/HR_reconstructed.jpg"
                        jpg_img = PSR.npy2jpg(reconstructed_imageHR)
                        jpg_img.save(Jimg_path)


                self.timelapseButton.setEnabled(True)
                self.statusLabel.setText("TL Mode Completed")
                QApplication.processEvents()
            else:
                self.timelapseButton.setEnabled(True)
                self.statusLabel.setText("TL Mode Completed")
                QApplication.processEvents()

        else:
            progress = "TL: " + info + f"/{str(num_set)}"
            self.statusLabel.setText(progress)
            QApplication.processEvents()
            if self.PSRBox.isChecked():
                subfolder_path = self.folderText.text() + '/' + str(info) + '/'
                focus = self.startZText.text()
                self.TL_image_processing([subfolder_path,info,focus])
            
    def TL_image_processing(self,subfolder_path):
        if self.ready_process:
            self.ready_process = False
            self.image_processing_thread = ImageProcessingThread(subfolder_path, self.processed_image_callback)
            self.image_processing_thread.processed_image_signal.connect(self.processed_image_callback)
            self.image_processing_thread.start()
        else:
            return
    
    def processed_image_callback(self, info_list):
        self.ready_process = True
        self.communicate.update_image_signal.emit(info_list)


    def messageLR_from_server(self, msg):

        LRpath = msg.get('LRpath', 'No path provided')
        path_focus = re.split(r'(\d+)$', LRpath)
        folder = self.folderText.text()
        file_path = folder + path_focus[0]

        if not os.path.exists(file_path):
            response_message = "File Not Found"
        else:
            time.sleep(6)
            fov = PSR.largest_FOV(file_path)
            if len(path_focus) > 1:
                reconstructed_image, ToG, optimized_zs = PSR.imageReconstruction(fov,int(path_focus[1])*10**-6,0,1)
                img_path = file_path[:-3] + "npy"
                Jimg_path = file_path[:-3] + "jpg"
                np.save(img_path, reconstructed_image)
                jpg_img = PSR.npy2jpg(reconstructed_image)
                jpg_img.save(Jimg_path)
            else:
                reconstructed_image, optimized_zs = PSR.imageReconstruction_unknownZ(fov)
                img_path = file_path[:-3] + "npy"
                Jimg_path = file_path[:-3] + "jpg"
                np.save(img_path, reconstructed_image)
                jpg_img = PSR.npy2jpg(reconstructed_image)
                jpg_img.save(Jimg_path)

        response_message = str(int(round(optimized_zs*10**6)))
        clientWin.emit('responseLR', {'focusLR': response_message})
        print(f"Sent response back to server: {response_message}")

    def messageHR_from_server(self, msg):

        HRpath = msg.get('HRpath', 'No path provided')
        path_focus = re.split(r'(\d+)$', HRpath)
        folder = self.folderText.text()
        folder_path = folder + path_focus[0]

        scale_factor = 4
        file_name_list = list(np.arange(17, 22)) + list(np.arange(25, 30)) + \
                         list(np.arange(33, 38)) + list(np.arange(41, 46)) + \
                         list(np.arange(49, 54))
        frames = []
        for i in range(len(file_name_list)):
            file_path = folder_path + str(file_name_list[i]) + ".dng"
            img = PSR.largest_FOV(file_path)
            frames.append(img)
        frames = np.array(frames)
        frame_size = len(file_name_list)

        app_path = os.path.abspath(__file__)
        app_directory = os.path.dirname(app_path)
        background_path = app_directory + "/background.npy"
        shift_map_path = app_directory + "/shift_map.npy"
        shift_map_path2 = folder_path + "shift_map.npy"
        if os.path.exists(shift_map_path):
            shift_map = np.load(shift_map_path)
            np.save(shift_map_path2,shift_map)
        else:
            shift_map = PSR.shiftMap(frames,frame_size)
            np.save(shift_map_path,shift_map)
            np.save(shift_map_path2,shift_map)
                    
        HR_img = PSR.superResolution(frames, shift_map, frame_size, scale_factor)
        HR_path = folder_path + "HR_raw.npy"
        np.save(HR_path, HR_img)

        if os.path.exists(background_path):
            background = np.load(background_path)
            HR_img -= background
        if len(path_focus) > 1:
            focus_z = path_focus[1]
            if focus_z < 1000:
                optimized_zs_HR = int(focus_z)*10**-6*scale_factor**2
                reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,optimized_zs_HR,1,1)
            else:
                reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,int(focus_z)*10**-6,0,1)
        else:
            reconstructed_image, optimized_zs = PSR.imageReconstruction_unknownZ(frames[12,:,:])
            optimized_zs_HR = optimized_zs*scale_factor**2
            reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,optimized_zs_HR,1,1)

        imgHR_path = folder_path + "HR_reconstructed.npy"
        np.save(imgHR_path, reconstructed_imageHR)
        Jimg_path = folder_path + "HR_reconstructed.jpg"
        jpg_img = PSR.npy2jpg(reconstructed_imageHR)
        jpg_img.save(Jimg_path)

        response_message = str(int(round(optimized_zs*10**6)))
        clientWin.emit('responseHR', {'focusHR': response_message})
        print(f"Sent response back to server: {response_message}")

    def messageTL_from_server(self, msg):

        TLpath = msg.get('TLpath', 'No path provided')
        path_focus = re.split(r'(\d+)$', TLpath)
        folder = self.folderText.text()
        folder_path = folder + path_focus[0]

        fullfolder_path = folder_path
        fullfolder_path = fullfolder_path[:-1]
        folder_subfolder = re.split(r'(\d+)$', fullfolder_path)
        print(TLpath)

        app_path = os.path.abspath(__file__)
        app_directory = os.path.dirname(app_path)
        shift_map_path = app_directory + "/shift_map.npy"
        if not os.path.exists(shift_map_path):
            clientWin.emit('responseHR', {'folderTL': "file: 404"})
            print(f"Sent response back to server: {"file: 404"}")
            return

        scale_factor = 4
        file_name_list = list(np.arange(17, 22)) + list(np.arange(25, 30)) + \
                         list(np.arange(33, 38)) + list(np.arange(41, 46)) + \
                         list(np.arange(49, 54))
        frames = []
        for i in range(len(file_name_list)):
            file_path = folder_path + str(file_name_list[i]) + ".dng"
            img = PSR.largest_FOV(file_path)
            frames.append(img)
        frames = np.array(frames)
        frame_size = len(file_name_list)
                    
        shift_map = np.load(shift_map_path)
        HR_img = PSR.superResolution(frames, shift_map, frame_size, scale_factor)
        HR_path = folder_path + "HR_raw.npy"
        np.save(HR_path, HR_img)

        #if int(folder_subfolder[1]) > 0:
        #    background_path = folder_subfolder[0] + "0/HR_raw.npy"
        #    background = np.load(background_path)
        #    HR_img -= background

        if len(path_focus) > 1:
            focus_z = path_focus[1]
            if focus_z < 1000:
                optimized_zs_HR = int(focus_z)*10**-6*scale_factor**2
                reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,optimized_zs_HR,1,1)
            else:
                reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,int(focus_z)*10**-6,0,1)
        else:
            reconstructed_image, optimized_zs = PSR.imageReconstruction_unknownZ(frames[12,:,:])
            optimized_zs_HR = optimized_zs*scale_factor**2
            reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,optimized_zs_HR,1,1)

        imgHR_path = folder_path + "HR_reconstructed.npy"
        np.save(imgHR_path, reconstructed_imageHR)
        Jimg_path = folder_path + "HR_reconstructed.jpg"
        jpg_img = PSR.npy2jpg(reconstructed_imageHR)
        jpg_img.save(Jimg_path)

        folder_path = folder_path[:-1]
        folder_subfolder = re.split(r'(\d+)$', folder_path)

        response_message = str(folder_subfolder[1])
        clientWin.emit('responseTL', {'folderTL': response_message})
        print(f"Sent response back to server: {response_message}")
    
    def messageFTL_from_server(self, msg):

        FTLpath = msg.get('FTLpath', 'No path provided')
        path_focus = re.split(r'(\d+)$', FTLpath)
        folder = self.folderText.text()
        folder_path = folder + path_focus[0]
        fullfolder_path = folder_path[:-1]
        main_sub = re.split(r'(\d+)$', fullfolder_path)
        num_set = main_sub[1]

        app_path = os.path.abspath(__file__)
        app_directory = os.path.dirname(app_path)
        shift_map_path = app_directory + "/shift_map.npy"
        shift_map = np.load(shift_map_path)

        scale_factor = 4
        file_name_list = list(np.arange(17, 22)) + list(np.arange(25, 30)) + \
                         list(np.arange(33, 38)) + list(np.arange(41, 46)) + \
                         list(np.arange(49, 54))

        for n in range(int(num_set)+1):
            HR_raw_path = main_sub[0] + str(n) + '/HR_raw.npy'
            if not os.path.exists(HR_raw_path):
                
                frames = []
                for i in range(len(file_name_list)):
                    file_path = main_sub[0] + str(n) + '/' + str(file_name_list[i]) + ".dng"
                    img = PSR.largest_FOV(file_path)
                    frames.append(img)
                frames = np.array(frames)
                frame_size = len(file_name_list)
                            
                HR_img = PSR.superResolution(frames, shift_map, frame_size, scale_factor)
                HR_path = main_sub[0] + str(n) + "HR_raw.npy"
                np.save(HR_path, HR_img)

                if len(path_focus) > 1:
                    focus_z = path_focus[1]
                    if focus_z < 1000:
                        optimized_zs_HR = int(focus_z)*10**-6*scale_factor**2
                        reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,optimized_zs_HR,1,1)
                    else:
                        reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,int(focus_z)*10**-6,0,1)
                else:
                    reconstructed_image, optimized_zs = PSR.imageReconstruction_unknownZ(frames[12,:,:])
                    optimized_zs_HR = optimized_zs*scale_factor**2
                    reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,optimized_zs_HR,1,1)

                imgHR_path = main_sub[0] + str(n) + "/HR_reconstructed.npy"
                np.save(imgHR_path, reconstructed_imageHR)
                Jimg_path = main_sub[0] + str(n) + "/HR_reconstructed.jpg"
                jpg_img = PSR.npy2jpg(reconstructed_imageHR)
                jpg_img.save(Jimg_path)

        clientWin.emit('responseFTL', {'msgFTL': "Completed"})
        print(f"Sent response back to server: {"Completed"}")

    def show_LR(self):

        self.statusLabel.setText("Display LR Image")
        QCoreApplication.processEvents()

        file_name = self.fileNameText.text()
        if not file_name or not file_name.endswith(".dng"):
            file_path = self.folderText.text() + "/26.dng"
        else:
            file_path = self.folderText.text() + "/" + file_name
        
        if not os.path.exists(file_path):
            self.show_warning = "No File Found"
            return
        
        img = PSR.loadImg(file_path)
        green_img = PSR.extraGreenChannel(img)
        green_img_u8 = (green_img / (2**10 - 1) * 255).astype(np.uint8)
        adjust_img = PSR.imadjust(green_img_u8, gamma=1.0)
        height, width = adjust_img.shape
        bytes_per_line = width
        q_image = QImage(adjust_img.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        pixmap = QPixmap.fromImage(q_image)
        self.display.setPixmap(pixmap)
        self.display.setScaledContents(True)
    
    def show_HR(self):

        self.statusLabel.setText("Display HR Image")
        QCoreApplication.processEvents()

        npyfile_path = self.folderText.text() + "/HR_raw.npy"
        
        if not os.path.exists(npyfile_path):
            self.statusLabel.setText("PSR Processing......")
            QCoreApplication.processEvents()

            scale_factor = 4
            file_name_list = list(np.arange(17, 22)) + list(np.arange(25, 30)) + \
                            list(np.arange(33, 38)) + list(np.arange(41, 46)) + \
                            list(np.arange(49, 54))
            
            frames = []
            for i in range(len(file_name_list)):
                file_path = self.folderText.text() + "/" + str(file_name_list[i]) + ".dng"
                img = PSR.largest_FOV(file_path)
                frames.append(img)
            frames = np.array(frames)
            frame_size = len(file_name_list)

            shift_map = PSR.shiftMap(frames,frame_size)
            HR_img = PSR.superResolution(frames, shift_map, frame_size, scale_factor)
            HR_path = self.folderText.text() + "/HR_raw.npy"
            np.save(HR_path, HR_img)

            HR_img_u8 = (HR_img / (2**10 - 1) * 255).astype(np.uint8)
            image = Image.fromarray(HR_img_u8)
            img_path = self.folderText.text() + "/HR_raw.jpg"
            image.save(img_path, 'JPEG')
            adjust_img = PSR.imadjust(HR_img_u8, gamma=1.0)

            self.statusLabel.setText("PSR Image Saved")
            QCoreApplication.processEvents()

        else:
            img = np.load(npyfile_path)
            img_u8 = (img / (2**10 - 1) * 255).astype(np.uint8)
            adjust_img = PSR.imadjust(img_u8, gamma=1.0)
        
        height, width = adjust_img.shape
        bytes_per_line = width
        q_image = QImage(adjust_img.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        pixmap = QPixmap.fromImage(q_image)
        self.display.setPixmap(pixmap)
        self.display.setScaledContents(True)

    def focus_LR(self):

        self.statusLabel.setText("LR Focusing...")
        QCoreApplication.processEvents()

        file_name = self.fileNameText.text()
        if not file_name or not file_name.endswith(".dng"):
            file_path = self.folderText.text() + "/26.dng"
        else:
            file_path = self.folderText.text() + "/" + file_name
        
        if not os.path.exists(file_path):
            self.show_warning = "No File Found"
            return
        
        z_start = self.startZText.text()
        z_step = self.stepZText.text()
        iteration = self.iterationText.text()
        time.sleep(6)
        fov = PSR.largest_FOV(file_path)
        reconstructed_image, ToG, optimized_zs = PSR.imageReconstruction(fov,int(z_start)*10**-6,int(z_step)*10**-6,int(iteration))
        self.startZText.setText(str(round(optimized_zs**10**6)))
        focused_path = file_path[:-4] + "_reconstructed.npy"
        np.save(focused_path, reconstructed_image)
        
        reconstructed_image_u8 = (reconstructed_image / (2**10 - 1) * 255).astype(np.uint8)
        image = Image.fromarray(reconstructed_image_u8)
        img_path = file_path[:-4] + "_reconstructed.jpg"
        image.save(img_path, 'JPEG')
        adjust_img = PSR.imadjust(reconstructed_image_u8, gamma=1.0)
        height, width = adjust_img.shape
        bytes_per_line = width
        q_image = QImage(adjust_img.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        pixmap = QPixmap.fromImage(q_image)
        self.display.setPixmap(pixmap)
        self.display.setScaledContents(True)

        self.statusLabel.setText("Focused LR")
        QCoreApplication.processEvents()

    def focus_HR(self):

        self.statusLabel.setText("HR Focusing...")
        QCoreApplication.processEvents()

        file_path = self.folderText.text() + "/HR_raw.npy"
        
        if not os.path.exists(file_path):
            self.show_warning("No File Found")
            return
        
        HR_img = np.load(file_path)
        z_start = self.startZText.text()
        z_step = self.stepZText.text()
        iteration = self.iterationText.text()
        scale_factor = 4

        if not z_start:
            self.show_warning("Please Enter A Starting Z")
            return
        else:
            if int(z_start) < 500:
                optimized_zs_HR = int(z_start)*10**-6*scale_factor**2
                reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,int(optimized_zs_HR)*10**-6,int(z_step)*10**-6,int(iteration))
                self.startZText.setText(str(round(optimized_zs**10**6)))
            else:
                reconstructed_imageHR, ToG, optimized_zs = PSR.imageReconstruction(HR_img,int(z_start)*10**-6,int(z_step)*10**-6,int(iteration))
                self.startZText.setText(str(round(optimized_zs**10**6)))

        focused_path = self.folderText.text() + "/HR_reconstructed.npy"
        np.save(focused_path, reconstructed_imageHR)
        
        reconstructed_image_u8 = (reconstructed_imageHR / (2**10 - 1) * 255).astype(np.uint8)
        image = Image.fromarray(reconstructed_image_u8)
        img_path = self.folderText.text() + "/HR_reconstructed.jpg"
        image.save(img_path, 'JPEG')
        adjust_img = PSR.imadjust(reconstructed_image_u8, gamma=1.0)
        height, width = adjust_img.shape
        bytes_per_line = width
        q_image = QImage(adjust_img.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        pixmap = QPixmap.fromImage(q_image)
        self.display.setPixmap(pixmap)
        self.display.setScaledContents(True)


    def all_PSR(self):

        self.statusLabel.setText("Processing...")
        self.allPSRButton.setEnabled(False)
        QCoreApplication.processEvents()

        total_frame = int(self.frameText.text())
        
        for n in range(total_frame+1):

            current_process = "Processing: " + str(n) + "/" + self.frameText.text()
            self.statusLabel.setText(current_process)
            QCoreApplication.processEvents()

            HR_path = self.folderText.text() + "/" + str(n) + "/HR_raw.npy"
            HR_img = np.load(HR_path)
            HR_section = HR_img[50:-50,50:-50]
            z_start = int(self.startZText.text())*10**-6
            reconstructed_image, ToG, optimized_zs = PSR.imageReconstruction(HR_section, z_start, 0, 1)
            HR_rec_path = self.folderText.text() + "/" + str(n) + "/HR_reconstructed.npy"
            np.save(HR_rec_path, reconstructed_image)

            reconstructed_image_u8 = (reconstructed_image / (2**10 - 1) * 255).astype(np.uint8)
            image = Image.fromarray(reconstructed_image_u8)
            img_path = self.folderText.text() + "/" + self.folderText_2.text() + "/HR_reconstructed.jpg"
            image.save(img_path, 'JPEG')
            adjust_img = PSR.imadjust(reconstructed_image_u8, gamma=1.0)
            adjust_img = np.ascontiguousarray(adjust_img)
            height, width = adjust_img.shape
            bytes_per_line = width
            q_image = QImage(adjust_img.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
            pixmap = QPixmap.fromImage(q_image)
            self.displayLabel.setPixmap(pixmap)
            self.displayLabel.setScaledContents(True)

        self.statusLabel.setText("All PSR Image Saved")
        self.allPSRButton.setEnabled(True)
        QCoreApplication.processEvents()

    def write_Video(self):

        self.statusLabel.setText("Writing Video...")
        self.videoButton.setEnabled(False)
        QCoreApplication.processEvents()

        total_frame = int(self.frameText.text())
        crop_size = 620

        for i in range(total_frame + 1):

            current_process = "Frames: " + str(i) + "/" + self.frameText.text()
            self.statusLabel.setText(current_process)
            QCoreApplication.processEvents()

            if i == 0:
                reference_HR = self.folderText.text() + "/" + str(i) + "/HR_raw.npy" 
                if os.path.exists(reference_HR):
                    reference_img = np.load(reference_HR)
                    reference_section = reference_img[crop_size:-crop_size,crop_size:-crop_size]
                    height, width = reference_section.shape
                    fps = 10
                    fourcc = cv2.VideoWriter_fourcc(*"MJPG") 
                    output_path = self.folderText.text() + "/output_video.avi"
                    output_video = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
                    z_start = int(self.startZText.text())*10**-6
                    reconstructed_image, ToG, optimized_zs = PSR.imageReconstruction(reference_section, z_start, 0, 1)
                    reconstructed_image_u8 = (reconstructed_image / (2**10 - 1) * 255).astype(np.uint8)
                    frame_rgb = cv2.cvtColor(reconstructed_image_u8, cv2.COLOR_GRAY2BGR)
                    output_video.write(frame_rgb)
                    total_shift = [0,0]
                else:
                    self.show_warning()
            else:
                reference_HR = self.folderText.text() + "/" + str(i-1) + "/HR_raw.npy" 
                HR_path = self.folderText.text() + "/" + str(i) + "/HR_raw.npy" 
                if os.path.exists(HR_path):
                    reference_img = np.load(reference_HR)
                    reference_section = reference_img[crop_size:-crop_size,crop_size:-crop_size]
                    HR_img = np.load(HR_path)
                    HR_section = HR_img[crop_size:-crop_size,crop_size:-crop_size]
                    shift, error, diffphase = phase_cross_correlation(HR_section, reference_section)
                    total_shift += shift
                    align_section = HR_img[int(np.round(crop_size+total_shift[0])):int(np.round(-crop_size+total_shift[0])),int(np.round(crop_size+total_shift[1])):int(np.round(-crop_size+total_shift[1]))]
                    z_start = int(self.startZText.text())*10**-6
                    reconstructed_image, ToG, optimized_zs = PSR.imageReconstruction(align_section, z_start, 0, 1)
                    reconstructed_image_u8 = (reconstructed_image / (2**10 - 1) * 255).astype(np.uint8)
                    frame_rgb = cv2.cvtColor(reconstructed_image_u8, cv2.COLOR_GRAY2BGR)
                    output_video.write(frame_rgb)
                else:
                    self.show_warning()

        output_video.release()
        self.statusLabel.setText("Video Saved.")
        QCoreApplication.processEvents()

    def shared_folder_path(self,path):
        
        folders = path.split('/')
        if len(folders) > 1:
            return '/'+'/'.join(folders[1:])+'/'
        else:
            return '/'
        
    def check_and_create_folder(self,folder_path):

        if not os.path.exists(folder_path):

            os.makedirs(folder_path, exist_ok=True)

    def display_Jimg(self,path):
        
        q_image = QImage(path)
        pixmap = QPixmap.fromImage(q_image)
        self.display.setPixmap(pixmap)
        self.display.setScaledContents(True)

    def display_output(self,info_list):
        
        path = info_list[0]
        print(info_list)
        focus = info_list[1]
        current_set = info_list[2]
        current_time = int(self.intervalText.text())*int(current_set)
        q_image = QImage(path)
        pixmap = QPixmap.fromImage(q_image)
        self.display.setPixmap(pixmap)
        self.display.setScaledContents(True)
        self.imageTimeLabel.setText(f"Image Time: {str(current_time)} min")
        self.startZText.setText(str(focus))
        
    def show_warning(self,warning):

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Warning")
        msg.setText("This is a warning message!")
        msg.setInformativeText(str(warning))
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ClientApp()
    window.show()
    sys.exit(app.exec_())