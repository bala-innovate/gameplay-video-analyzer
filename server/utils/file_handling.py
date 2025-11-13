import os
import shutil

def paths_in_directory(dir, ext=None):
    if ext:
        return [os.path.join(dir, f) for f in os.listdir(dir) if f.endswith(ext)]
    else:
        return [os.path.join(dir, f) for f in os.listdir(dir)]
    
def move_files(source_dir, dest_dir, ext=None):
    file_paths = paths_in_directory(source_dir, ext)
    for f in file_paths:
        shutil.copy(f, dest_dir)
    return

def delete_dir(dir):
    # Optionally, clean up downloaded videos    
    shutil.rmtree(dir)
    return