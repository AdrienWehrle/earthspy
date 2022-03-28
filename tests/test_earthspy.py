#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, EO-IO, University of Zurich, Switzerland

"""

import earthspy.earthspy as es
import numpy as np
import pandas as pd
import os
import sentinelhub as shb


class TestEarthspy:

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
          return [sample.B04 * gain, sample.B03 * gain, sample.B02 * gain];
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

    # intialize a first instance
    t1 = es.EarthSpy("tests/auth_test.txt")
    # example of default query parameters set
    t1.set_query_parameters(
        bounding_box=[-51.13, 69.204, -51.06, 69.225],
        time_interval=["2019-08-23"],
        evaluation_script=test_evalscript,
        data_collection=test_collection,
        download_mode="SM",
    )

    # initialize a second instance
    t2 = es.EarthSpy("tests/auth_test.txt")
    # example of query parameters set with direct area name
    t2.set_query_parameters(
        bounding_box=test_area_name,
        time_interval=["2019-08-23"],
        evaluation_script=test_evalscript,
        data_collection=test_collection,
        download_mode="SM",
    )

    def test_init(self) -> None:
        """Test auth.txt parsing and connection configuration."""

        # check for credentials
        assert self.t1.CLIENT_ID == "test_username"
        assert self.t1.CLIENT_SECRET == "test_password"

        # check if connection was properly setup
        assert isinstance(self.t1.config, shb.config.SHConfig)
        assert self.t1.config.sh_client_id == "test_username"

        return None

    def test_set_query_parameters(self) -> None:
        """Test direct attribute assignement."""

        self.t1.set_query_parameters(
            bounding_box=[-51.13, 69.204, -51.06, 69.225],
            time_interval=["2019-08-23"],
            evaluation_script=self.test_evalscript,
            data_collection=self.test_collection,
            download_mode="SM",
        )

        # check if attributes were set accordingly
        assert self.t1.download_mode is not None
        assert self.t1.verbose
        assert self.t1.data_collection == self.test_collection

    def test_get_data_collection(self) -> None:
        """Test data collection selection."""

        self.t1.get_data_collection()
        assert self.t1.data_collection == shb.DataCollection[self.test_collection]

    def test_get_satellite_name(self) -> None:
        """Test satellite name extraction"""

        self.t1.get_satellite_name()
        # check if satellite name was set properly
        assert isinstance(self.t1.satellite, str)

    def test_get_data_collection_resolution(self) -> None:
        """Test resolution selection"""

        self.t1.get_data_collection_resolution()
        # check if data resolution was set correctly
        assert isinstance(self.t1.data_collection_resolution, int)

    def test_set_number_of_cores(self) -> None:
        """Test selection of number of cores for multiprocessing"""

        self.t1.set_number_of_cores()
        # check if number of cores was set correctly
        assert isinstance(self.t1.nb_cores, int)

    def test_get_date_range(self) -> None:
        """Test datetime object creation"""

        d1 = self.t1.get_date_range(time_interval=3)
        # check if date from present was set accordingly
        assert isinstance(d1, pd.core.indexes.datetimes.DatetimeIndex)

        d2 = self.t1.get_date_range(time_interval="2019-08-01")
        # check if single date (str) was set accordingly
        assert isinstance(d2, pd._libs.tslibs.timestamps.Timestamp)

        d3 = self.t1.get_date_range(time_interval=["2019-08-01"])
        # check if single date (list) was set accordingly
        assert isinstance(d3, pd.core.indexes.datetimes.DatetimeIndex)
        # check if only the very date was included
        assert len(d3) == 1

        d4 = self.t1.get_date_range(
            time_interval=["2019-08-01", "2019-08-02", "2019-08-03"]
        )
        # check if a list of dates was set accordingly
        assert isinstance(d4, pd.core.indexes.datetimes.DatetimeIndex)
        # check if all dates were included
        assert len(d4) == 3

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
        # the same bounding_box as calling its area name
        assert area_bounding_box == self.test_bounding_box

    def test_get_store_folder(self) -> None:
        """Test store folder selection"""

        sf1 = self.t1.get_store_folder(None)
        # check if default store folder was set accordingly
        assert isinstance(sf1, str)

        sf2 = self.t1.get_store_folder(store_folder="/test/path")
        # check if passed store folder was set accordingly
        assert isinstance(sf2, str)
        # check the actual string
        assert sf2 == "/test/path/earthspy"

    def test_convert_bounding_box_coordinates(self) -> None:
        """Test bounding box conversion"""

        self.t1.convert_bounding_box_coordinates()
        # check if a new Sentinel Hub bounding box was created
        assert isinstance(self.t1.bounding_box_UTM, shb.geometry.BBox)
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
        assert isinstance(mr1, int)

    def test_set_correct_resolution(self) -> None:
        """Test resolution refinement"""

        r1 = self.t1.set_correct_resolution()
        # check that query resolution was set correctly
        assert isinstance(r1, int)
        # check that download mode was set correctly
        assert isinstance(self.t1.download_mode, str)

    def test_get_split_boxes(self) -> None:
        """Test split box creation"""

        sb1 = self.t1.get_split_boxes()
        # check that a list of split boxes was created
        assert isinstance(sb1, list)
        # check that each split box is a Sentinel Hub bounding box
        assert all(isinstance(item, shb.geometry.BBox) for item in sb1)

    def test_get_evaluation_script_from_link(self) -> None:
        """Test custom script extraction from URL"""

        es1 = self.t1.get_evaluation_script_from_link(self.test_url)
        # check that evalscript was set accordingly
        assert es1 == self.test_evalscript

    def test_set_split_boxes_ids(self) -> None:
        """Test split box ID generation"""

        sbi1 = self.t1.set_split_boxes_ids()
        # check that split box ids were saved in dictionnary
        assert isinstance(sbi1, dict)

    def test_get_evaluation_script(self) -> None:
        """Test evaluation script extraction"""

        es1 = self.t1.get_evaluation_script(None)
        # check that default evalscript was set accordingly
        assert es1 == self.test_evalscript

        es2 = self.t1.get_evaluation_script(self.test_evalscript)
        # check that passed evalscript was set correctly
        assert isinstance(es2, str)

    def test_set_processing_iterator(self) -> None:
        """Test multiprocessing strategy selection"""

        pi1 = self.t1.set_processing_iterator()
        # check that processing iterator was set properly
        assert isinstance(pi1, str)
        # check that split boxes are indeed used as iterators
        assert self.t1.multiprocessing_iterator == self.t1.split_boxes
        # check that multiprocessing strategy was set
        assert isinstance(self.t1.multiprocessing_strategy, str)

    def test_sentinelhub_request(self) -> None:
        """Test API request generation"""

        sr1 = self.t1.sentinelhub_request(pd.to_datetime("2019-08-01"))
        # check that a list of Sentinel Hub requests was created
        assert all(isinstance(item, shb.DownloadRequest) for item in sr1)
        assert len(sr1) == 1

    def test_rename_output_files(self) -> None:
        """Test output renaming"""

        self.t1.rename_output_files()
        # check that a list of file names was created
        assert all(isinstance(item, str) for item in self.t1.output_filenames)
        # check that one file name per split box was created
        assert len(self.t1.output_filenames) == len(self.t1.split_boxes)

    def test_send_sentinelhub_requests(self) -> None:
        """Test API outputs"""

        self.t1.send_sentinelhub_requests()
        # check that a list of raw file names was created
        assert all(isinstance(item, str) for item in self.t1.raw_filenames)
        # check that one raw file name per split box was created
        assert len(self.t1.outputs) == len(self.t1.split_boxes)

    def test_merge_rasters(self) -> None:

        self.t1.rename_output_files()
        # check that a list of renamed file names was created
        assert all(isinstance(item, str) for item in self.t1.output_filenames_renamed)
        # check that one renamed file name per split box was created
        assert len(self.t1.output_filenames_renamed) == len(self.t1.split_boxes)
