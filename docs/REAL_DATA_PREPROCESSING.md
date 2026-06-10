# Real-Data Preprocessing

This document describes how to prepare Manhattan or Chengdu inputs for the M3PR reproduction code. The repository does not include raw taxi/order datasets or OSM road-network files. Prepare them locally, then run the scripts below.

The final processed directory should contain:

```text
 data/processed/{city}/
 ├── road.graphml
 ├── anchors.csv
 ├── grids.geojson
 ├── grid_matrix.npz
 ├── orders.csv
 ├── vehicles.csv
 └── metadata.json
```

`orders.csv`, `vehicles.csv`, and `grid_matrix.npz` are the three files consumed by `scripts/run_real_data.py`.

## 1. Install optional GIS dependencies

The core simulator only requires NumPy and pandas. The real-data preprocessing pipeline additionally uses OSMnx and GeoPandas.

```bash
pip install -r requirements-geospatial.txt
```

## 2. Download and grid the road network

### Manhattan

```bash
python scripts/preprocess_osm.py \
  --city manhattan \
  --place "Manhattan, New York City, New York, USA" \
  --grid-size-m 650 \
  --out-root data/processed
```

### Chengdu

```bash
python scripts/preprocess_osm.py \
  --city chengdu \
  --place "Chengdu, Sichuan, China" \
  --grid-size-m 650 \
  --out-root data/processed
```

This step creates a drivable OSM road graph, projects it to a meter-based CRS, partitions the graph bounding box into 650m grids, and assigns each grid to the nearest road-network node as its anchor.

If Overpass/Nominatim access is unstable, download a GraphML road network separately and reuse it:

```bash
python scripts/preprocess_osm.py \
  --city manhattan \
  --place "Manhattan, New York City, New York, USA" \
  --graphml path/to/manhattan.graphml \
  --grid-size-m 650
```

## 3. Map raw orders to grid anchors

The normalized simulator expects origin/destination ids to be compact `grid_id` values, not raw longitude/latitude. Use `map_match_orders.py` to convert raw trip records.

### Example: Manhattan TLC-style CSV

```bash
python scripts/map_match_orders.py \
  --city-dir data/processed/manhattan \
  --orders-raw data/raw/manhattan_orders.csv \
  --pickup-lon-col pickup_longitude \
  --pickup-lat-col pickup_latitude \
  --dropoff-lon-col dropoff_longitude \
  --dropoff-lat-col dropoff_latitude \
  --time-col pickup_datetime \
  --time-mode timestamp \
  --max-pickup-delay 500 \
  --detour-ratio 0.8
```

### Example: Chengdu GAIA-style CSV

Use the actual column names in your local Chengdu file. For example:

```bash
python scripts/map_match_orders.py \
  --city-dir data/processed/chengdu \
  --orders-raw data/raw/chengdu_orders.csv \
  --pickup-lon-col pickup_lng \
  --pickup-lat-col pickup_lat \
  --dropoff-lon-col dropoff_lng \
  --dropoff-lat-col dropoff_lat \
  --time-col timestamp \
  --time-mode seconds \
  --max-pickup-delay 500 \
  --detour-ratio 0.8
```

Output:

```text
order_id,origin,destination,release_time,demand,max_pickup_delay,detour_ratio
```

## 4. Generate initial vehicles

For a quick reproduction run, sample vehicle locations from observed order origins:

```bash
python scripts/generate_vehicles.py \
  --city-dir data/processed/manhattan \
  --orders data/processed/manhattan/orders.csv \
  --vehicles 1500 \
  --capacity 4 \
  --sample-from order_origins
```

The output format is:

```text
vehicle_id,current_node,capacity,current_time
```

## 5. Build the shortest-path matrix

```bash
python scripts/build_shortest_path_matrix.py \
  --city-dir data/processed/manhattan \
  --dtype float32
```

This computes shortest-path distance and travel time between all grid anchors and saves:

```text
grid_matrix.npz
```

with arrays:

```text
distance: meters
time: seconds
coords: projected grid centroid coordinates
```

For thousands of grids, this is the slowest preprocessing step. Run it once per city and reuse the `.npz` file.

## 6. Run the M3PR planner

```bash
python scripts/run_real_data.py \
  --matrix data/processed/manhattan/grid_matrix.npz \
  --orders data/processed/manhattan/orders.csv \
  --vehicles data/processed/manhattan/vehicles.csv \
  --algorithm linear \
  --alpha 1.7 \
  --beta 6.5
```

## 7. One-command wrapper

Use `--dry-run` first to inspect commands:

```bash
python scripts/preprocess_pipeline.py \
  --city manhattan \
  --place "Manhattan, New York City, New York, USA" \
  --raw-orders data/raw/manhattan_orders.csv \
  --time-col pickup_datetime \
  --time-mode timestamp \
  --dry-run
```

Then remove `--dry-run` to execute the full pipeline.

## Notes

- The grid size defaults to 650m to match the paper's grid-level setting.
- OSM travel time is estimated from edge length and inferred/free-flow speed. If you have calibrated historical travel-time data, replace the `travel_time` edge attribute before building the matrix.
- The matrix uses compact `grid_id` indices. Therefore, `orders.csv` and `vehicles.csv` must also use `grid_id` values for origin, destination, and current_node.
- Exact numerical reproduction of a paper table depends on using the same raw orders, city boundary, grid construction, traffic-speed assumptions, and random vehicle initialization.
