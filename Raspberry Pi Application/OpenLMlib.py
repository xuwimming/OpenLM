import rawpy
import numpy as np
from skimage import exposure
from scipy import ndimage
from image_registration import chi2_shift
from PIL import Image
from skimage.restoration import inpaint

def loadImg(path):

    raw_im = rawpy.imread(path)
    np_im = np.int_(raw_im.raw_image)

    return np_im

def largest_FOV(path):

    raw_im = rawpy.imread(path)
    green_frame = extraGreenChannel(np.int_(raw_im.raw_image))
    height, width = green_frame.shape
    section = green_frame[:, 408:height + 408]
    rotate = rotate45(section)        
    fov = rotate[616:-616, 616:-617]
    
    return fov

def extraGreenChannel(image):

    green_channel_image = np.zeros(image.shape)
    green_channel_image[0::2, 1::2] = image[0::2, 1::2]
    green_channel_image[1::2, 0::2] = image[1::2, 0::2]
    return green_channel_image

def rotate45(image):

    height, width = image.shape
    new_height = np.int_((height/2)+(width/2)-1)
    new_width = min(height, width)
    rotated_image = np.zeros((new_height,new_width))
    image_flip = np.fliplr(image)
    digonal_list_width = [x*2 for x in range(width)]
    digonal_list_height = [-x*2 for x in range(height)]
    num_blocks_width = np.int_(width/2)
    num_blocks_height = np.int_(height/2)
    for i in range(num_blocks_width):
        current_row = np.diagonal(image_flip,digonal_list_width[i])
        num_zero = np.int_((new_width - len(current_row))/2)
        rotated_image[num_blocks_width-1-i,num_zero:(new_width-num_zero)] = current_row

    for j in range(num_blocks_height):
        current_row = np.diagonal(image_flip,digonal_list_height[j])
        num_zero = np.int_((new_width - len(current_row))/2)
        rotated_image[num_blocks_width+j-1,num_zero:(new_width-num_zero)] = current_row
    
    rotated_image = np.fliplr(rotated_image)
    return rotated_image

def imageReconstruction(hologram,z_start,z_step,iteration):
    
    wavelength = 532*10**-9
    hologram_fft = np.fft.fft2(hologram)
    ny,nx = hologram.shape
    u = np.fft.fftfreq(nx, d = (1.12*np.sqrt(2)*10**-6)) # unit in meter
    v = np.fft.fftfreq(ny, d = (1.12*np.sqrt(2)*10**-6))
    ux, uy = np.meshgrid(u,v)
    ToG= np.zeros(iteration) 
    for i in range(iteration):
        z = z_start + i * z_step
        P = np.exp(1j * z * (2*np.pi/wavelength) * np.sqrt(1-wavelength**2*(ux**2+uy**2)))
        complex_distribution = np.fft.ifft2(hologram_fft * P)
        intensity_distribution = np.abs(complex_distribution)
        sobel_result = np.sqrt((ndimage.sobel(intensity_distribution,-1))**2+(ndimage.sobel(intensity_distribution,0))**2)
        ToG[i] = np.sqrt(ny*nx*sobel_result.std()/sobel_result.sum().sum())
    
    optimized_zs = z_start + np.argmax(ToG) * z_step
    P = np.exp(1j * optimized_zs * (2*np.pi/wavelength) * np.sqrt(1-wavelength**2*(ux**2+uy**2)))
    reconstructed_image = np.abs(np.fft.ifft2(hologram_fft * P))
    
    return reconstructed_image, ToG, optimized_zs

def imageReconstruction_unknownZ_loop(hologram):
    
    wavelength = 532*10**-9
    hologram_fft = np.fft.fft2(hologram)
    ny,nx = hologram.shape
    u = np.fft.fftfreq(nx, d = (1.12*np.sqrt(2)*10**-6)) # unit in meter
    v = np.fft.fftfreq(ny, d = (1.12*np.sqrt(2)*10**-6))
    ux, uy = np.meshgrid(u,v)
    z_start = 500*10**-6
    z_step = 20*10**-6
    iteration = 11
    optimized_zs = angularSpectrum(hologram_fft, iteration, z_start, z_step, wavelength, ux, uy, nx, ny)
    z_start = optimized_zs - z_step + 5*10**-6
    z_step = 5*10**-6
    iteration = 7
    optimized_zs = angularSpectrum(hologram_fft, iteration, z_start, z_step, wavelength, ux, uy, nx, ny)
    z_start = optimized_zs - z_step + 1*10**-6
    z_step = 1*10**-6
    iteration = 9
    optimized_zs = angularSpectrum(hologram_fft, iteration, z_start, z_step, wavelength, ux, uy, nx, ny)
    
    P = np.exp(1j * optimized_zs * (2*np.pi/wavelength) * np.sqrt(1-wavelength**2*(ux**2+uy**2)))
    reconstructed_image = np.abs(np.fft.ifft2(hologram_fft * P))
    
    return reconstructed_image, optimized_zs

