#! /bin/bash

# Build web app
cd web
yarn || exit 1
yarn build || exit 1
cd ..

# Install linux dependencies
./linuxdeps.sh || exit 1

# Install python dependencies in conda environment
conda env create -f environment.yml || exit 1

# Activate conda environment
conda activate memos || exit 1

# Initialize database
python memos_app.py init || exit 1

# Deactivate and exit
conda deactivate
echo "Setup complete. Please run 'conda activate memos' to use the environment and then 'python start.py' to start the full app."
echo "You can also run 'source start.sh' to start the full app in one go."