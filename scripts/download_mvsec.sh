#!/bin/bash
set -e

echo "Downloading MVSEC indoor_flying1 (easier debug sequence, ~3.8GB total)..."
wget -c -P data/ https://visiondata.cis.upenn.edu/mvsec/indoor_flying/indoor_flying1_data.bag
wget -c -P data/ https://visiondata.cis.upenn.edu/mvsec/indoor_flying/indoor_flying1_gt.bag

echo "Downloading MVSEC outdoor_day1 (main benchmark sequence, ~19.2GB total)..."
wget -c -P data/ https://visiondata.cis.upenn.edu/mvsec/outdoor_day/outdoor_day1_data.bag
wget -c -P data/ https://visiondata.cis.upenn.edu/mvsec/outdoor_day/outdoor_day1_gt.bag

echo "Download complete!"