def imageReconstruction_unknownZ(hologram):
    
    sections = dividImage(hologram)

    optimized_zs = np.zeros(16)
    for i in range(16):
        reconstructed_image, optimized_z = imageReconstruction_unknownZ_loop(sections[i,:,:])
        optimized_zs[i] = optimized_z

    median_optimized_z = np.median(optimized_zs)

    reconstructed_image, ToG, optimized_zs = imageReconstruction(hologram,median_optimized_z,1,1)

    return reconstructed_image, median_optimized_z

def angularSpectrum(hologram_fft, iteration, z_start, z_step, wavelength, ux, uy, nx, ny):
    
    ToG= np.zeros(iteration) 
    for i in range(iteration):
        z = z_start + i * z_step
        P = np.exp(1j * z * (2*np.pi/wavelength) * np.sqrt(1-wavelength**2*(ux**2+uy**2)))
        complex_distribution = np.fft.ifft2(hologram_fft * P)
        intensity_distribution = np.abs(complex_distribution)
        sobel_result = np.sqrt((ndimage.sobel(intensity_distribution,-1))**2+(ndimage.sobel(intensity_distribution,0))**2)
        ToG[i] = np.sqrt(ny*nx*sobel_result.std()/sobel_result.sum().sum())
    
    optimized_zs = z_start + np.argmax(ToG) * z_step
    
    return optimized_zs

def imadjust(img, gamma=1.0):

    img_float32 = img.astype(np.float32)
    low_in, high_in = np.percentile(img_float32, (2, 98))
    img_normalized = exposure.rescale_intensity(img_float32, in_range=(low_in, high_in), out_range=(0, 1))
    img_adjusted = exposure.adjust_gamma(img_normalized, gamma)
    low_out, high_out = 0, 1
    img_scaled = exposure.rescale_intensity(img_adjusted, in_range=(0, 1), out_range=(low_out, high_out))
    img_scaled = exposure.rescale_intensity(img_scaled, out_range=(0, 255))
    img_scaled = img_scaled.astype(img.dtype)
    
    return img_scaled

def shiftMap(frames,frame_size):

    reference_section = frames[1,:,:]
    scale_factor = 4
    shifts = np.zeros((frame_size,2))
    for i in range(frame_size):
        dx,dy,edx,edy = chi2_shift(reference_section, frames[i,:,:], upsample_factor='auto')
        shifts[i,:] = [dy,dx]

    shift_map = shifts*scale_factor
    return shift_map

def superResolution(frames, shift_map, frame_size, scale_factor):

    reference_section = frames[1,:,:]
    shiftsX_round = -np.round(shift_map[:,1])
    shiftsY_round = -np.round(shift_map[:,0])
    minShiftX = np.min(shiftsX_round)
    minShiftY = np.min(shiftsY_round)

    if minShiftX <= 0:
        shiftsX_round = np.abs(shiftsX_round - minShiftX)
    if minShiftY <= 0:
        shiftsY_round = np.abs(shiftsY_round - minShiftY)

    lry, lrx = reference_section.shape
    initial_guess = np.zeros((lry*scale_factor, lrx*scale_factor))
    for i in range(frame_size):
        current_section = initial_guess[int(shiftsY_round[i])::scale_factor, int(shiftsX_round[i])::scale_factor]
        section_size = current_section.shape
        initial_guess[int(shiftsY_round[i])::scale_factor, int(shiftsX_round[i])::scale_factor] = frames[i, 0:section_size[0], 0:section_size[1]]
    
    initial_guess_2 = initial_guess.copy()
    initial_guess_2[initial_guess_2 == 0] = np.nan

    rows, cols = initial_guess_2.shape
    x_indices = np.arange(cols)
    y_indices = np.arange(rows)

    masked_initial_guess = np.ma.masked_invalid(initial_guess_2)
    filled_initial_guess = inpaint.inpaint_biharmonic(initial_guess_2, masked_initial_guess.mask)

    return filled_initial_guess

def npy2jpg(array):
    
    normalized_array = (array - np.min(array)) / (np.max(array) - np.min(array)) * 255
    normalized_array = np.clip(normalized_array, 0, 255)
    img = Image.fromarray(normalized_array.astype(np.uint8))
    
    return img

def dividImage(image):

    sections_size = 308
    overlap = 20
    num_sections = 16 

    # Collecting the squares
    sections = []
    for i in range(0, 1231 - sections_size + 1, sections_size - overlap):
        for j in range(0, 1231 - sections_size + 1, sections_size - overlap):
            section = image[i:i+sections_size, j:j+sections_size]
            sections.append(section)
            if len(sections) == num_sections:
                break
        if len(sections) == num_sections:
            break

    sections = np.array(sections)

    return sections
