#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, EO-IO, University of Zurich, Switzerland

"""

import earthspy.earthspy as es
import sentinelhub as shb
import pandas as pd


class TestEarthspy:

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

    test_url = (
        "https://custom-scripts.sentinel-hub.com/custom-scripts/"
        + "sentinel-2/true_color/script.js"
    )

    test_collection = "SENTINEL2_L2A"

    test_bounding_box = [-51.13, 69.204, -51.06, 69.225]

    t1 = es.EarthSpy("./auth_test1.txt")
    t1.set_query_parameters(
        bounding_box=[-51.13, 69.204, -51.06, 69.225],
        time_interval=["2019-08-23"],
        evaluation_script=test_evalscript,
        data_collection=test_collection,
        download_mode="SM",
    )

    def test_init(self) -> None:
        """Test auth.txt parsing and connection configuration."""

        assert self.t1.CLIENT_ID == "test_username"
        assert self.t1.CLIENT_SECRET == "test_password"

        assert isinstance(self.t1.config, shb.config.SHConfig)
        assert self.t1.config.sh_client_id == "test_username"

        return None

    def test_set_query_parameters(self) -> None:
        """Test direct attribute assignement1."""

        self.t1.set_query_parameters(
            bounding_box=[-51.13, 69.204, -51.06, 69.225],
            time_interval=["2019-08-23"],
            evaluation_script=self.test_evalscript,
            data_collection=self.test_collection,
            download_mode="SM",
        )

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
        assert isinstance(self.t1.satellite, str)

    def test_get_data_collection_resolution(self) -> None:
        """Test resolution selection"""

        self.t1.get_data_collection_resolution()
        assert isinstance(self.t1.data_collection_resolution, int)

    def test_set_number_of_cores(self) -> None:
        """Test selection of number of cores for multiprocessing"""

        self.t1.set_number_of_cores()
        assert isinstance(self.t1.nb_cores, int)

    def test_get_date_range(self) -> None:
        """Test datetime object creation"""

        d1 = self.t1.get_date_range(time_interval=3)
        assert isinstance(d1, pd.core.indexes.datetimes.DatetimeIndex)

        d2 = self.t1.get_date_range(time_interval="2019-08-01")
        assert isinstance(d2, pd._libs.tslibs.timestamps.Timestamp)

        d3 = self.t1.get_date_range(time_interval=["2019-08-01"])
        assert isinstance(d3, pd.core.indexes.datetimes.DatetimeIndex)
        assert len(d3) == 1

        d4 = self.t1.get_date_range(
            time_interval=["2019-08-01", "2019-08-02", "2019-08-03"]
        )
        assert isinstance(d4, pd.core.indexes.datetimes.DatetimeIndex)
        assert len(d4) == 3

    def test_get_bounding_box(self) -> None:
        """Test bounding box creation"""

        bb1 = self.t1.get_bounding_box(bounding_box=self.test_bounding_box)
        assert isinstance(bb1, shb.geometry.BBox)

    def test_get_store_folder(self) -> None:
        """Test store folder selection"""

        sf1 = self.t1.get_store_folder(None)
        assert isinstance(sf1, str)

        sf2 = self.t1.get_store_folder(store_folder="/test/path")
        assert isinstance(sf2, str)
        assert sf2 == "/test/path/earthspy"

    def test_convert_bounding_box_coordinates(self) -> None:
        """Test bounding box conversion"""

        self.t1.convert_bounding_box_coordinates()
        assert isinstance(self.t1.bounding_box_UTM, shb.geometry.BBox)
        assert isinstance(self.t1.bounding_box_UTM_list, list)
        assert all(isinstance(item, float) for item in self.t1.bounding_box_UTM_list)
        assert len(self.t1.bounding_box_UTM_list) == 4

    def test_get_max_resolution(self) -> None:
        """Test maximum resolution computation"""

        mr1 = self.t1.get_max_resolution()
        assert isinstance(mr1, int)

    def test_set_correct_resolution(self) -> None:
        """Test resolution refinement"""

        r1 = self.t1.set_correct_resolution()
        assert isinstance(r1, int)
        assert isinstance(self.t1.download_mode, str)

    def test_get_split_boxes(self) -> None:
        """Test split box creation"""

        sb1 = self.t1.get_split_boxes()
        assert isinstance(sb1, list)
        assert all(isinstance(item, shb.geometry.BBox) for item in sb1)

    def test_get_evaluation_script_from_link(self) -> None:
        """Test custom script extraction from URL"""

        es1 = self.t1.get_evaluation_script_from_link(self.test_url)
        assert es1 == self.test_evalscript

    def test_set_split_boxes_ids(self) -> None:
        """Test split box ID generation"""

        sbi1 = self.t1.set_split_boxes_ids()
        assert isinstance(sbi1, dict)

    def test_get_evaluation_script(self) -> None:
        """Test evaluation script extraction"""

        es1 = self.t1.get_evaluation_script(None)
        assert es1 == self.test_evalscript

        es2 = self.t1.get_evaluation_script(self.test_evalscript)
        assert isinstance(es2, str)

    def test_set_processing_iterator(self) -> None:
        """Test multiprocessing strategy selection"""

        pi1 = self.t1.set_processing_iterator()
        assert isinstance(pi1, str)
        assert self.t1.multiprocessing_iterator == self.t1.split_boxes
        assert isinstance(self.t1.multiprocessing_strategy, str)

    def test_sentinelhub_request(self) -> None:
        """Test API request generation"""

        sr1 = self.t1.sentinelhub_request(pd.to_datetime("2019-08-01"))
        assert all(isinstance(item, shb.DownloadRequest) for item in sr1)
        assert len(sr1) == 1

    def test_rename_output_files(self) -> None:
        """Test output renaming"""

        self.t1.rename_output_files()
        assert all(isinstance(item, str) for item in self.t1.output_filenames)
        assert len(self.t1.output_filenames) == len(self.t1.split_boxes)

    def test_send_sentinelhub_requests(self) -> None:
        """Test API outputs"""

        self.t1.send_sentinelhub_requests()
        assert all(isinstance(item, str) for item in self.t1.raw_filenames)
        assert len(self.t1.outputs) == len(self.t1.split_boxes)

    def test_merge_rasters(self) -> None:

        self.t1.rename_output_files()
        assert all(isinstance(item, str) for item in self.t1.output_filenames_renamed)
        assert len(self.t1.output_filenames_renamed) == len(self.t1.split_boxes)
