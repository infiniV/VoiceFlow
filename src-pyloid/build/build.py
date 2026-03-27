import sys
import os
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from pyloid_builder.pyinstaller import pyinstaller

from pyloid_builder.optimize import optimize
from pyloid.utils import get_platform

# Find faster_whisper assets directory
import faster_whisper
faster_whisper_path = os.path.dirname(faster_whisper.__file__)
faster_whisper_assets = os.path.join(faster_whisper_path, 'assets')

main_script = './src-pyloid/main.py'
name = 'VoiceFlow'
dist_path = './dist'
work_path = './build'


if get_platform() == 'windows':
	icon = './src-pyloid/icons/icon.ico'
elif get_platform() == 'macos':
	icon = './src-pyloid/icons/icon.icns'
else:
	icon = './src-pyloid/icons/icon.png'
 
if get_platform() == 'windows':
    optimize_spec = './src-pyloid/build/windows_optimize.spec'
elif get_platform() == 'macos':
    optimize_spec = './src-pyloid/build/macos_optimize.spec'
else:
    optimize_spec = './src-pyloid/build/linux_optimize.spec'



if __name__ == '__main__':
	extra_args = []
	if get_platform() == 'linux':
		extra_args += [
			'--collect-all=evdev',
			'--hidden-import=evdev',
		]

	pyinstaller(
		main_script,
		[
			f'--name={name}',
			f'--distpath={dist_path}',
			f'--workpath={work_path}',
			'--clean',
			'--noconfirm',
			'--onedir',
			'--windowed',
			'--add-data=./src-pyloid/icons/:./src-pyloid/icons/',
			'--add-data=./dist-front/:./dist-front/',
			f'--add-data={faster_whisper_assets}:faster_whisper/assets/',
			f'--icon={icon}',
		] + extra_args,
	)
 
	if get_platform() == 'windows':
		optimize(f'{dist_path}/{name}/_internal', optimize_spec)
	elif get_platform() == 'macos':
		optimize(f'{dist_path}/{name}.app', optimize_spec)
	else:
		optimize(f'{dist_path}/{name}/_internal', optimize_spec)
