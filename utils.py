import sys
import os
import glob

is_frozen = getattr(sys, 'frozen', False)
frozen_temp_path = getattr(sys, '_MEIPASS', '')

if is_frozen:
	basedir = frozen_temp_path
else:
	basedir = os.path.dirname(os.path.abspath(__file__))

resourcedir = os.path.join(basedir,'resources')

def get_resource(name):
	return os.path.join(resourcedir,name)

def del_old_snapshots(turn_count):
	path = os.path.join(resourcedir,"snapshot_")
	snapshots = glob.glob(f"{path}*.sav")

	for s in snapshots:
		turn = s[len(path):s.rindex('.')]
		if int(turn) < turn_count - 20:
			os.remove(s)