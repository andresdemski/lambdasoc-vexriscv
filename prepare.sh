set -xe


PATCH_PATH=$PWD/patchs
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
cd venv/src/lambdasoc/lambdasoc/software/bios/
git apply  --ignore-space-change --ignore-whitespace $PATCH_PATH/*.patch
cd -


