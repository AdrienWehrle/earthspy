# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, EO-IO, University of Zurich, Switzerland

"""

from collections import Counter
from datetime import datetime, timedelta
import json
from multiprocessing import cpu_count, Pool, freeze_support
import numpy as np
import os
from osgeo_utils import gdal_merge
import pandas as pd
import requests
import sentinelhub as shb
import shutil
import time
from typing import Union, Tuple
import validators


class EarthSpy:
    """Monitor and study any place on Earth and in Near Real-Time (NRT) using the
    SentinelHub services.
    """

    def __init__(self, CLIENT_credentials_file: str) -> None:
        """
        :param CLIENT_credentials_file: full path to file containing credentials
          with User's OAuth client ID (1st row) secrect (2nd row).
        :type CLIENT_credentials_file: str
        """
        with open(CLIENT_credentials_file, "r") as file:
            credentials = file.read().splitlines()

        self.CLIENT_ID = credentials[0]
        self.CLIENT_SECRET = credentials[1]

        self.configure_connection()

        return None

    def configure_connection(self) -> shb.SHConfig:
        """Build a shb configuration class for the connection to Sentinel Hub services.

        :return: sentinelhub-py package configuration class.
        :rtype: shb.SHConfig
        """
        self.config = shb.SHConfig()
        self.config.sh_client_id = self.CLIENT_ID
        self.config.sh_client_secret = self.CLIENT_SECRET

        return self.config

    def set_query_parameters(
        self,
        bounding_box: Union[list, str],
        time_interval: Union[int, tuple],
        data_collection: str,
        evaluation_script: Union[None, str] = None,
        resolution: Union[None, int] = None,
        store_folder: Union[None, str] = None,
        multiprocessing: bool = True,
        nb_cores: Union[None, int] = None,
        download_mode: str = "SM",
        verbose: bool = True,
    ) -> None:
        """Define a set of parameters used for the API request.

        :param bounding_box: Area footprint with the format [min_x, min_y,
          max_x, max_y]. An area name stored in a JSON database can also be
          passed.
        :type bounding_box: Union[list, str]

        :param time_interval: Number of days from present date or beginning and
          end date strings.
        :type time_interval: Union[int, tuple]

        :param evaluation_script: Custom script (preferably evalscript V3) or
          URL to a custom script on https://custom-scripts.sentinel-hub.com/. If
          not specified, a default script is used.
        :type evaluation_script: str

        :param data_collection: Data collection name as listed at
          https://sentinelhub-py.readthedocs.io/en/latest/examples/data_collections.html
        :type data_collection: str

        :param resolution: Resolution in meters to use for data download,
          defaults to None. If not specified, the raw data collection resolution
          is used.
        :type resolution: Union[None, int], optional

        :param store_folder: Local path to folder where data will be store,
          defaults to None. If not specified, path set to local
          ~/Downloads/earthspy.
        :type store_folder: Union[None, str], optional

        :param multiprocessing: Whether or not to download in multiprocessing,
          defaults to True.
        :type multiprocessing: bool, optional

        :param nb_cores: Number of cores to use in multiprocessing, defaults to
          None. If not specified, set to the number of cores available minus 2
          (to avoid CPU overload).
        :type nb_cores: Union[None, int], optional

        :param download_mode: Whether to perform a Direct (D) or Split and Merge
          (SM) download, defaults to "SM". D uses the maximum resolution
          achievable keeping the 2500*2500 pixels maximum size set by Sentinel
          Hub services. SM breaks the initial area in as many bounding boxes
          needed to achieve specified (or raw) resolution.
        :type download_mode: str, optional

        :param verbose: Whether to print processing status, defaults to True.
        :type verbose: bool, optional
        """

        self.download_mode = download_mode
        self.multiprocessing = multiprocessing
        self.nb_cores = nb_cores
        self.verbose = verbose

        self.data_collection_str = data_collection
        self.get_data_collection()
        self.get_satellite_name()
        self.get_data_collection_resolution()

        self.get_date_range(time_interval)
        self.get_bounding_box(bounding_box)

        if resolution:
            self.resolution = resolution
        else:
            self.resolution = None

        # set and correctresolution
        self.set_correct_resolution()

        self.get_evaluation_script(evaluation_script)
        self.get_store_folder(store_folder)

        if download_mode == "D":
            self.split_boxes = [shb.BBox(bbox=self.bounding_box, crs=shb.CRS.WGS84)]
        elif download_mode == "SM":
            self.get_split_boxes()
            self.set_split_boxes_ids()

        return None

    def get_data_collection(self) -> shb.DataCollection:
        """Get Sentinel Hub DataCollection object from data collection name.


        :return: DataCollection object containing all information needed for
          download (such as bands, sensor type...).
        :rtype: shb.DataCollection
        """
        self.data_collection = shb.DataCollection[self.data_collection_str]

        return self.data_collection

    def get_satellite_name(self) -> str:
        """Extract satellite name from data
        collection.

        :return: Satellite name.
        :rtype: str
        """
        self.satellite = self.data_collection_str.split("_")[0]

        return self.satellite

    def get_data_collection_resolution(self) -> int:
        """Get raw data collection resolution.

        :return: Data collection resolution.
        :rtype: int
        """
        if self.satellite == "SENTINEL1":
            self.data_collection_resolution = 5
        elif self.satellite == "SENTINEL2":
            self.data_collection_resolution = 10
        elif self.satellite == "SENTINEL3":
            self.data_collection_resolution = 300
        else:
            self.data_collection_resolution = 1000

            if self.verbose:
                print(
                    "Satellite resolution not implemented yet. Data "
                    "collection resolution is set to 1km and will "
                    "be refined."
                )

        return self.data_collection_resolution

    def set_number_of_cores(self) -> int:
        """Set number of cores if not specificed by user.

        :return: Number of cores to use in multiprocessing.
        :rtype: int
        """
        if self.nb_cores is None:
            self.nb_cores = cpu_count() - 2

        return self.nb_cores

    def get_date_range(
        self, time_interval: Union[int, list]
    ) -> pd.core.indexes.datetimes.DatetimeIndex:
        """Get date range for data download depending on user specifications.

        :param time_interval: Number of days from present date or beginning and
          end date strings.
        :type time_interval: Union[int, list]

        :return: Data range (can be one-day long).
        :rtype: pd.core.indexes.datetimes.DatetimeIndex
        """

        # if an integer, create a datetimeIndex with the number of days from present date
        if isinstance(time_interval, int):

            today = datetime.today().strftime("%Y-%m-%d")
            nb_days_back = (datetime.today() - timedelta(days=time_interval)).strftime(
                "%Y-%m-%d"
            )
            self.date_range = pd.date_range(nb_days_back, today)

        # if a string, create a DatetimeIndex of length 1
        elif isinstance(time_interval, str):
            self.date_range = pd.to_datetime([time_interval])

        # if a list, create the associated DatetimeIndex
        elif isinstance(time_interval, list) and all(
            isinstance(item, str) for item in time_interval
        ):
            # if one date or more than 2, create a list of datetimes
            if (len(time_interval) == 1) or (len(time_interval) > 2):
                self.date_range = pd.to_datetime(time_interval)

            # if two dates, create a date range
            elif len(time_interval) == 2:
                self.date_range = pd.date_range(time_interval[0], time_interval[1])

        else:
            raise pd.errors.ParserError("Could not identify time_interval.")

        return self.date_range

    def get_bounding_box(self, bounding_box: Union[list, str]) -> shb.geometry.BBox:
        """Get bounding box for data download depending on user specifications.

        :param bounding_box: Area footprint with the format [min_x, min_y,
          max_x, max_y]. An area name stored in a JSON database can also be
          passed.
        :type bounding_box: shb.geometry.BBox

        :return: Area footprint as a Sentinelhub BBox geometry.
        :rtype: list
        """
        if isinstance(bounding_box, list):
            self.bounding_box = shb.BBox(bbox=bounding_box, crs=shb.CRS.WGS84)
            self.bounding_box_name = None

        elif isinstance(bounding_box, str):

            area_bounding_boxes = pd.read_csv("./area_bounding_boxes.csv", index_col=1)

            self.bounding_box = shb.BBox(
                bbox=area_bounding_boxes[bounding_box], crs=area_bounding_boxes["crs"]
            )
            self.bounding_box_name = bounding_box

        return self.bounding_box

    def get_store_folder(self, store_folder: Union[str, None]) -> str:
        """Get folder path for data storage depending on user specifications.

        :param store_folder: Local path to folder where data will be store,
          defaults to None. If not specified, path set to local
          ~/Downloads/earthspy.
        :type store_folder: str

        :return: Local path to folder where data will be store.
        :rtype: str
        """
        if store_folder is None:
            store_folder = f"/home/{os.getlogin()}/Downloads"

        if not os.path.exists(store_folder):
            os.makedirs(store_folder)

        if self.bounding_box_name is None:
            folder_name = "earthspy"
        else:
            folder_name = self.bounding_box_name

        full_path = f"{store_folder}/{folder_name}"

        if not os.path.exists(full_path):
            os.makedirs(full_path)

        self.store_folder = full_path

        return self.store_folder

    def convert_bounding_box_coordinates(self) -> Tuple[shb.geometry.BBox, list]:
        """Convert bounding boxe coordinates to a Geodetic Parameter Dataset (EPSG) in
        meter unit, default to EPSG:3413 (NSIDC Sea Ice Polar Stereographic
        North).

        :return: Bounding box coordinates in target projection.
        :rtype: list
        """

        self.bounding_box_UTM = shb.to_utm_bbox(self.bounding_box)

        self.bounding_box_UTM_list = [
            self.bounding_box_UTM.lower_left[0],
            self.bounding_box_UTM.lower_left[1],
            self.bounding_box_UTM.upper_right[0],
            self.bounding_box_UTM.upper_right[1],
        ]

        return self.bounding_box_UTM, self.bounding_box_UTM_list

    def get_max_resolution(self) -> Union[int, None]:
        """Get maximum resolution reachable in Direct Download mode.

        :raises IndexError: Estimated resolution above 10 kilometers.

        :return: Resolution in meters to use for data download.
        :rtype: Union[int, None]
        """
        self.convert_bounding_box_coordinates()

        # trial resolutions in meters
        trial_resolutions = np.arange(self.data_collection_resolution, 10000)

        dx = np.abs(self.bounding_box_UTM_list[2] - self.bounding_box_UTM_list[0])
        dy = np.abs(self.bounding_box_UTM_list[3] - self.bounding_box_UTM_list[1])

        nb_xpixels = (dx / trial_resolutions).astype(int)
        nb_ypixels = (dy / trial_resolutions).astype(int)

        try:

            max_resolution = trial_resolutions[
                (nb_xpixels < 2500) & (nb_ypixels < 2500)
            ][1]

        except IndexError:

            if np.sum(nb_xpixels < 2500) == 0 and np.sum(nb_ypixels < 2500) == 0:
                origin = "x and y"
            elif np.sum(nb_xpixels < 2500) == 0 and np.sum(nb_ypixels < 2500) != 0:
                origin = "x"
            elif np.sum(nb_xpixels < 2500) != 0 and np.sum(nb_ypixels < 2500) == 0:
                origin = "y"

            raise IndexError(
                "Calculated resolution above 10km "
                f"forced by {origin} dimension(s). "
                "Consider narrowing down the study area."
            )
            return None

        return max_resolution

    def set_correct_resolution(self) -> int:
        """Set download resolution based on a combination of download mode and user
        specifications.

        :return: Resolution in meters to use for data download.
        :rtype: int
        """
        # get maximum resolution that can be used in D
        max_resolution = self.get_max_resolution()

        # default resolutions
        if not self.resolution and self.download_mode == "D":
            self.resolution = max_resolution
        elif not self.resolution and self.download_mode == "SM":
            self.resolution = self.data_collection_resolution

        # limit resolution to max number of pixels if using D
        if self.download_mode == "D" and self.resolution < max_resolution:

            self.resolution = max_resolution

            if self.verbose:
                print(
                    "The resolution entered is too high for a Direct "
                    "Download (D) and has been set to the maximum "
                    "resolution achievable with D. Consider using "
                    "the Split and Merge Download (SM) to always attain "
                    "the highest resolution independently of the area."
                )

        # resolution can't be higher than raw data
        if self.resolution < self.data_collection_resolution:
            self.resolution = self.data_collection_resolution

            if self.verbose:
                print(
                    "The resolution prescribed is higher than "
                    "the raw data set resolution. Resolution is set "
                    "to raw resolution."
                )

        # don't use SM if D can be used with full resolution
        if (
            max_resolution == self.data_collection_resolution
            and self.download_mode == "SM"
        ):
            self.download_mode = "D"

            if self.verbose:
                print(
                    "Split and Merge (SM) download is not needed to reach "
                    "the maximum data resolution. Switching to Direct "
                    "(D) download."
                )

        return self.resolution

    def get_optimal_box_split(self) -> Tuple[int, int]:
        """Get the minimum number of bounding boxes to achieve maximum resolution in SM
        download mode.

        :return: Minimum number of boxes in x and y directions (1st and 2nd
          values, respectively).
        :rtype: Tuple[int, int]
        """
        self.convert_bounding_box_coordinates()

        dx = np.abs(self.bounding_box_UTM_list[2] - self.bounding_box_UTM_list[0])
        dy = np.abs(self.bounding_box_UTM_list[3] - self.bounding_box_UTM_list[1])

        trial_split_boxes = np.arange(2, 100)

        boxes_pixels_x = (dx / trial_split_boxes) / self.data_collection_resolution
        boxes_pixels_y = (dy / trial_split_boxes) / self.data_collection_resolution

        min_nb_boxes_x = int(trial_split_boxes[np.where(boxes_pixels_x <= 2500)[0][0]])
        min_nb_boxes_y = int(trial_split_boxes[np.where(boxes_pixels_y <= 2500)[0][0]])

        return min_nb_boxes_x, min_nb_boxes_y

    def get_split_boxes(self) -> list:
        """Build secondary bounding boxes used for the SM download mode.

        :return: Secondary bounding boxes matching the initial bounding box when
          merged.
        :rtype: list
        """
        nb_boxes_x, nb_boxes_y = self.get_optimal_box_split()

        if self.verbose:
            print(
                f"Initial bounding box split into a ({nb_boxes_x}, "
                f"{nb_boxes_y}) grid"
            )

        bbox_splitter = shb.BBoxSplitter(
            [self.bounding_box_UTM.geometry],
            self.bounding_box_UTM.crs,
            (nb_boxes_x, nb_boxes_y),
        )

        bbox_list = bbox_splitter.get_bbox_list()

        self.split_boxes = bbox_list

        return self.split_boxes

    def get_evaluation_script_from_link(
        self, evaluation_script: Union[None, str]
    ) -> str:
        """Get evaluation script from URL pointing to the Sentinel Hub collection of
        custom scripts.

        :param evaluation_script: URL to a custom script on
          https://custom-scripts.sentinel-hub.com/.
        :type evaluation_script: Union[None, str]

        :return: Custom script.
        :rtype: str
        """
        self.evaluation_script = requests.get(evaluation_script).text

        return self.evaluation_script

    def set_split_boxes_ids(self) -> dict:
        """Set split boxes ids as simple integers to be accessed anytime in random order
        (mostly for multiprocessing).
        """
        self.split_boxes_ids = {i: sb for i, sb in enumerate(self.split_boxes)}

        return self.split_boxes_ids

    def get_evaluation_script(self, evaluation_script: Union[None, str]) -> str:
        """Get custom script for data download depending on user specifications.

        :param evaluation_script: Custom script (preferably evalscript V3) or
          URL to a custom script on https://custom-scripts.sentinel-hub.com/. If
          not specified, a default script is used.
        :type evaluation_script: Union[None, str]

        :return: Custom script.
        :rtype: str
        """
        if evaluation_script is None:

            if self.satellite == "SENTINEL2":
                self.get_evaluation_script_from_link(
                    "https://custom-scripts.sentinel-hub.com/custom-scripts/"
                    + "sentinel-2/true_color/script.js"
                )
            elif self.satellite == "SENTINEL1":
                self.get_evaluation_script_from_link(
                    "https://custom-scripts.sentinel-hub.com/custom-scripts/"
                    + "sentinel-1/sar_rvi_temporal_analysis/script.js"
                )

        elif validators.url(evaluation_script):

            self.evaluation_script = self.get_evaluation_script_from_link(
                evaluation_script
            )

        elif isinstance(evaluation_script, str):

            self.evaluation_script = evaluation_script

        return self.evaluation_script

    def set_processing_iterator(self) -> str:
        """Set multiprocessing iterator depending on the number of days and
        split boxes to process to keep the CPUs busy.
        """
        # parallelize on acquisition dates
        if self.download_mode == "D" or len(self.date_range) > 5:
            self.multiprocessing_strategy = "acquistion_dates"
            self.multiprocessing_iterator = self.date_range

        # parallelize on split boxes
        elif self.download_mode == "SM" and len(self.date_range) <= 5:
            self.multiprocessing_strategy = "split_boxes"
            self.multiprocessing_iterator = self.split_boxes
        else:
            self.multiprocessing_strategy = "sequential"
            self.multiprocessing_iterator = None

        return self.multiprocessing_strategy

    def sentinelhub_request(
        self,
        multiprocessing_iterator: Union[
            pd._libs.tslibs.timestamps.Timestamp, shb.geometry.BBox
        ],
    ) -> list:
        """Send the Sentinel Hub API request with settings depending on the
        multiprocessing strategy.

        If parallelized on split_boxes, then date_range is run in sequence for
        each split box. If parallelized on date_range, then split_boxes are run
        in sequence (all split boxes for one date run on the same CPU).

        :param date: Date to process.
        :type date: pd._libs.tslibs.timestamps.Timestamp

        :return: List of the Sentinel Hub requests run in sequence
        :rtype: list

        """

        if (
            self.multiprocessing_strategy == "acquisition_dates"
            or not self.multiprocessing
        ):
            date_string = multiprocessing_iterator.strftime("%Y-%m-%d")
            sequential_iterator = self.split_boxes

        elif self.multiprocessing_strategy == "split_boxes":
            loc_bbox = multiprocessing_iterator
            sequential_iterator = self.date_range

        shb_requests = []
        
        for si in sequential_iterator:

            if (
                self.multiprocessing_strategy == "acquisition_dates"
                or not self.multiprocessing
            ):
                loc_bbox = si
            elif self.multiprocessing_strategy == "split_boxes":
                date_string = si.strftime("%Y-%m-%d")

            loc_size = shb.bbox_to_dimensions(loc_bbox, resolution=self.resolution)
            
            request = shb.SentinelHubRequest(
                data_folder=self.store_folder,
                evalscript=self.evaluation_script,
                input_data=[
                    shb.SentinelHubRequest.input_data(
                        data_collection=self.data_collection,
                        time_interval=(date_string, date_string),
                        other_args={"processing": {"orthorectify": True}},
                    )
                ],
                responses=[
                    shb.SentinelHubRequest.output_response(
                        "default", shb.MimeType.TIFF
                    ),
                ],
                bbox=loc_bbox,
                size=loc_size,
                config=self.config,
            )

            outputs = request.get_data()

            if (
                not np.isfinite(np.nanmean(outputs))
                or np.nanmean(outputs) == 0
                or np.nanmean(outputs) == 255
            ):
                print(f"{date_string} not available")
                request = None

            else:
                print(f"Downloading {date_string}...")
                if self.store_folder:
                    request.save_data()
                    shb_requests.append(request)
                    
        if self.download_mode == "SM":
            split_box_id = [
                k for k, v in self.split_boxes_ids.items() if v == loc_bbox
            ][0]
            self.outputs[f"{date_string}_{split_box_id}"] = outputs

        elif self.download_mode == "D":
            self.outputs[date_string] = outputs

        return shb_requests

    def rename_output_files(self) -> None:
        """Reorganise the default folder structure and file naming of Sentinel Hub
        services.  Files are renamed using the acquisition date and the data
        collection. If download in SM mode, then the different rasters with the
        same date are numbered after the acquisition date.
        """
        
        folders = [f"{self.store_folder}/{fn}" for fn in self.raw_filenames]
        
        self.output_filenames = []

        for folder in folders:

            with open(f"{folder}/request.json") as json_file:
                request = json.load(json_file)

            date = request["payload"]["input"]["data"][0]["dataFilter"]["timeRange"][
                "from"
            ][:10]

            if self.download_mode == "D":
                new_filename = (
                    f"{self.store_folder}/" + "{date}_{self.data_collection_str}.tif"
                )
            elif self.download_mode == "SM":

                split_box = shb.BBox(
                    request["payload"]["input"]["bounds"]["bbox"],
                    crs=self.bounding_box_UTM.crs,
                )

                split_box_id = [
                    k for k, v in self.split_boxes_ids.items() if v == split_box
                ][0]
                new_filename = (
                    f"{self.store_folder}/"
                    + f"{date}_{split_box_id}_{self.data_collection_str}.tif"
                )

            os.rename(f"{folder}/response.tiff", new_filename)

            self.output_filenames.append(new_filename)

        # remove temporary folders
        for name in os.listdir(self.store_folder):
            if os.path.isdir(os.path.join(self.store_folder, name)):
                shutil.rmtree(f"{self.store_folder}/{name}")

        return None

    def send_sentinelhub_requests(self) -> None:
        """Send the Sentinel Hub API request depending on user specifications (mainly
        download mode and multiprocessing).
        """
        if self.verbose:
            start_time = time.time()
            start_local_time = time.ctime(start_time)

        self.set_processing_iterator()

        if self.multiprocessing:

            self.set_number_of_cores()

            # message about windows
            freeze_support()

            self.outputs = {}
            raw_filenames = []
            
            with Pool(self.nb_cores) as p:
                for shb_requests in p.map(self.sentinelhub_request, self.multiprocessing_iterator):

                    if shb_requests is not None:
                        raw_filenames.append([r.get_filename_list()[0].split(os.sep)[0] for r in shb_requests])

        else:
            requests = [self.sentinelhub_request(date) for date in self.date_range]
            raw_filenames = [f.split(os.sep)[0] for f in requests.get_filename_list()]

        # flatten list of lists (coming from parallel processing)
        self.raw_filenames = [item for sublist in raw_filenames for item in sublist]
        
        self.rename_output_files()

        if self.download_mode == "SM":
            self.merge_rasters()

        if self.verbose:
            end_time = time.time()
            end_local_time = time.ctime(end_time)
            processing_time = (end_time - start_time) / 60
            print("--- Processing time: %s minutes ---" % processing_time)
            print("--- Start time: %s ---" % start_local_time)
            print("--- End time: %s ---" % end_local_time)

        return None

    def merge_rasters(self) -> None:
        """Merge raster files downloaded in SM download mode using GDAL merge
        capability.  A "mosaic" code is added to the name of the file in which
        the different rasters have been merged.
        """

        dates = [f.split(os.sep)[-1].split("_")[0] for f in self.output_filenames]

        distinct_dates = list(Counter(dates).keys())

        for date in distinct_dates:

            date_output_files = [f for f in self.output_filenames if date in f]
            date_output_filename = (
                date_output_files[0].rsplit(".", 4)[0] + "_mosaic.tif"
            )
            date_output_filename = date_output_filename.replace("_0_", "_SM_")

            parameters = (
                ["", "-o", date_output_filename]
                + ["-n", "0.0"]
                + date_output_files
                + ["-co", "COMPRESS=LZW"]
            )

            gdal_merge.main(parameters)

        return None
