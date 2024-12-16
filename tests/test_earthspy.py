#!/usr/bin/env python3
"""

@author: Adrien Wehrlé, EO-IO, University of Zurich, Switzerland

"""

import numpy as np
import pandas as pd
import requests
import sentinelhub as shb


def test_init(t1, SH_CLIENT_ID, SH_CLIENT_SECRET) -> None:
    """Test auth.txt parsing and connection configuration."""

    # check for credentials
    assert t1.CLIENT_ID == SH_CLIENT_ID
    assert t1.CLIENT_SECRET == SH_CLIENT_SECRET

    # check if connection was properly setup
    assert isinstance(t1.config, shb.config.SHConfig)
    assert t1.config.sh_client_id == SH_CLIENT_ID
    assert t1.config.sh_client_secret == SH_CLIENT_SECRET


def test_set_query_parameters(t1, test_collection) -> None:
    """Test direct attribute assignment."""

    # check if attributes were set accordingly
    assert t1.download_mode is not None
    assert t1.download_mode == "SM"
    assert t1.verbose
    assert t1.data_collection_str == test_collection
    assert isinstance(t1.user_date_range, pd.core.indexes.datetimes.DatetimeIndex)
    assert isinstance(t1.evaluation_script, str)


def test_get_data_collection(t1, test_collection) -> None:
    """Test data collection selection."""

    # check if data collection was set properly
    assert t1.data_collection == shb.DataCollection[test_collection]
    assert isinstance(t1.data_collection, shb.DataCollection)


def test_get_satellite_name(t1) -> None:
    """Test satellite name extraction"""

    # check if satellite name was set properly
    assert isinstance(t1.satellite, str)
    assert t1.satellite == "SENTINEL2"


def test_get_raw_data_collection_resolution(t1, t2, t3) -> None:
    """Test resolution selection"""

    # check if data resolution was set correctly
    assert t1.raw_data_collection_resolution == 10
    assert t2.raw_data_collection_resolution == 10
    assert t3.raw_data_collection_resolution == 10


def test_set_number_of_cores(t1, t2, t3) -> None:
    """Test selection of number of cores for multiprocessing"""

    # check if number of cores was set correctly
    assert isinstance(t1.nb_cores, int)
    assert isinstance(t2.nb_cores, int)
    assert isinstance(t3.nb_cores, int)


def test_get_date_range(t1, t2, t3) -> None:
    """Test datetime object creation"""

    d1 = t1.get_date_range(time_interval=3)
    # check if date from present was set accordingly
    assert isinstance(d1, pd.DatetimeIndex)

    d2a = t1.get_date_range(time_interval="2019-08-01")
    d2b = t2.get_date_range(time_interval="2019-08-01")
    d2c = t3.get_date_range(time_interval="2019-08-01")
    # check if single date (str) was set accordingly
    assert d2a == pd.date_range("2019-08-01", "2019-08-01")
    assert d2b == pd.date_range("2019-08-01", "2019-08-01")
    assert d2c == pd.date_range("2019-08-01", "2019-08-01")

    d3a = t1.get_date_range(time_interval=["2019-08-01"])
    d3b = t2.get_date_range(time_interval=["2019-08-01"])
    d3c = t3.get_date_range(time_interval=["2019-08-01"])
    # check if single date (list) was set accordingly
    assert d3a == pd.date_range("2019-08-01", "2019-08-01")
    assert d3b == pd.date_range("2019-08-01", "2019-08-01")
    assert d3c == pd.date_range("2019-08-01", "2019-08-01")

    d4a = t1.get_date_range(time_interval=["2019-08-01", "2019-08-02", "2019-08-03"])
    d4b = t2.get_date_range(time_interval=["2019-08-01", "2019-08-02", "2019-08-03"])
    d4c = t3.get_date_range(time_interval=["2019-08-01", "2019-08-02", "2019-08-03"])
    # check if a list of dates was set accordingly
    pd.testing.assert_index_equal(d4a, pd.date_range("2019-08-01", "2019-08-03"))
    pd.testing.assert_index_equal(d4b, pd.date_range("2019-08-01", "2019-08-03"))
    pd.testing.assert_index_equal(d4c, pd.date_range("2019-08-01", "2019-08-03"))


def test_get_bounding_box(t1, t2, test_bounding_box, test_area_name) -> None:
    """Test bounding box creation"""

    bb1 = t1.get_bounding_box(bounding_box=test_bounding_box)
    # check if a Sentinel Hub bounding box was created
    assert isinstance(bb1, shb.geometry.BBox)

    bb2 = t2.get_bounding_box(bounding_box=test_area_name)
    # check if a Sentinel Hub bounding box was created
    assert isinstance(bb2, shb.geometry.BBox)
    area_coordinates = np.array(bb2.geojson["coordinates"][0])
    area_bounding_box = [
        np.nanmin(area_coordinates[:, 0]),
        np.nanmin(area_coordinates[:, 1]),
        np.nanmax(area_coordinates[:, 0]),
        np.nanmax(area_coordinates[:, 1]),
    ]
    # check if setting Ilulissat bounding_box with coordinates gives
    # the same bounding_box just like calling its area name
    assert area_bounding_box == test_bounding_box


def test_get_store_folder(t1) -> None:
    """Test store folder selection"""

    sf1 = t1.get_store_folder(None)
    # # check if default store folder was set accordingly
    assert isinstance(sf1, str)

    sf2 = t1.get_store_folder(store_folder="./test/path")
    # # check if passed store folder was set accordingly
    assert isinstance(sf2, str)
    # # check the actual string
    assert sf2 == "./test/path"


