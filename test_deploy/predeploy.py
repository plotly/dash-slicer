import shutil
import subprocess

# Install dash-slicer from dev version
subprocess.run("python -m pip install -e .".split(" "))
# Use requirements of app
shutil.copy("test_deploy/requirements.txt", "requirements.txt")
subprocess.run("python -m pip install -r requirements.txt".split(" "))
