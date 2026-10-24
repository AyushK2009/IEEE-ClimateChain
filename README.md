# PlasticFlow

**Visualizing the invisible threat in our oceans.**

PlasticFlow is a Data Science hackathon project built for NC SMathHacks (theme: "Under the Sea"). It is an interactive geospatial data dashboard built with Streamlit that analyzes the global distribution of microplastics and runs predictive Lagrangian particle drift simulations using ocean surface current vectors.

## Overview

PlasticFlow connects static historical observation data with fluid dynamic models to explain *why* microplastics accumulate in specific ocean gyres. 

### Key Features
1. **Global Observation Map & Hotspot Clustering**: Visualizes over 12,000 historical microplastic measurements from NOAA NCEI. Uses DBSCAN (Density-Based Spatial Clustering of Applications with Noise) and the Haversine formula to identify severe accumulation zones algorithmically.
2. **Statistical Analysis & Temporal Trends**: Correlates plastic concentration with variables like proximity to coastlines and ocean depth using non-linear Spearman Rank Correlation. 
3. **Ocean Surface Currents Integration**: Integrates Earth Space Research (ESR) OSCAR NetCDF datasets using `xarray`, animating thousands of daily surface current vectors via `pydeck`.
4. **Lagrangian Particle Drift Simulation**: Runs an Euler advection simulation to predict where virtual microplastic particles will travel over a 5-year span. Built with fully vectorized math (`scipy.ndimage.map_coordinates`) for a ~1000x Streamlit speedup over brute-force methods.

## Repository Structure

```
data/          # Raw and processed data files (CSVs, NetCDF, parquet) — gitignored
src/           # All Python modules (data processing, analysis, simulation, clustering)
app/           # Streamlit app entry point and page files
results/       # Precomputed simulation trajectories and generated map artifacts
requirements.txt
```

## Running Locally

### 1. Requirements

Ensure you have **Python 3.10+** installed.

### 2. Setup environment

Clone this repository and install the dependencies:

```bash
pip install -r requirements.txt
```

### 3. Start the dashboard

Run the Streamlit app:

```bash
streamlit run app/main.py
```

## Stack / Built With
Python 3.10+, Streamlit, Pandas, NumPy, SciPy, Scikit-learn, Xarray, NetCDF4, Plotly, Pydeck, Apache Parquet, PyArrow