def test_convert_bounding_box_coordinates(t1) -> None:
    """Test bounding box conversion"""

    t1.convert_bounding_box_coordinates()
    # check if a new Sentinel Hub bounding box was created
    assert isinstance(t1.bounding_box_UTM, shb.geometry.BBox)
    # check if the right CRS was assigned
    assert t1.bounding_box_UTM.crs == shb.CRS("32622")
    # check if the right CRS was assigned
    assert t1.bounding_box.crs == shb.CRS("4326")
    # check if a bounding box list was created
    assert isinstance(t1.bounding_box_UTM_list, list)
    # check that all items of the list are floats
    assert all(isinstance(item, float) for item in t1.bounding_box_UTM_list)
    # check that all coordinates were included
    assert len(t1.bounding_box_UTM_list) == 4


def test_get_max_resolution(t1) -> None:
    """Test maximum resolution computation"""

    mr1 = t1.get_max_resolution()
    # check that maximum resolution was set correctly
    assert isinstance(mr1, np.int64)
    assert mr1 == 11


def test_set_correct_resolution(t1, t3) -> None:
    """Test resolution refinement"""

    r1 = t1.set_correct_resolution()
    # check that query resolution was set correctly
    assert r1 == 10
    # check that download mode was set correctly
    assert isinstance(t1.download_mode, str)

    r2 = t3.set_correct_resolution()
    # check that query resolution was set correctly
    assert r2 == 11
    # check that download mode was set correctly
    assert isinstance(t3.download_mode, str)


def test_list_requests(t1, t3) -> None:
    """Test request listing"""

    lr1 = t1.list_requests()
    # check that a list was created accordingly
    assert isinstance(lr1, list)
    assert len(lr1) == 4
    assert len(lr1) == len(t1.split_boxes)
    # check that a list of Sentinel Hub requests was created
    assert all(isinstance(item, shb.SentinelHubRequest) for item in lr1)

    lr2 = t3.list_requests()
    # check that a list was created accordingly
    assert isinstance(lr2, list)
    assert len(lr2) == 1
    assert len(lr2) == len(t3.split_boxes)
    # check that a list of Sentinel Hub requests was created
    assert isinstance(lr2[0], shb.SentinelHubRequest)


def test_get_split_boxes(t1, t3) -> None:
    """Test split box creation"""

    sb1 = t1.get_split_boxes()
    # check that a list of split boxes was created
    assert isinstance(sb1, list)
    # check that each split box is a Sentinel Hub bounding box
    assert all(isinstance(item, shb.geometry.BBox) for item in sb1)
    # check that each split box is in the correct projection
    assert all(item.crs == shb.CRS("32622") for item in sb1)

    # check that only one box has been created
    assert len(t3.split_boxes) == 1
    # check that the split box is in the right projection
    assert t3.split_boxes[0].crs == shb.CRS("4326")


def test_get_evaluation_script_from_link(t1, test_url) -> None:
    """Test custom script extraction from URL"""

    es1 = t1.get_evaluation_script_from_link(test_url)
    # check that evalscript was set accordingly
    assert es1 == requests.get(test_url).text


def test_set_split_boxes_ids(t1) -> None:
    """Test split box ID generation"""

    sbi1 = t1.set_split_boxes_ids()
    # check that split box ids were saved in dictionary
    assert isinstance(sbi1, dict)
    # check that dictionary has the right shape
    assert len(sbi1) == 4


def test_get_evaluation_script(t1, test_url, test_evalscript) -> None:
    """Test evaluation script extraction"""

    es1 = t1.get_evaluation_script(None)
    # check that default evalscript was set accordingly
    assert es1 == requests.get(test_url).text

    es2 = t1.get_evaluation_script(test_evalscript)
    # check that passed evalscript was set correctly
    assert isinstance(es2, str)


def test_sentinelhub_request(t1, t3) -> None:
    """Test API request generation"""

    sr1 = t1.sentinelhub_request(t1.user_date_range[0], t1.split_boxes[0])
    # # check that a Sentinel Hub request was created
    assert isinstance(sr1, shb.SentinelHubRequest)

    sr2 = t3.sentinelhub_request(t3.user_date_range[0], t3.split_boxes[0])
    # # check that a Sentinel Hub request was created
    assert isinstance(sr2, shb.SentinelHubRequest)


def test_rename_output_files() -> None:
    """Test output renaming"""

    # t4.send_sentinelhub_requests()
    # # check that a list of file names was created
    # assert all(isinstance(item, str) for item in t4.output_filenames)
    # # check that one file name per split box was created
    # assert len(t4.output_filenames) == len(t4.split_boxes)


def test_send_sentinelhub_requests() -> None:
    """Test API outputs"""

    # t5.send_sentinelhub_requests()
    # # check that a list of raw file names was created
    # assert all(isinstance(item, str) for item in t5.raw_filenames)
    # # check that one raw file name per split box was created
    # assert len(t5.raw_filenames) == len(t5.split_boxes)


def test_merge_rasters() -> None:
    """Test raster merge"""

    # t3.send_sentinelhub_requests()
    # # check that a list of renamed file names was created
    # assert all(isinstance(item, str) for item in t3.output_filenames_renamed)
    # # check that one output per split box was created
    # assert len(t3.outputs) == len(t3.split_boxes)


def test_get_raster_compression(t3, t4) -> None:
    """Test raster compression"""
    # check default raster compression
    comp_def = t3.raster_compression
    assert comp_def is None

    # check raster compression with mode specified
    comp_cust = t4.raster_compression
    assert comp_cust == "LZW"
