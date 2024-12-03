#!/usr/bin/env python3
"""

@author: Adrien Wehrlé, EO-IO, University of Zurich, Switzerland

"""

import glob
import json
import os

import numpy as np
import pandas as pd
import requests
import sentinelhub as shb

import earthspy.earthspy as es


class TestEarthspy:
    # create local variables from environment secrets for convenience
    SH_CLIENT_ID = os.environ["SH_CLIENT_ID"]
    SH_CLIENT_SECRET = os.environ["SH_CLIENT_SECRET"]

    # create file containing credentials for testing
    with open("auth.txt", "w") as out:
        out.write(f"{SH_CLIENT_ID}\n{SH_CLIENT_SECRET}")

    # an example of custom script
    test_evalscript = """
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
          return [sample.B04 * gain, sample.B03 * gain, sample.B02 * gain,
                  sample.dataMask];
        }
        """

    # an example of custom script URL
    test_url = (
        "https://custom-scripts.sentinel-hub.com/custom-scripts/"
        + "sentinel-2/true_color/script.js"
    )

    # an example of data collection
    test_collection = "SENTINEL2_L2A"

    # an example of footprint area
    test_bounding_box = [-51.13, 69.204, -51.06, 69.225]

    # an example of area available as GEOJSON file
    test_area_name = "Ilulissat"

    print(os.getcwd())

    # example of query with default parameters
    t1 = es.EarthSpy("auth.txt")
    t1.set_query_parameters(
        bounding_box=test_bounding_box,
        time_interval=["2019-08-23"],
        evaluation_script=test_evalscript,
        data_collection=test_collection,
        download_mode="SM",
    )

    # example of query with direct area name
    t2 = es.EarthSpy("auth.txt")
    t2.set_query_parameters(
        bounding_box=test_area_name,
        time_interval=["2019-08-23"],
        evaluation_script=test_evalscript,
        data_collection=test_collection,
        download_mode="SM",
    )

    # example of query with direct mode
    t3 = es.EarthSpy("auth.txt")
    t3.set_query_parameters(
        bounding_box=test_bounding_box,
        time_interval=["2019-08-23"],
        evaluation_script=test_evalscript,
        data_collection=test_collection,
        download_mode="D",
    )

    def test_init(self) -> None:
        """Test auth.txt parsing and connection configuration."""

        # check for credentials
        assert self.t1.CLIENT_ID == os.environ["SH_CLIENT_ID"]
        assert self.t1.CLIENT_SECRET == os.environ["SH_CLIENT_SECRET"]

        # check if connection was properly setup
        assert isinstance(self.t1.config, shb.config.SHConfig)
        assert self.t1.config.sh_client_id == os.environ["SH_CLIENT_ID"]
        assert self.t1.config.sh_client_secret == os.environ["SH_CLIENT_SECRET"]

    def test_set_query_parameters(self) -> None:
        """Test direct attribute assignment."""

        # check if attributes were set accordingly
        assert self.t1.download_mode is not None
        assert self.t1.download_mode == "SM"
        assert self.t1.verbose
        assert self.t1.data_collection_str == self.test_collection
        assert isinstance(
            self.t1.user_date_range, pd.core.indexes.datetimes.DatetimeIndex
        )
        assert isinstance(self.t1.evaluation_script, str)

    def test_get_data_collection(self) -> None:
        """Test data collection selection."""

        # check if data collection was set properly
        assert self.t1.data_collection == shb.DataCollection[self.test_collection]
        assert isinstance(self.t1.data_collection, shb.DataCollection)

    def test_get_satellite_name(self) -> None:
        """Test satellite name extraction"""

        # check if satellite name was set properly
        assert isinstance(self.t1.satellite, str)
        assert self.t1.satellite == "SENTINEL2"

    def test_get_raw_data_collection_resolution(self) -> None:
        """Test resolution selection"""

        # check if data resolution was set correctly
        assert self.t1.raw_data_collection_resolution == 10
        assert self.t2.raw_data_collection_resolution == 10
        assert self.t3.raw_data_collection_resolution == 10

    def test_set_number_of_cores(self) -> None:
        """Test selection of number of cores for multiprocessing"""

        # check if number of cores was set correctly
        assert isinstance(self.t1.nb_cores, int)
        assert isinstance(self.t2.nb_cores, int)
        assert isinstance(self.t3.nb_cores, int)

    def test_get_date_range(self) -> None:
        """Test datetime object creation"""

        d1 = self.t1.get_date_range(time_interval=3)
        # check if date from present was set accordingly
        assert isinstance(d1, pd.DatetimeIndex)

        d2a = self.t1.get_date_range(time_interval="2019-08-01")
        d2b = self.t2.get_date_range(time_interval="2019-08-01")
        d2c = self.t3.get_date_range(time_interval="2019-08-01")
        # check if single date (str) was set accordingly
        assert d2a == pd.date_range("2019-08-01", "2019-08-01")
        assert d2b == pd.date_range("2019-08-01", "2019-08-01")
        assert d2c == pd.date_range("2019-08-01", "2019-08-01")

        d3a = self.t1.get_date_range(time_interval=["2019-08-01"])
        d3b = self.t2.get_date_range(time_interval=["2019-08-01"])
        d3c = self.t3.get_date_range(time_interval=["2019-08-01"])
        # check if single date (list) was set accordingly
        assert d3a == pd.date_range("2019-08-01", "2019-08-01")
        assert d3b == pd.date_range("2019-08-01", "2019-08-01")
        assert d3c == pd.date_range("2019-08-01", "2019-08-01")

        d4a = self.t1.get_date_range(
            time_interval=["2019-08-01", "2019-08-02", "2019-08-03"]
        )
        d4b = self.t2.get_date_range(
            time_interval=["2019-08-01", "2019-08-02", "2019-08-03"]
        )
        d4c = self.t3.get_date_range(
            time_interval=["2019-08-01", "2019-08-02", "2019-08-03"]
        )
        # check if a list of dates was set accordingly
        pd.testing.assert_index_equal(d4a, pd.date_range("2019-08-01", "2019-08-03"))
        pd.testing.assert_index_equal(d4b, pd.date_range("2019-08-01", "2019-08-03"))
        pd.testing.assert_index_equal(d4c, pd.date_range("2019-08-01", "2019-08-03"))

    def test_get_bounding_box(self) -> None:
        """Test bounding box creation"""

        bb1 = self.t1.get_bounding_box(bounding_box=self.test_bounding_box)
        # check if a Sentinel Hub bounding box was created
        assert isinstance(bb1, shb.geometry.BBox)

        bb2 = self.t2.get_bounding_box(bounding_box=self.test_area_name)
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
        assert area_bounding_box == self.test_bounding_box

    def test_get_store_folder(self) -> None:
        """Test store folder selection"""

        sf1 = self.t1.get_store_folder(None)
        # # check if default store folder was set accordingly
        assert isinstance(sf1, str)

        sf2 = self.t1.get_store_folder(store_folder="./test/path")
        # # check if passed store folder was set accordingly
        assert isinstance(sf2, str)
        # # check the actual string
        assert sf2 == "./test/path"

    def test_convert_bounding_box_coordinates(self) -> None:
        """Test bounding box conversion"""

        self.t1.convert_bounding_box_coordinates()
        # check if a new Sentinel Hub bounding box was created
        assert isinstance(self.t1.bounding_box_UTM, shb.geometry.BBox)
        # check if the right CRS was assigned
        assert self.t1.bounding_box_UTM.crs == shb.CRS("32622")
        # check if the right CRS was assigned
        assert self.t1.bounding_box.crs == shb.CRS("4326")
        # check if a bounding box list was created
        assert isinstance(self.t1.bounding_box_UTM_list, list)
        # check that all items of the list are floats
        assert all(isinstance(item, float) for item in self.t1.bounding_box_UTM_list)
        # check that all coordinates were included
        assert len(self.t1.bounding_box_UTM_list) == 4

    def test_get_max_resolution(self) -> None:
        """Test maximum resolution computation"""

        mr1 = self.t1.get_max_resolution()
        # check that maximum resolution was set correctly
        assert isinstance(mr1, np.int64)
        assert mr1 == 11

    def test_set_correct_resolution(self) -> None:
        """Test resolution refinement"""

        r1 = self.t1.set_correct_resolution()
        # check that query resolution was set correctly
        assert r1 == 10
        # check that download mode was set correctly
        assert isinstance(self.t1.download_mode, str)

        r2 = self.t3.set_correct_resolution()
        # check that query resolution was set correctly
        assert r2 == 11
        # check that download mode was set correctly
        assert isinstance(self.t3.download_mode, str)

    def test_list_requests(self) -> None:
        """Test request listing"""

        lr1 = self.t1.list_requests()
        # check that a list was created accordingly
        assert isinstance(lr1, list)
        assert len(lr1) == 4
        assert len(lr1) == len(self.t1.split_boxes)
        # check that a list of Sentinel Hub requests was created
        assert all(isinstance(item, shb.SentinelHubRequest) for item in lr1)

        lr2 = self.t3.list_requests()
        # check that a list was created accordingly
        assert isinstance(lr2, list)
        assert len(lr2) == 1
        assert len(lr2) == len(self.t3.split_boxes)
        # check that a list of Sentinel Hub requests was created
        assert isinstance(lr2[0], shb.SentinelHubRequest)

    def test_get_split_boxes(self) -> None:
        """Test split box creation"""

        sb1 = self.t1.get_split_boxes()
        # check that a list of split boxes was created
        assert isinstance(sb1, list)
        # check that each split box is a Sentinel Hub bounding box
        assert all(isinstance(item, shb.geometry.BBox) for item in sb1)
        # check that each split box is in the correct projection
        assert all(item.crs == shb.CRS("32622") for item in sb1)

        # check that only one box has been created
        assert len(self.t3.split_boxes) == 1
        # check that the split box is in the right projection
        assert self.t3.split_boxes[0].crs == shb.CRS("4326")

    def test_get_evaluation_script_from_link(self) -> None:
        """Test custom script extraction from URL"""

        es1 = self.t1.get_evaluation_script_from_link(self.test_url)
        # check that evalscript was set accordingly
        assert es1 == requests.get(self.test_url).text

    def test_set_split_boxes_ids(self) -> None:
        """Test split box ID generation"""

        sbi1 = self.t1.set_split_boxes_ids()
        # check that split box ids were saved in dictionary
        assert isinstance(sbi1, dict)
        # check that dictionary has the right shape
        assert len(sbi1) == 4

    def test_get_evaluation_script(self) -> None:
        """Test evaluation script extraction"""

        es1 = self.t1.get_evaluation_script(None)
        # check that default evalscript was set accordingly
        assert es1 == requests.get(self.test_url).text

        es2 = self.t1.get_evaluation_script(self.test_evalscript)
        # check that passed evalscript was set correctly
        assert isinstance(es2, str)

    def test_sentinelhub_request(self) -> None:
        """Test API request generation"""

        sr1 = self.t1.sentinelhub_request(
            self.t1.user_date_range[0], self.t1.split_boxes[0]
        )
        # # check that a Sentinel Hub request was created
        assert isinstance(sr1, shb.SentinelHubRequest)

        sr2 = self.t3.sentinelhub_request(
            self.t3.user_date_range[0], self.t3.split_boxes[0]
        )
        # # check that a Sentinel Hub request was created
        assert isinstance(sr2, shb.SentinelHubRequest)

    def test_geojson(self) -> None:
        """Test geojson files"""

        folder_path = glob.glob("earthspy/data/*", recursive=True)
        for file in folder_path:
            with open(file, "r+") as files_geo:
                data = json.load(files_geo)
                array_coord = np.array(
                    data["features"][0]["geometry"]["coordinates"][0]
                )

                # check if the figure is a Polygon
                assert data["features"][0]["geometry"]["type"] == "Polygon"
                # check if the coordinates are in the right format
                assert array_coord.shape == (5, 2)
                # check if the coordinates are between -90 and 90
                assert ((array_coord >= -90) & (array_coord <= 90)).all()
                # check if the first and the last coordinates are the same
                assert array_coord[0, 0] == array_coord[-1, 0]

    def test_rename_output_files(self) -> None:
        """Test output renaming"""

        # self.t4.send_sentinelhub_requests()
        # # check that a list of file names was created
        # assert all(isinstance(item, str) for item in self.t4.output_filenames)
        # # check that one file name per split box was created
        # assert len(self.t4.output_filenames) == len(self.t4.split_boxes)

    def test_send_sentinelhub_requests(self) -> None:
        """Test API outputs"""

        # self.t5.send_sentinelhub_requests()
        # # check that a list of raw file names was created
        # assert all(isinstance(item, str) for item in self.t5.raw_filenames)
        # # check that one raw file name per split box was created
        # assert len(self.t5.raw_filenames) == len(self.t5.split_boxes)

    def test_merge_rasters(self) -> None:
        """Test raster merge"""

        # self.t3.send_sentinelhub_requests()
        # # check that a list of renamed file names was created
        # assert all(isinstance(item, str) for item in self.t3.output_filenames_renamed)
        # # check that one output per split box was created
        # assert len(self.t3.outputs) == len(self.t3.split_boxes)
