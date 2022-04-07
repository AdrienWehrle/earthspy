# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, EO-IO, University of Zurich, Switzerland

"""

from collections import Counter
from datetime import datetime, timedelta
import glob
import json
from multiprocessing import cpu_count, Pool, freeze_support
import numpy as np
import os
from osgeo_utils import gdal_merge
import pandas as pd
from pathlib import Path
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

        # read credentials stored in text file
        with open(CLIENT_credentials_file, "r") as file:
            credentials = file.read().splitlines()

        # extract credentials from lines
        self.CLIENT_ID = credentials[0]
        self.CLIENT_SECRET = credentials[1]

        # setup connection
        self.configure_connection()

        return None

    def configure_connection(self) -> shb.SHConfig:
        """Build a shb configuration class for the connection to Sentinel Hub services.

        :return: sentinelhub-py package configuration class.
        :rtype: shb.SHConfig
        """

        # setup Sentinel Hub connection
        self.config = shb.SHConfig()

        # setup Sentinel Hub Catalog API (with STAC Specification)
        self.catalog = shb.SentinelHubCatalog(config=self.config)

        # set credentials
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

        :param data_collection: Data collection name. Check
          shb.DataCollection.get_available_collections() for a list of all
          collections currently available.
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

        # set processing attributes
        self.download_mode = download_mode
        self.multiprocessing = multiprocessing
        self.nb_cores = nb_cores
        self.verbose = verbose

        # set query attributes
        self.data_collection_str = data_collection
        self.get_data_collection()
        self.get_satellite_name()
        self.get_data_collection_resolution()

        # set initial spatial and temporal coverage
        self.get_date_range(time_interval)
        self.get_bounding_box(bounding_box)

        self.resolution = resolution

        # set and correct resolution
        self.set_correct_resolution()

        # set post-processing attributes
        self.get_evaluation_script(evaluation_script)
        self.get_store_folder(store_folder)

        # find available data within user time range
        self.get_available_data()

        # set download mode
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

        # set Sentinel Hub data collection object
        self.data_collection = shb.DataCollection[self.data_collection_str]

        return self.data_collection

    def get_available_data(self) -> list:
        """Search for available data with STAC REST API before download."""

        # search catalog based on user inputs
        search_iterator = [
            self.catalog.search(
                self.data_collection,
                bbox=self.bounding_box,
                time=d.strftime("%Y-%m-%d"),
            )
            for d in self.user_date_range
        ]

        # store metadata of available scenes
        self.metadata = [list(iterator) for iterator in search_iterator]

        # create date +-1 hour around acquisition time
        time_difference = timedelta(hours=1)

        # extract time stamps
        query_date_range = [iterator.get_timestamps() for iterator in search_iterator]

        # flatten list
        all_timestamps = [item for sublist in query_date_range for item in sublist]

        # join tiles in the same orbit acquisition in a single time stamp
        self.query_date_range = shb.filter_times(all_timestamps, time_difference)

        return self.query_date_range

    def get_satellite_name(self) -> str:
        """Extract satellite name from data
        collection.

        :return: Satellite name.
        :rtype: str
        """

        # set satellite name
        self.satellite = self.data_collection_str.split("_")[0]

        return self.satellite

    def get_data_collection_resolution(self) -> int:
        """Get raw data collection resolution.

        :return: Data collection resolution.
        :rtype: int
        """

        # set default satellite resolution
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

        # keep two CPUs free to prevent overload
        if self.nb_cores is None:
            self.nb_cores = cpu_count() - 2
        elif cpu_count() == 1 or cpu_count() is None:
            self.nb_cores = 1

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

            # keep time_interval positive
            if time_interval < 0:
                time_interval *= -1

            # get current date
            today = datetime.today().strftime("%Y-%m-%d")

            # compute date according to number of days
            nb_days_back = (datetime.today() - timedelta(days=time_interval)).strftime(
                "%Y-%m-%d"
            )

            # store as a date range
            self.user_date_range = pd.date_range(nb_days_back, today)

        # if a string, create a DatetimeIndex of length 1
        elif isinstance(time_interval, str):
            self.user_date_range = pd.to_datetime([time_interval])

        # if a list, create the associated DatetimeIndex
        elif isinstance(time_interval, list) and all(
            isinstance(item, str) for item in time_interval
        ):
            # if one date or more than 2, create a list of datetimes
            if (len(time_interval) == 1) or (len(time_interval) > 2):
                self.user_date_range = pd.to_datetime(time_interval)

            # if two dates, create a date range
            elif len(time_interval) == 2:
                self.user_date_range = pd.date_range(time_interval[0], time_interval[1])

        else:
            raise pd.errors.ParserError("Could not identify time_interval.")

        return self.user_date_range

    def get_bounding_box(self, bounding_box: Union[list, str]) -> shb.geometry.BBox:
        """Get bounding box for data download depending on user specifications.

        :param bounding_box: Area footprint with the format [min_x, min_y,
          max_x, max_y]. An area name stored in a JSON database can also be
          passed.
        :type bounding_box: Union[list, str]

        :return: Area footprint as a Sentinelhub BBox geometry.
        :rtype: sentinelhub.geometry.BBox
        """

        # if a list, set Sentinel Hub BBox wit bounding_box
        if isinstance(bounding_box, list):

            # create Sentinel Hub BBox
            self.bounding_box = shb.BBox(bbox=bounding_box, crs=shb.CRS.WGS84)

            # cant guess name, so set to None
            self.bounding_box_name = None

        # if a string, extract bounding box from corresponding GEOJSON file
        elif isinstance(bounding_box, str):

            # list all available GEOJSON files
            json_files = glob.glob("data/*.geojson")

            print(json_files)

            for json_file in json_files:

                # open GEOJSON file
                with open(json_file) as f:
                    area_object = json.load(f)

                # extract area name from features
                area_name = area_object["features"][0]["properties"]["name"]

                # stop loop if the right file was found
                if area_name == bounding_box:
                    break

            # extract bounding box coordinates
            area_coordinates = np.array(
                area_object["features"][0]["geometry"]["coordinates"][0]
            )

            # create bounding box compliant with Sentinel Hub standards
            area_bounding_box = [
                np.nanmin(area_coordinates[:, 0]),
                np.nanmin(area_coordinates[:, 1]),
                np.nanmax(area_coordinates[:, 0]),
                np.nanmax(area_coordinates[:, 1]),
            ]

            # create Sentinel Hub BBox
            self.bounding_box = shb.BBox(bbox=area_bounding_box, crs=shb.CRS.WGS84)

            # bounding box name is known, so store it
            self.bounding_box_name = area_name

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

        # set Downloads folder as default main store folder
        if store_folder is None:
            store_folder = f"{Path.home()}/Downloads"

        # create folder if doesnt exist
        if not os.path.exists(store_folder):
            os.makedirs(store_folder)

        # set earthspy folder as default sub store folder
        if self.bounding_box_name is None:
            folder_name = "earthspy"

        # or use bounding box name (if available) to prevent overwrite
        else:
            folder_name = self.bounding_box_name

        # create full path
        full_path = f"{store_folder}/{folder_name}"

        # create subfolder if doesnt exist
        if not os.path.exists(full_path):
            os.makedirs(full_path)

        # set attribute
        self.store_folder = full_path

        return self.store_folder

    def convert_bounding_box_coordinates(self) -> Tuple[shb.geometry.BBox, list]:
        """Convert bounding boxe coordinates to a Geodetic Parameter Dataset (EPSG) in
        meter unit, default to EPSG:3413 (NSIDC Sea Ice Polar Stereographic
        North).

        :return: Bounding box coordinates in target projection.
        :rtype: list
        """

        # transform bbox into UTM CRS
        self.bounding_box_UTM = shb.to_utm_bbox(self.bounding_box)

        # recreate bounding box list from object
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

        # convert to meter projection
        self.convert_bounding_box_coordinates()

        # set an array of trial resolutions
        trial_resolutions = np.arange(self.data_collection_resolution, 10000)

        # compute x and y dimensions in meters
        dx = np.abs(self.bounding_box_UTM_list[2] - self.bounding_box_UTM_list[0])
        dy = np.abs(self.bounding_box_UTM_list[3] - self.bounding_box_UTM_list[1])

        # compute x and y dimensions in pixels for all trial resolutions
        nb_xpixels = (dx / trial_resolutions).astype(int)
        nb_ypixels = (dy / trial_resolutions).astype(int)

        try:

            # get max resolution while staying below Sentinel Hub max dimensions
            max_resolution = trial_resolutions[
                (nb_xpixels < 2500) & (nb_ypixels < 2500)
            ][1]

        # identify why max resolution was not found in trial resolutions
        except IndexError:

            # find the origin
            if np.sum(nb_xpixels < 2500) == 0 and np.sum(nb_ypixels < 2500) == 0:
                origin = "x and y"
            elif np.sum(nb_xpixels < 2500) == 0 and np.sum(nb_ypixels < 2500) != 0:
                origin = "x"
            elif np.sum(nb_xpixels < 2500) != 0 and np.sum(nb_ypixels < 2500) == 0:
                origin = "y"

            # inform user
            raise IndexError(
                "Calculated resolution above 10km "
                f"forced by {origin} dimension(s). "
                "Consider narrowing down the study area."
            )

        return max_resolution

    def set_correct_resolution(self) -> int:
        """Set download resolution based on a combination of download mode and user
        specifications.

        :return: Resolution in meters to use for data download.
        :rtype: int
        """

        # get max resolution to use in D download mode
        max_resolution = self.get_max_resolution()

        # set default resolutions
        if not self.resolution and self.download_mode == "D":
            self.resolution = max_resolution
        elif not self.resolution and self.download_mode == "SM":
            self.resolution = self.data_collection_resolution

        # resolution cant be higher than max resolution in D download mode
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

        # dont use SM download mode if D can be used with full resolution
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

        # convert to meter projection
        self.convert_bounding_box_coordinates()

        # compute x and y dimensions in meters
        dx = np.abs(self.bounding_box_UTM_list[2] - self.bounding_box_UTM_list[0])
        dy = np.abs(self.bounding_box_UTM_list[3] - self.bounding_box_UTM_list[1])

        # set an array of trial number of split boxes
        trial_split_boxes = np.arange(2, 100)

        # x and y pixel dimensions for each trial split box
        boxes_pixels_x = (dx / trial_split_boxes) / self.data_collection_resolution
        boxes_pixels_y = (dy / trial_split_boxes) / self.data_collection_resolution

        # get minimum number of split boxes needed to stay below Sentinel Hub max dimensions
        min_nb_boxes_x = int(trial_split_boxes[np.where(boxes_pixels_x <= 2500)[0][0]])
        min_nb_boxes_y = int(trial_split_boxes[np.where(boxes_pixels_y <= 2500)[0][0]])

        return min_nb_boxes_x, min_nb_boxes_y

    def get_split_boxes(self) -> list:
        """Build secondary bounding boxes used for the SM download mode.

        :return: Secondary bounding boxes matching the initial bounding box when
          merged.
        :rtype: list
        """

        # get optimal number of split boxes
        nb_boxes_x, nb_boxes_y = self.get_optimal_box_split()

        if self.verbose:
            print(
                f"Initial bounding box split into a ({nb_boxes_x}, "
                f"{nb_boxes_y}) grid"
            )

        # split initial bounding box with optimal split boxes
        bbox_splitter = shb.BBoxSplitter(
            [self.bounding_box_UTM.geometry],
            self.bounding_box_UTM.crs,
            (nb_boxes_x, nb_boxes_y),
        )

        # get split boxes
        bbox_list = bbox_splitter.get_bbox_list()

        # set attribute
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

        # extract text from URL
        self.evaluation_script = requests.get(evaluation_script).text

        return self.evaluation_script

    def set_split_boxes_ids(self) -> dict:
        """Set split boxes ids as simple integers to be accessed anytime in random order
        (mostly for multiprocessing).
        """

        # store split boxes ids in dict
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

        # if not set, set default evaluation script
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

        # if a URL, extract text
        elif validators.url(evaluation_script):

            self.evaluation_script = self.get_evaluation_script_from_link(
                evaluation_script
            )

        # if a str, set attribute directly
        elif isinstance(evaluation_script, str):

            self.evaluation_script = evaluation_script

        return self.evaluation_script

    def set_processing_iterator(self) -> str:
        """Set multiprocessing iterator depending on the number of days and
        split boxes to process to keep the CPUs busy.
        """

        # parallelize on acquisition dates
        if self.download_mode == "D" or len(self.query_date_range) > 5:
            self.multiprocessing_strategy = "acquisition_dates"
            self.multiprocessing_iterator = self.query_date_range

        # parallelize on split boxes
        elif self.download_mode == "SM" and len(self.query_date_range) <= 5:
            self.multiprocessing_strategy = "split_boxes"
            self.multiprocessing_iterator = self.split_boxes

        # dont paralellize
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

        # prepare iterators according to the multiprocessing strategy
        if (
            self.multiprocessing_strategy == "acquisition_dates"
            or not self.multiprocessing
        ):
            date_string = multiprocessing_iterator.strftime("%Y-%m-%d")
            sequential_iterator = self.split_boxes

        elif self.multiprocessing_strategy == "split_boxes":
            loc_bbox = multiprocessing_iterator
            sequential_iterator = self.query_date_range

        # store Sentinel Hub requests
        shb_requests = []

        # loop over sequential iterators
        for si in sequential_iterator:

            # set main variables according to the multiprocessing strategy
            if (
                self.multiprocessing_strategy == "acquisition_dates"
                or not self.multiprocessing
            ):
                loc_bbox = si

            elif self.multiprocessing_strategy == "split_boxes":
                date_string = si.strftime("%Y-%m-%d")

            # get bounding box size
            loc_size = shb.bbox_to_dimensions(loc_bbox, resolution=self.resolution)

            # build Sentinel Hub request
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

            # verbose statement
            if self.verbose:
                print(f"Downloading {date_string}...")

            # send Sentinel Hub Request
            if self.store_folder:
                outputs = request.get_data(save_data=True)
            else:
                outputs = request.get_data()

        # store request
        shb_requests.append(request)

        # if split boxes, use split box id as dictionnary key
        if self.download_mode == "SM":
            split_box_id = [
                k for k, v in self.split_boxes_ids.items() if v == loc_bbox
            ][0]
            self.outputs[f"{date_string}_{split_box_id}"] = outputs

        # if direct download, use date as dictionnary key
        elif self.download_mode == "D":
            self.outputs[date_string] = outputs

        return shb_requests

    def rename_output_files(self) -> None:
        """Reorganise the default folder structure and file naming of Sentinel Hub
        services.  Files are renamed using the acquisition date and the data
        collection. If download in SM mode, then the different rasters with the
        same date are numbered after the acquisition date.
        """

        # get raw folders created by Sentinel Hub API
        folders = [f"{self.store_folder}/{fn}" for fn in self.raw_filenames]

        # store new file names
        self.output_filenames = []

        for folder in folders:

            # open request JSON file
            with open(f"{folder}/request.json") as json_file:
                request = json.load(json_file)

            # extract date of acquisition
            date = request["payload"]["input"]["data"][0]["dataFilter"]["timeRange"][
                "from"
            ][:10]

            # if D download mode, set file name using date and data collection
            if self.download_mode == "D":

                # build new file name
                new_filename = (
                    f"{self.store_folder}/" + "{date}_{self.data_collection_str}.tif"
                )

            # if SM download mode, set file name using date, data collection and box id
            elif self.download_mode == "SM":

                # recreate split box
                split_box = shb.BBox(
                    request["payload"]["input"]["bounds"]["bbox"],
                    crs=self.bounding_box_UTM.crs,
                )

                # get split box id
                split_box_id = [
                    k for k, v in self.split_boxes_ids.items() if v == split_box
                ][0]

                # build new file name
                new_filename = (
                    f"{self.store_folder}/"
                    + f"{date}_{split_box_id}_{self.data_collection_str}.tif"
                )

            if os.path.exists(f"{folder}/response.tiff"):
                # rename file using new file name
                os.rename(f"{folder}/response.tiff", new_filename)
                self.output_filenames.append(new_filename)

        # remove raw storage folders
        for name in os.listdir(self.store_folder):
            if os.path.isdir(os.path.join(self.store_folder, name)):
                shutil.rmtree(f"{self.store_folder}/{name}")

        return None

    def send_sentinelhub_requests(self) -> None:
        """Send the Sentinel Hub API request depending on user specifications (mainly
        download mode and multiprocessing).
        """

        # store time and start time
        if self.verbose:
            start_time = time.time()
            start_local_time = time.ctime(start_time)

        # set iterators
        self.set_processing_iterator()

        if self.multiprocessing:

            # set number of cores to use depending on user input
            self.set_number_of_cores()

            # add support when Windows freezes to produce an executable (Move to Linux!)
            freeze_support()

            # save outputs
            self.outputs = {}

            # store raw folders created by Sentinel Hub API
            raw_filenames = []

            # start a pool of worker processes and give them jobs
            with Pool(self.nb_cores) as p:
                for shb_requests in p.map(
                    self.sentinelhub_request, self.multiprocessing_iterator
                ):

                    # get raw files names for renaming
                    if shb_requests is not None:
                        raw_filenames.append(
                            [
                                r.get_filename_list()[0].split(os.sep)[0]
                                for r in shb_requests
                            ]
                        )

        # if not multiprocessing, run in sequential
        else:
            requests = [
                self.sentinelhub_request(date) for date in self.query_date_range
            ]
            raw_filenames = [f.split(os.sep)[0] for f in requests.get_filename_list()]

        # flatten list of file name lists (coming from parallel processing)
        self.raw_filenames = [item for sublist in raw_filenames for item in sublist]

        # change raw ambiguous file names
        self.rename_output_files()

        # if SM download mode, merge rasters back to fit initial bounding box
        if self.download_mode == "SM":
            self.merge_rasters()

        # if verbose, print processing time
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

        # extract dates from file names
        dates = [f.split(os.sep)[-1].split("_")[0] for f in self.output_filenames]

        # get distinct dates because several split boxes a day
        distinct_dates = list(Counter(dates).keys())

        # store new file names
        self.output_filenames_renamed = []

        # merge rasters for each distinct date
        for date in distinct_dates:

            # select only files matching acquisition date
            date_output_files = [f for f in self.output_filenames if date in f]

            # set file name ofx merged raster
            date_output_filename = (
                date_output_files[0].rsplit(".", 4)[0] + "_mosaic.tif"
            )

            # add download mode in file name
            date_output_filename = date_output_filename.replace("_0_", "_SM_")

            # prepare GDAL parameters
            parameters = (
                ["", "-o", date_output_filename]
                + ["-n", "0.0"]
                + date_output_files
                + ["-co", "COMPRESS=LZW"]
            )

            # merge with GDAL
            gdal_merge.main(parameters)

            # save file name of merged raster
            self.output_filenames_renamed.append(date_output_filename)

        return None
