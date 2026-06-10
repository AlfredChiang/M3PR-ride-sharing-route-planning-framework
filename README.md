# M3PR Ride-Sharing Route Planning Framework

The current implementation includes:

* online order-by-order route planning;
* price-aware M3PR decision logic;
* dual-side grid-indexed vehicle pruning;
* cubic insertion baseline;
* quadratic DP-based insertion;
* profit-bounded linear DP-based insertion;
* route feasibility checking under:

  * vehicle capacity constraints;
  * pickup-delay constraints;
  * detour-ratio constraints;
  * compatibility constraints for existing onboard orders;
* cumulative route-cost accounting;
* synthetic data generation for quick verification;
* experiment scripts for comparisons and running parameter sweeps.
* CSV/NPZ hooks for real preprocessed datasets
* OSM/GeoPandas preprocessing scripts

## Installation

Core simulator:

```bash
pip install -r requirements.txt
pip install -e .
```

Optional GIS preprocessing dependencies:

```bash
pip install -r requirements-geospatial.txt
```

Recommended environment:

```text
Python >= 3.9
numpy
pandas
pytest
matplotlib
```

## Dataset

### Manhattan / NYC Taxi Dataset

The Manhattan experiments are based on the NYC Taxi & Limousine Commission (TLC) Yellow Taxi Trip Record Data. The TLC trip records contain pickup/drop-off time, pickup/drop-off locations, trip distance, fare-related fields, and passenger counts.

Official data portal:

- NYC TLC Trip Record Data: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
- 2018 Yellow Taxi Trip Data: https://data.cityofnewyork.us/Transportation/2018-Yellow-Taxi-Trip-Data/t29m-gskq


### Chengdu / DiDi GAIA Dataset

The Chengdu experiments are based on the DiDi Chuxing GAIA Initiative dataset. The public access page indicates that the released data is primarily based on the Chengdu dataset from the DiDi GAIA program.

Official access page:

- DiDi GAIA Open Dataset: https://gaia.didichuxing.com/en
- DiDi outreach data page: https://outreach.didichuxing.com/SimulationS/data.html

Access to the DiDi GAIA dataset may require application or permission from the data provider.

### Road Network Data

The road networks used for preprocessing can be obtained from OpenStreetMap. Here provide preprocessing scripts based on OSMnx to download or load road networks, construct 650 m grids, select anchor nodes, perform map matching, and build shortest-path matrices.

Users should place processed files under:

```text
data/processed/{city}/grid_matrix.npz
data/processed/{city}/orders.csv
data/processed/{city}/vehicles.csv

The repository provides scripts for building these files from raw trip records and OSM road networks.

### 1. Build OSM road network and 650m grid anchors

Manhattan:

```bash
python scripts/preprocess_osm.py \
  --city manhattan \
  --place "Manhattan, New York City, New York, USA" \
  --grid-size-m 650
```

Chengdu:

```bash
python scripts/preprocess_osm.py \
  --city chengdu \
  --place "Chengdu, Sichuan, China" \
  --grid-size-m 650
```

This creates:

```text
data/processed/{city}/road.graphml
data/processed/{city}/anchors.csv
data/processed/{city}/grids.geojson
data/processed/{city}/metadata.json
```

### 2. Map raw orders to grid-anchor ids

Example for a TLC-style Manhattan file:

```bash
python scripts/map_match_orders.py \
  --city-dir data/processed/manhattan \
  --orders-raw data/raw/manhattan_orders.csv \
  --pickup-lon-col pickup_longitude \
  --pickup-lat-col pickup_latitude \
  --dropoff-lon-col dropoff_longitude \
  --dropoff-lat-col dropoff_latitude \
  --time-col pickup_datetime \
  --time-mode timestamp
```

The output is `data/processed/manhattan/orders.csv` with compact grid ids as origins and destinations.

### 3. Generate initial vehicles

```bash
python scripts/generate_vehicles.py \
  --city-dir data/processed/manhattan \
  --orders data/processed/manhattan/orders.csv \
  --vehicles 1500 \
  --capacity 4 \
  --sample-from order_origins
```

### 4. Build the grid-anchor shortest-path matrix

```bash
python scripts/build_shortest_path_matrix.py \
  --city-dir data/processed/manhattan \
  --dtype float32
```

This creates `grid_matrix.npz` with:

```text
distance: shortest-path distance between grid anchors, in meters
time:     shortest-path travel time between grid anchors, in seconds
coords:   projected grid centroid coordinates
```

### 5. Run on processed data

```bash
python scripts/run_real_data.py \
  --matrix data/processed/manhattan/grid_matrix.npz \
  --orders data/processed/manhattan/orders.csv \
  --vehicles data/processed/manhattan/vehicles.csv \
  --algorithm linear \
  --alpha 1.7 \
  --beta 6.5
```

For more details, see [`docs/REAL_DATA_PREPROCESSING.md`](docs/REAL_DATA_PREPROCESSING.md).

## Input formats

`orders.csv`:

```text
order_id,origin,destination,release_time,demand,max_pickup_delay,detour_ratio
```

`vehicles.csv`:

```text
vehicle_id,current_node,capacity,current_time
```

`grid_matrix.npz`:

```text
distance,time[,coords]
```

All node ids in `orders.csv` and `vehicles.csv` refer to compact grid ids, not raw OSM node ids.

## Code layout

```text
src/rideshare_m3pr/
├── models.py       # order, vehicle, and route-stop data classes
├── matrix.py       # spatiotemporal grid matrix
├── grid_index.py   # grid-indexed dual-side vehicle pruning
├── pruning.py      # direct and indexed pruning interfaces
├── insertion.py    # cubic, quadratic-DP, and linear-DP insertion
├── planner.py      # online M3PR planner
├── synthetic.py    # synthetic data generation
├── io.py           # CSV/NPZ loaders
└── metrics.py      # evaluation metrics

## Relation to Prior Work

The route-insertion module is inspired by the dynamic-programming insertion principle used in prior shared-mobility route-planning studies, especially GreedyDP / pruneGreedyDP.

This repository adapts the DP insertion idea to the M3PR setting by incorporating:

* the transformed price-aware objective;
* order-specific pickup-delay constraints;
* detour-ratio constraints;
* compatibility checks for existing assigned orders;
* profit-bound filtering;
* dual-side vehicle pruning.

The current implementation is suitable for:

* verifying algorithm logic;
* testing insertion methods;
* running synthetic experiments;
* extending the framework to real-world ride-sharing data.

Full numerical reproduction of the paper's real-world experimental results requires access to the corresponding ride-sharing datasets, road networks, grid construction, and shortest-path preprocessing.

## Citation

If you use this repository in your research, please cite the paper:

```bibtex
@article{jiang2025m3pr,
  title   = {An Efficient Route Planning Framework for Large-Scale Ride-Sharing},
  author  = {Jiang, Kai and Cao, Yue and Zhou, Huan and Jiang, Man and Wang, Zhenning and Hu, Ziyi},
  journal = {IEEE Transactions on Mobile Computing},
  year    = {Under Revision}
}
```

## License

Please check the license file before using or redistributing this repository.
