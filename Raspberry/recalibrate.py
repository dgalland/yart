import picamera.array
import picamera
import numpy as np
import sys
import time
from fractions import Fraction
#import cv2

def lens_shading_correction_from_rgb(rgb_array, binsize, version):
    """Calculate a correction to a lens shading table from an RGB image.
    
    Returns:
        a floating-point table of gains that should multiply the current
        lens shading table.
    """
    full_resolution = rgb_array.shape[:2]
    table_resolution = [(r // binsize) + 1 for r in full_resolution]
    lens_shading = np.zeros([4] + table_resolution, dtype=np.float)
    
    for i in range(3):
        # We simplify life by dealing with only one channel at a time.
        image_channel = rgb_array[:,:,i]
        iw, ih = image_channel.shape
        ls_channel = lens_shading[int(i*1.6),:,:] # NB there are *two* green channels
        lw, lh = ls_channel.shape
        # The lens shading table is rounded **up** in size to 1/64th of the size of
        # the image.  Rather than handle edge images separately, I'm just going to
        # pad the image by copying edge pixels, so that it is exactly 32 times the
        # size of the lens shading table (NB 32 not 64 because each channel is only
        # half the size of the full image - remember the Bayer pattern...  This
        # should give results very close to 6by9's solution, albeit considerably 
        # less computationally efficient!
        dw = lw*binsize - iw
        dh = lh*binsize - ih
        if version == 2 :
#            image_channel[iw-8:iw:1,:] = np.mean(image_channel[iw-16:iw-8:,:],axis=0)  #bottom  adjust verify !
            padded_image_channel = np.pad(image_channel, [(0, dw), (0, dh)], mode='edge') # Pad image to the right and bottom
        else :
#            image_channel[iw-8:iw:1,:] = np.mean(image_channel[iw-16:iw-8:,:],axis=0)
            padded_image_channel = np.pad(image_channel, [(dw, 0), (dh, 0)], mode='edge') # Pad image top left
        assert padded_image_channel.shape == (lw*binsize, lh*binsize), "padding problem"
        # Next, fill the shading table (except edge pixels).  Please excuse the
        # for loop - I know it's not fast but this code needn't be!
        box = 3 # We average together a square of this side length for each pixel.
        # NB this isn't quite what 6by9's program does - it averages 3 pixels
        # horizontally, but not vertically.
        for dx in np.arange(box) - box//2:
            for dy in np.arange(box) - box//2:
                ls_channel[:,:] += padded_image_channel[binsize//2+dx::binsize,binsize//2+dy::binsize]   
        ls_channel /= box**2
        # Everything is normalised relative to the centre value.  I follow 6by9's
        # example and average the central 64 pixels in each channel.
        channel_centre = np.mean(image_channel[iw//2-4:iw//2+4, ih//2-4:ih//2+4])
        ls_channel /= channel_centre
        print("channel {} centre brightness {}".format(i, channel_centre))
        # NB the central pixel should now be *approximately* 1.0 (may not be exactly
        # due to different averaging widths between the normalisation & shading table)
        # For most sensible lenses I'd expect that 1.0 is the maximum value.
        # NB ls_channel should be a "view" of the whole lens shading array, so we don't
        # need to update the big array here.
        print("min {}, max {}".format(ls_channel.min(), ls_channel.max()))
    # What we actually want to calculate is the gains needed to compensate for the 
    # lens shading - that's 1/lens_shading_table_float as we currently have it.
    lens_shading[2,...] = lens_shading[1,...] # Duplicate the green channels
    gains = 1.0/lens_shading # 32 is unity gain
    print('Max:', np.max(gains), ' Min:', np.min(gains))
    return gains

def gains_to_lst(gains):
    """Given a lens shading gains table (where no gain=1.0), convert to 8-bit."""
    lst = gains / np.min(gains)*32 # minimum gain is 32 (= unity gain)
    lst[lst > 255] = 255 # clip at 255
    return lst.astype(np.uint8)

##def get_rgb_image(camera):
##    with picamera.array.PiRGBArray(camera) as output:
##        camera.capture(output, format='rgb', use_video_port=True)
##        return output.array

def get_rgb_image(camera, resize):
    with picamera.array.PiRGBArray(camera, size=resize) as output:
        camera.capture(output, format='rgb', resize=resize, use_video_port=True)
        return output.array

def get_bgr_image(camera, resize):
    with picamera.array.PiRGBArray(camera, size=resize) as output:
        camera.capture(output, format='bgr', resize=resize, use_video_port=True)
        return output.array

def freeze_camera_settings(camera):
    camera.awb_mode = "auto"
    camera.exposure_mode = "auto"
    time.sleep(5)
    camera.shutter_speed = camera.exposure_speed
#    camera.exposure_mode = "off"
    g = camera.awb_gains
    camera.awb_mode = "off"
    camera.awb_gains = g
    print('Gains:', camera.awb_gains,' Shutter:', camera.exposure_speed)
    time.sleep(5)


def generate_lens_shading_table_closed_loop(hflip, vflip, n_iterations=5, images_to_average=5):

    camera = picamera.PiCamera(sensor_mode=2)
    lens_shading_table = np.zeros(camera._lens_shading_table_shape(), dtype=np.uint8) + 32
    gains = np.ones_like(lens_shading_table, dtype=np.float)
    max_res = camera.MAX_RESOLUTION
    if max_res[0] == 3280 :
        calibrate_res = (max_res[0]//2, max_res[1]//2)
        binSize = 32
        version = 2
    else :
        version = 1
        binSize = 64
        calibrate_res = max_res
    time.sleep(2)
    camera.close()
    
    camera = picamera.PiCamera(sensor_mode=2,lens_shading_table=lens_shading_table, resolution=calibrate_res)
    if version == 1 :
        camera.hflip = True
        camera.vflip = True
    freeze_camera_settings(camera)

    for i in range(n_iterations):
        print("Optimising lens shading, pass {}/{}".format(i+1, n_iterations))
        rgb_image  = get_rgb_image(camera, calibrate_res).astype(dtype=np.float)
        for j in range(images_to_average - 1):
            rgb_image = rgb_image + get_rgb_image(camera, calibrate_res)
        rgb_image = rgb_image / images_to_average
        incremental_gains = lens_shading_correction_from_rgb(rgb_image, binSize, version)
        gains *= incremental_gains#**0.8
        # Apply this change (actually apply a bit less than the change)
        camera.lens_shading_table = gains_to_lst(gains*32)
        time.sleep(2)
   
    lens_shading_table = camera.lens_shading_table
    camera.close()
    return lens_shading_table


if __name__ == '__main__':
    camera = picamera.PiCamera(sensor_mode=2)
    camera.resolution = camera.MAX_RESOLUTION
    time.sleep(2)
    print('Before Shutter:', camera.exposure_speed, ' Gains:', camera.awb_gains)
    camera.capture('before.jpg', use_video_port=True)
##    bgr = get_bgr_image(camera, camera.MAX_RESOLUTION)
##    cv2.imwrite('before_bgr.jpg', bgr)
    camera.close()
    lens_shading_table = generate_lens_shading_table_closed_loop(False,False, n_iterations=2)
    np.savez('calibrate.npz',   lens_shading_table = lens_shading_table)
    
    camera = picamera.PiCamera(lens_shading_table=lens_shading_table)
    camera.resolution = camera.MAX_RESOLUTION
    time.sleep(2)


##    bgr = get_bgr_image(camera, camera.MAX_RESOLUTION)
##    cv2.imwrite('after_bgr.jpg', bgr)
##    print(np.mean(lens_shading_table))
##    table = (lens_shading_table *8.).astype(np.uint8)
##    b = table[0,:,:]
##    g1 = table[1,:,:]
##    g2 = table[2,:,:]
##    r = table[3,:,:]
##    cv2.imwrite('lens_b.jpg', b)
##    cv2.imwrite('lens_g1.jpg', g1)
##    cv2.imwrite('lens_g2.jpg', g2)
##    cv2.imwrite('lens_r.jpg', r)
    
    print('After Shutter:', camera.exposure_speed, ' Gains:', camera.awb_gains)
    camera.hflip=False
    camera.vflip=False
    time.sleep(1)
    camera.capture('after_f_f.jpg',use_video_port=True)
    camera.hflip=True
    time.sleep(1)
    camera.capture('after_t_f.jpg',use_video_port=True)
    camera.vflip=True
    time.sleep(1)
    camera.capture('after_t_t.jpg',use_video_port=True)
    camera.hflip=False
    camera.vflip=True
    time.sleep(1)
    camera.capture('after_f_t.jpg',use_video_port=True)
    
    
