conda env create -f ./environment.yml

conda activate module-allocator

shinylive export ./app ./dist

ghp-import dist --message "Update public site"

read