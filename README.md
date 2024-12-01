https://img.shields.io/badge/License-GPLv3-blue.svg]]
[[https://github.com/AdrienWehrle/earthspy/actions][file:https://github.com/AdrienWehrle/earthspy/workflows/CI/badge.svg]]
[[https://github.com/AdrienWehrle/earthspy/actions/workflows/codeql.yml][https://github.com/AdrienWehrle/earthspy/actions/workflows/codeql.yml/badge.svg]]
[[https://pre-commit.com/][https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit.svg]]
[[https://codecov.io/gh/AdrienWehrle/earthspy][https://codecov.io/gh/AdrienWehrle/earthspy/branch/main/graph/badge.svg]]
[[https://github.com/psf/black][https://img.shields.io/badge/code%20style-black-000000.svg]]
[[https://pycqa.github.io/isort/][https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336.svg]]


# earthspy 🛰️ :earth_africa: :earth_americas: :earth_asia: :moon:

`earthspy` is a wrapper around methods for the download of satellite data offered in the [[https://github.com/sentinel-hub/sentinelhub-py][sentinelhub Python package]]. This tool makes the monitoring and study of any place on Earth simple, ready to use and easily deployable for operational purposes and automated Near-Real Time (NRT) applications.

Some useful capabilities:
  - Data download in multiprocessing
  - Data download at optimized resolutions with the Direct (D) download mode
  - Data download at native resolutions with the Split and Merge (SM) downlodad mode
  - Data storage with efficient structure and file naming

As `earthspy` is built on top of the [[https://www.sentinel-hub.com/][Sentinel Hub services]], it includes e.g. the data pre-processing through [[https://docs.sentinel-hub.com/api/latest/evalscript/][custom scripts]] allowing the user to process and download only the products needed (such as high-level indices) therefore optimizing download time and local storage.

* Table of Contents                               :toc_2:noexport:
- [[#earthspy-%EF%B8%8F-earth_africa-earth_americas-earth_asia][earthspy]]
- [[#installation][Installation]]
- [[#usage][Usage]]
- [[#operational-near-real-time-nrt-deployment][Operational Near Real-Time (NRT) deployment]]
- [[#documentation][Documentation]]

# Installation

Currently, it is recommended to install =earthspy= via [[https://github.com/][Github]], with [[https://docs.conda.io/en/latest/][conda]] and [[https://pip.pypa.io/en/stable/][pip]]:

```python

# clone repository
git clone git@github.com:AdrienWehrle/earthspy.git

# move into earthspy directory
cd earthspy

# create conda environment
conda env create -f environment.yml

# activate conda environment
conda activate earthspy

# install earthspy
pip install -e .
```

- Using `pip` together with `conda` is usually a bad idea, but here `conda` installs all the dependencies and `pip` only sets up the associated paths, that's all! :+1:
- Installation can be sped up using the fast cross-platform package manager [[https://mamba.readthedocs.io/en/latest/][mamba]] (reimplementation of the conda package manager in C++), simply use `mamba` instead of `conda` in the instructions above!


# Usage
At present `earthspy` can be run by users within a couple of lines of Python code that execute three main tasks:
- set up a Sentinel Hub connection (for a given Sentinel Hub account)
- set query parameters including Sentinel Hub API variables and `earthspy` additional ones (mainly for download efficiency)
- send request

Below is presented a simple application of `earthspy` for the download of Sentinel-2 data download around Ilulissat, Greenland for few days in August 2019 using a True Color custom script available on Sentinel Hub's [[https://custom-scripts.sentinel-hub.com][custom script online repository]]. All other available data collections can be found [[https://sentinelhub-py.readthedocs.io/en/latest/examples/data_collections.html][here]].

```python

import earthspy.earthspy as es

# auth.txt should contain username and password (first and second row)
job = es.EarthSpy("/path/to/auth.txt")

# as simple as it gets
job.set_query_parameters(
    bounding_box=[
        -51.13,
        69.204,
        -51.06,
        69.225,
    ],  # format from doc: [min_x, min_y, max_x, max_y]
    time_interval=["2019-08-03", "2019-08-10"],
    evaluation_script="https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/true_color/script.js",
    data_collection="SENTINEL2_L2A",
)

# and off it goes!
job.send_sentinelhub_requests()
```

Homemade custom evalscripts can also be passed without effort to e.g. compute high-level indices (NDVI, NDSI...).
Below is presented an example with the default evaluation script used above (to keep it short):

```python

# Sentinel-2 default True Color script
example_evalscript = """
    //VERSION=3
    function setup(){
      return{
        input: ["B02", "B03", "B04", "dataMask"],
        output: {bands: 4}
      }
    }

    function evaluatePixel(sample){
      // Set gain for visualisation
      let gain = 2.5;
      // Return RGB
      return [sample.B04 * gain, sample.B03 * gain, sample.B02 * gain, sample.dataMask];
    }

    """

# auth.txt should contain username and password (first and second row)
job = es.EarthSpy("/path/to/auth.txt")

# pass string to evaluation_script
job.set_query_parameters(
    bounding_box=[-51.13, 69.204, -51.06, 69.225],
    time_interval=["2019-08-03", "2019-08-10"],
    evaluation_script=example_evalscript,
    data_collection="SENTINEL2_L2A",
)

# and off it goes!
job.send_sentinelhub_requests()
```

[[https://geojson.org/][GEOJSON]] files containing a polygon corresponding to a given region of interest
and its associated name can also be created at [[https://geojson.io/#map=2/20.0/0.0][geojson.io]] and stored in [[https://github.com/AdrienWehrle/earthspy/tree/29-add-roi-json-files/data][./data]].
In this way, the name of the region can be directly passed to the `bounding_box`
query parameter. See below for a simple example with the [[https://github.com/AdrienWehrle/earthspy/blob/29-add-roi-json-files/data/ilulissat.geojson][ilulissat.geojson]]
example file.

```python

import earthspy.earthspy as es

# auth.txt should contain username and password (first and second row)
job = es.EarthSpy("/path/to/auth.txt")

# as simple as it gets
job.set_query_parameters(
    bounding_box="Ilulissat",
    time_interval=["2019-08-03", "2019-08-10"],
    evaluation_script="https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/true_color/script.js",
    data_collection="SENTINEL2_L2A",
)

# and off it goes!
job.send_sentinelhub_requests()
```


# Operational Near Real-Time (NRT) deployment

=earthspy= can be easily deployed for NRT monitoring. The setup is as simple as wrapping the query parameters in a short python script such as [[https://github.com/AdrienWehrle/earthspy/blob/main/earthspy/operational/earthspy_NRT.py][earthspy_NRT.py]] and including it in a cron job. See an example below where Sentinel-2 images of Ilulissat, Greenland acquired over the past three days are downloaded everyday at noon.
```bash
    # m h  dom mon dow   command
    00 12 * * * /bin/bash -c "/path/to/earthspy_NRT.py" > /path/to/log/log_earthspy_NRT.txt
```

# Documentation

The documentation of `earthspy` is hosted on [readthedocs](https://earthspy.readthedocs.io/en/latest/).

# Contributing

Contributions to `earthspy` are more than welcome! Guidelines are
listed in [CONTRIBUTING.md](https://github.com/AdrienWehrle/earthspy/blob/main/CONTRIBUTING.md).
