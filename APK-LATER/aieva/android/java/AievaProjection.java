package org.aieva;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.ImageFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Handler;
import android.os.HandlerThread;
import android.util.DisplayMetrics;
import android.view.WindowManager;

import java.nio.ByteBuffer;
import java.util.Arrays;

/**
 * The screen capture of an Android smart board.
 *
 * <p>It is called from Python (python-for-android / pyjnius):
 *
 * <pre>
 *   AievaProjection.isAvailable()
 *   AievaProjection.start()        # asks the teacher for the permission
 *   AievaProjection.isStarted()
 *   AievaProjection.grabFrame()    # the newest picture (PNG bytes)
 *   AievaProjection.stop()
 * </pre>
 *
 * <p>The permission can only be given by a person: Android shows a dialog
 * ("Aieva wants to record the screen"), the teacher taps "Allow" once.
 *
 * <p><b>Honest:</b> this helper has not been run on a physical board yet -
 * it is written against the Android API of Android 5.0 (API 21) and newer
 * and still has to prove itself on the device.
 */
public class AievaProjection {

    private static final int REQUEST_CODE = 4242;
    private static final int VIRTUAL_DISPLAY_FLAGS =
            DisplayManager.VIRTUAL_DISPLAY_FLAG_PUBLIC
                    | DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR;

    private static MediaProjection projection;
    private static VirtualDisplay virtualDisplay;
    private static ImageReader imageReader;
    private static HandlerThread thread;
    private static Handler handler;
    private static byte[] lastFrame;

    private AievaProjection() {
    }

    /** Is the screen capture possible on this device? */
    public static boolean isAvailable() {
        try {
            Context context = getContext();
            return context != null && getManager(context) != null;
        } catch (Throwable error) {
            return false;
        }
    }

    /**
     * Asks for the permission and starts the projection.
     *
     * @return true when the projection runs (the teacher said yes)
     */
    public static boolean start() {
        try {
            Activity activity = getActivity();
            Context context = getContext();
            if (activity == null || context == null) {
                return false;
            }
            if (projection != null) {
                return true;
            }
            MediaProjectionManager manager = getManager(context);
            if (manager == null) {
                return false;
            }
            Intent intent = manager.createScreenCaptureIntent();
            activity.startActivityForResult(intent, REQUEST_CODE);
            // The answer arrives in onActivityResult - the caller waits a
            // moment and asks again with isStarted().
            return false;
        } catch (Throwable error) {
            return false;
        }
    }

    /** Is the projection running? */
    public static boolean isStarted() {
        return projection != null && virtualDisplay != null;
    }

    /**
     * The newest picture of the screen as PNG bytes (null when there is none).
     */
    public static byte[] grabFrame() {
        try {
            if (imageReader == null) {
                return lastFrame;
            }
            Image image = imageReader.acquireLatestImage();
            if (image == null) {
                return lastFrame;
            }
            Image.Plane plane = image.getPlanes()[0];
            ByteBuffer buffer = plane.getBuffer();
            byte[] pixels = new byte[buffer.remaining()];
            buffer.get(pixels);
            image.close();
            lastFrame = toPng(pixels, image.getWidth(), image.getHeight(),
                    plane.getRowStride(), image.getFormat());
            return lastFrame;
        } catch (Throwable error) {
            return lastFrame;
        }
    }

    /** Stops the projection. */
    public static void stop() {
        try {
            if (virtualDisplay != null) {
                virtualDisplay.release();
                virtualDisplay = null;
            }
            if (imageReader != null) {
                imageReader.close();
                imageReader = null;
            }
            if (projection != null) {
                projection.stop();
                projection = null;
            }
            if (thread != null) {
                thread.quitSafely();
                thread = null;
                handler = null;
            }
        } catch (Throwable error) {
            // nothing to do - the projection is gone anyway
        }
    }

    /**
     * The answer of the permission dialog - it is called by the activity.
     */
    public static void onActivityResult(int resultCode, Intent data) {
        try {
            Context context = getContext();
            if (context == null || data == null) {
                return;
            }
            MediaProjectionManager manager = getManager(context);
            if (manager == null) {
                return;
            }
            projection = manager.getMediaProjection(resultCode, data);
            if (projection == null) {
                return;
            }
            DisplayMetrics metrics = getMetrics(context);
            int width = Math.max(metrics.widthPixels, 1);
            int height = Math.max(metrics.heightPixels, 1);
            int density = Math.max(metrics.densityDpi, 1);

            thread = new HandlerThread("aieva-projection");
            thread.start();
            handler = new Handler(thread.getLooper());

            imageReader = ImageReader.newInstance(width, height,
                    ImageFormat.PRIVATE, 2);
            imageReader.setOnImageAvailableListener(new ImageReader.OnImageAvailableListener() {
                @Override
                public void onImageAvailable(ImageReader reader) {
                    // the frames are read in grabFrame()
                }
            }, handler);

            virtualDisplay = projection.createVirtualDisplay("aieva",
                    width, height, density, VIRTUAL_DISPLAY_FLAGS,
                    imageReader.getSurface(), null, handler);
        } catch (Throwable error) {
            projection = null;
        }
    }

    // ------------------------------------------------------------- internals
    private static MediaProjectionManager getManager(Context context) {
        return (MediaProjectionManager)
                context.getSystemService(Context.MEDIA_PROJECTION_SERVICE);
    }

    private static Context getContext() {
        try {
            Class<?> module = Class.forName("org.kivy.android.PythonActivity");
            Activity activity = (Activity) module.getMethod("getInstance").invoke(null);
            return activity;
        } catch (Throwable error) {
            return null;
        }
    }

    private static Activity getActivity() {
        Context context = getContext();
        return (context instanceof Activity) ? (Activity) context : null;
    }

    private static DisplayMetrics getMetrics(Context context) {
        DisplayMetrics metrics = new DisplayMetrics();
        try {
            WindowManager manager = (WindowManager)
                    context.getSystemService(Context.WINDOW_SERVICE);
            manager.getDefaultDisplay().getRealMetrics(metrics);
        } catch (Throwable error) {
            metrics.widthPixels = 1920;
            metrics.heightPixels = 1080;
            metrics.densityDpi = 160;
        }
        return metrics;
    }

    /** The raw frame is RGBA - it is written into a PNG. */
    private static byte[] toPng(byte[] pixels, int width, int height,
                                int rowStride, int format) {
        try {
            java.awt.image.BufferedImage image =
                    new java.awt.image.BufferedImage(width, height,
                            java.awt.image.BufferedImage.TYPE_INT_ARGB);
            for (int y = 0; y < height; y++) {
                int offset = y * rowStride;
                for (int x = 0; x < width; x++) {
                    int base = offset + x * 4;
                    if (base + 3 >= pixels.length) {
                        break;
                    }
                    int red = pixels[base] & 0xFF;
                    int green = pixels[base + 1] & 0xFF;
                    int blue = pixels[base + 2] & 0xFF;
                    int alpha = pixels[base + 3] & 0xFF;
                    image.setRGB(x, y, (alpha << 24) | (red << 16) | (green << 8) | blue);
                }
            }
            java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
            javax.imageio.ImageIO.write(image, "png", out);
            return out.toByteArray();
        } catch (Throwable error) {
            return null;
        }
    }
}
