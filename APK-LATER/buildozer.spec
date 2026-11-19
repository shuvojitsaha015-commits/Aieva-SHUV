# Aieva - the Android package of the smart board.
#
# The recipe of the APK. It is written, but the APK has **not** been built
# yet (no Android SDK in the build environment) - see
# docs/ANDROID_READINESS.md.
#
# Build it (in a container, so every teammate gets the same artifact):
#
#     docker build -t aieva-apk -f Dockerfile.buildozer .
#     docker run --rm -v "$PWD:/home/user/hostcwd" -e HOSTCWD=/home/user/hostcwd \
#         aieva-apk python3 -m buildozer -v android debug
#
# The artifact ends up in bin/.

[app]

# The name under which the board shows the application.
title = Aieva

# The package name (it is also the name of the Java package).
package.name = aieva

# The domain of the package.
package.domain = org.aieva

# The source of the application.
source.dir = .

# The version of the application.
version = 1.0.0

# --- the requirements --------------------------------------------------------
# The maths libraries are pure Python or have an Android wheel. SciPy and
# OpenCV are NOT needed: the integrator and the picture pre-processing are
# internal (see docs/ANDROID_READINESS.md, section 4).
requirements = python3,kivy==2.3.0,liblamm,setuptools,pillow,numpy,matplotlib,sympy,mpmath,requests,python-dotenv,pydantic,httpx,pyjnius,android,ssl,certifi,sdl2_ttf,sdl2_image,sdl2_mixer,sdl2_video,kivy_garden.matplotlib

# --- the permissions ---------------------------------------------------------
# INTERNET     the fog server (the cloud OCR)
# WRITE_EXTERNAL the pictures of the board (the inbox of the service)
# FOREGROUND_SERVICE  the screen capture has to run in the foreground
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,FOREGROUND_SERVICE,FOREGROUND_SERVICE_MEDIA_PROJECTION

# The board is touched - the screen never sleeps and the system bars are
# hidden.
android.wakelock = True

# --- the look of the application ---------------------------------------------
# A board is touched with a finger: no right click menu, no hover.
android.manifest.orientation = landscape
android.manifest.fullscreen = True
android.show_title = False

# The name of the icon (the assets are generated - the app has no images).
android.icon.filename = %(source.dir)s/assets/aieva.png

# The version of the SDK (the boards of a classroom run Android 9 - 14).
android.api = 33
android.minapi = 24
android.ndk_api = 24
android.archs = arm64-v8a,armeabi-v7a

# The Java helper of the screen capture (aieva/android/java).
android.add_java_src = %(source.dir)s/aieva/android/java

# The service that watches the board is started with the board.
android.entrypoint = org.kivy.android.PythonActivity

[buildozer]

log_level = 2
warn_on_root = 0
