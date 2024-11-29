# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, EO-IO, University of Zurich, Switzerland

"""

from collections import Counter
from datetime import datetime, timedelta
import glob
import json
from multiprocessing import cpu_count
import numpy as np
import objectpath
import os
import pandas as pd
from pathlib import Path
import rasterio
from rasterio.merge import merge
import requests
import sentinelhub as shb
import shutil
import tarfile
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

        # modify default download parameters for batch downloads
        self.config.download_timeout_seconds = 300
        self.config.download_sleep_time = 20

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
        algorithm: Union[None, str] = None,
        resolution: Union[None, int] = None,
        store_folder: Union[None, str] = None,
        multithreading: bool = True,
        nb_cores: Union[None, int] = None,
        download_mode: str = "SM",
        remove_splitboxes: bool = True,
        verbose: bool = True,
        raster_compression: str = None
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

        :param algorithm: Name of the algorithm to apply (some algorithms
          would require a large number of variables to be set by the user, we
          therefore decided to encapsule them).
        :type algorithm: Union[None, str], optional

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

        :param multithreading: Whether or not to download in multithreading,
          defaults to True.
        :type multithreading: bool, optional

        :param nb_cores: Number of cores to use in multithreading, defaults to
          None. If not specified, set to the number of cores available minus 2
          (to avoid CPU overload).
        :type nb_cores: Union[None, int], optional

        :param download_mode: Whether to perform a Direct (D) or Split and Merge
          (SM) download, defaults to "SM". D uses the maximum resolution
          achievable keeping the 2500*2500 pixels maximum size set by Sentinel
          Hub services. SM breaks the initial area in as many bounding boxes
          needed to achieve specified (or raw) resolution.
        :type download_mode: str, optional

        :param remove_splitboxes: Whether to remove rasters of split boxes
          after merge (mosaic creation) or not.
        :type download_mode: bool, optional

        :param verbose: Whether to print processing status or not, defaults
          to True.
        :type verbose: bool, optional
        
        :param raster_compression: Raster compression to apply following methods
          available in rasterio, defaults to None.
        :type raster_compression: Union[None, str], optional
        """

        # set processing attributes
        self.download_mode = download_mode
        self.multithreading = multithreading
        self.verbose = verbose
        self.remove_splitboxes = remove_splitboxes
        self.algorithm = algorithm

        # set query attributes
        self.data_collection_str = data_collection
        self.get_data_collection()
        self.get_satellite_name()
        self.get_raw_data_collection_resolution()

        # set number of cores
        self.set_number_of_cores(nb_cores)

        # set initial spatial and temporal coverage
        self.get_date_range(time_interval)
        self.get_bounding_box(bounding_box)

        self.resolution = resolution

        # set and correct resolution
        self.set_correct_resolution()
        
        # set compress mode
        self.get_raster_compression(raster_compression)

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

    def get_raster_compression(self, raster_compression) -> str:
        """Verify valid keyword for raster compression
        
        :return: Compression mode
        """
        
        if raster_compression in ['DEFLATE','LZW','PACKBITS','JPEG', 'WEBP','LZMA','ZSTD']:
           self.raster_compression = raster_compression
        elif raster_compression == None:
            self.raster_compression = None
        else:
          raise KeyError("Compression mode not found")
        
        return self.raster_compression

    def get_data_collection(self) -> shb.DataCollection:
        """Get Sentinel Hub DataCollection object from data collection name.


        :return: DataCollection object containing all information needed for
          download (such as bands, sensor type...).
        :rtype: shb.DataCollection
        """

        # set Sentinel Hub data collection object
        if self.algorithm == "SICE":
            self.data_collection = shb.DataCollection.SENTINEL3_OLCI
        else:
            self.data_collection = shb.DataCollection[self.data_collection_str]

        return self.data_collection

    def get_available_data(self) -> list:
        """Search for available data with STAC REST API before download."""

        # create a copy of shb configuration to get catalog
        self.catalog_config = self.config.copy()

        # setup Sentinel Hub Catalog API (with STAC Specification)
        self.catalog = shb.SentinelHubCatalog(config=self.catalog_config)

        # search catalog based on user inputs
        search_iterator = [
            self.catalog.search(
                self.data_collection,
                bbox=self.bounding_box,
                time=d.strftime("%Y-%m-%d"),
            )
            for d in self.user_date_range
        ]

        # some data sets require a difference service_url, test search_iterator
        # and update service_url if dowload failed
        try:
            # store metadata of available scenes
            self.metadata = [list(iterator) for iterator in search_iterator]

        except shb.exceptions.DownloadFailedException:
            # set specific base URL of deployment
            self.catalog_config.sh_base_url = shb.DataCollection[
                self.data_collection_str
            ].service_url

            # setup Sentinel Hub Catalog API (with STAC Specification)
            self.catalog = shb.SentinelHubCatalog(config=self.catalog_config)

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

    def get_raw_data_collection_resolution(self) -> int:
        """Get lowest raw data collection resolution possible (then
        refined at the download stage).

        :return: Data collection resolution.
        :rtype: int

        """

        # set default satellite resolution
        if self.satellite == "SENTINEL1":
            self.raw_data_collection_resolution = 5
        elif self.satellite == "SENTINEL2":
            self.raw_data_collection_resolution = 10
        elif self.satellite == "SENTINEL3":
            self.raw_data_collection_resolution = 300
        elif self.satellite == "LANDSAT":
            self.raw_data_collection_resolution = 15
        else:
            self.raw_data_collection_resolution = 1000

            if self.verbose:
                print(
                    "Satellite resolution not implemented yet. Data "
                    "collection resolution is set to 1km and will "
                    "be refined."
                )

        return self.raw_data_collection_resolution

    def set_number_of_cores(self, nb_cores) -> int:
        """Set number of cores if not specificed by user.

        :return: Number of cores to use in multithreading.
        :rtype: int
        """

        # set number of cores provided by user
        if self.multithreading and isinstance(nb_cores, (int, float)):
            self.nb_cores = nb_cores

        # keep two CPUs free to prevent overload
        elif self.multithreading and nb_cores is None:
            self.nb_cores = cpu_count() - 2

        # if not multithreading, sequential processing
        elif not self.multithreading:
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
        if not store_folder:
            store_folder = f"{Path.home()}/Downloads/earthspy"

            # set earthspy folder as default sub store folder
            if self.bounding_box_name:
                store_folder += f"{os.sep}{self.bounding_box_name}"

            if self.algorithm:
                store_folder += f"{os.sep}{self.algorithm}"

        # create subfolder if doesnt exist
        if not os.path.exists(store_folder):
            os.makedirs(store_folder)

        # set attribute
        self.store_folder = store_folder

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
        trial_resolutions = np.arange(self.raw_data_collection_resolution, 10000)

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
            self.resolution = self.raw_data_collection_resolution

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

        # dont use SM download mode if D can be used with full resolution
        if (
            max_resolution == self.raw_data_collection_resolution
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
        boxes_pixels_x = (dx / trial_split_boxes) / self.resolution
        boxes_pixels_y = (dy / trial_split_boxes) / self.resolution

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
        (mostly for multithreading).
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

    def list_requests(self) -> list:
        """ """

        # loop over dates if direct download
        if self.download_mode == "D":
            requests_list = [
                self.sentinelhub_request(date, self.split_boxes[0])
                for date in self.query_date_range
            ]

        # loop over dates and split boxes if Split-and-Merge download
        elif self.download_mode == "SM":
            requests_list = [
                [
                    self.sentinelhub_request(date, split_box)
                    for date in self.query_date_range
                ]
                for split_box in self.split_boxes
            ]

        # create list of requests
        if self.download_mode == "D":
            self.requests_list = requests_list

        elif self.download_mode == "SM":
            self.requests_list = [item for sublist in requests_list for item in sublist]

        # create list of download requests
        self.download_list = [item.download_list[0] for item in self.requests_list]

        return self.requests_list

    def sentinelhub_request(
        self, date: pd._libs.tslibs.timestamps.Timestamp, loc_bbox: shb.geometry.BBox
    ) -> list:
        """Send the Sentinel Hub API request with settings depending on the
        multithreading strategy.

        If parallelized on split_boxes, then date_range is run in sequence for
        each split box. If parallelized on date_range, then split_boxes are run
        in sequence (all split boxes for one date run on the same CPU).

        :param date: Date to process.
        :type date: pd._libs.tslibs.timestamps.Timestamp

        :return: List of the Sentinel Hub requests run in sequence
        :rtype: list

        """

        # get bounding box size
        loc_size = shb.bbox_to_dimensions(loc_bbox, resolution=self.resolution)

        # convert datetime to string
        date_string = date.strftime("%Y-%m-%d")

        # build Sentinel Hub request
        shb_request = shb.SentinelHubRequest(
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
                shb.SentinelHubRequest.output_response("default", shb.MimeType.TIFF),
            ],
            bbox=loc_bbox,
            size=loc_size,
            config=self.config,
        )

        if self.algorithm == "SICE":
            self.response_files = [
                "r_TOA_01",
                "r_TOA_06",
                "r_TOA_17",
                "r_TOA_21",
                "snow_grain_diameter",
                "snow_specific_surface_area",
                "diagnostic_retrieval",
                "albedo_bb_planar_sw",
                "albedo_bb_spherical_sw",
            ]

            shb_request = shb.SentinelHubRequest(
                data_folder=self.store_folder,
                evalscript=self.evaluation_script,
                input_data=[
                    shb.SentinelHubRequest.input_data(
                        data_collection=shb.DataCollection.DEM_COPERNICUS_30,
                        identifier="COP_30",
                        upsampling="NEAREST",
                        downsampling="NEAREST",
                    ),
                    shb.SentinelHubRequest.input_data(
                        data_collection=shb.DataCollection.SENTINEL3_OLCI,
                        identifier="OLCI",
                        time_interval=(date_string, date_string),
                        upsampling="NEAREST",
                        downsampling="NEAREST",
                    ),
                ],
                responses=[
                    shb.SentinelHubRequest.output_response(rf, shb.MimeType.TIFF)
                    for rf in self.response_files
                ],
                bbox=loc_bbox,
                size=loc_size,
                config=self.config,
            )

        return shb_request

    def send_sentinelhub_requests(self) -> list:
        """Send the Sentinel Hub API request depending on user specifications (mainly
        download mode and multithreading).
        """

        # list SentinelHub requests to send over
        self.list_requests()

        # store time and start time
        if self.verbose:
            start_time = time.time()
            start_local_time = time.ctime(start_time)

        # the actual Sentinel Hub download
        self.outputs = shb.SentinelHubDownloadClient(config=self.config).download(
            self.download_list, max_threads=20, show_progress=True
        )

        # store raw folders created by Sentinel Hub API
        self.raw_folder_names = [
            r.get_filename_list()[0].split(os.sep)[0] for r in self.requests_list
        ]

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

        return self.outputs

    def extract_sentinelhub_responses(self, folders: list) -> None:
        """Extract all members of a Tape ARchive produced by the Sentinel Hub
        API.

        :param folders: List of folders containing outputs.
        :type folders: list
        """

        for folder in folders:
            # open Tape ARchive file produced by Sentinel Hub API
            tar = tarfile.open(f"{folder}/response.tar", "r:")

            # extract all members from the archive
            tar.extractall(path=folder, filter="data")

            # close the TAR file
            tar.close()

        return None

    def rename_output_files(self) -> None:
        """Reorganise the default folder structure and file naming of Sentinel Hub
        services.  Files are renamed using the acquisition date and the data
        collection. If download in SM mode, then the different rasters with the
        same date are numbered after the acquisition date.
        """

        # get raw folders created by Sentinel Hub API
        folders = [f"{self.store_folder}/{fn}" for fn in self.raw_folder_names]

        # extract outputs stored in archives
        if self.algorithm == "SICE":
            self.extract_sentinelhub_responses(folders)

        # store new file names
        self.output_filenames = []

        for folder in folders:
            # open request JSON file
            with open(f"{folder}/request.json") as json_file:
                request = json.load(json_file)

            # create a tree object to facilitate queries
            request_tree = objectpath.Tree(request)

            # extract date of acquisition
            date = list(request_tree.execute("$..timeRange"))[0]["from"].split("T")[0]

            # if SICE, store files in date subfolders if multiple outputs
            if self.algorithm == "SICE":
                # build folder name
                date_folder = f"{self.store_folder}/{date}"

                # create folder if doesn't exist
                if not os.path.exists(date_folder):
                    os.makedirs(date_folder)

                # list all output files available for date
                date_files = sorted(glob.glob(f"{folder}/*.tif"))

            # if D download mode, set file name using date and data collection
            if self.download_mode == "D":
                # build new file name
                new_filename = (
                    f"{self.store_folder}/" + "{date}_{self.data_collection_str}.tif"
                )

                # If SICE, don't rename file but move to date folder
                if self.algorithm == "SICE":
                    for f in date_files:
                        # include date in path
                        os.rename(
                            f, f"{self.store_folder}/{date}/{f.split(os.sep)[-1]}"
                        )

                        # store output file name
                        self.output_filenames.append(f)

            # if SM download mode, set file name using date, data collection and box id
            elif self.download_mode == "SM":
                # recreate split box
                split_box = shb.BBox(
                    list(request_tree.execute("$..bbox")),
                    crs=self.bounding_box_UTM.crs,
                )

                # get split box id
                split_box_id = [
                    k for k, v in self.split_boxes_ids.items() if v == split_box
                ][0]

                # build new file name
                new_filename = (
                    f"{self.store_folder}/"
                    + f"{date}_{self.data_collection_str}_{split_box_id}.tif"
                )

                # if SICE, add split box id in all names and move to date folder
                if self.algorithm == "SICE":
                    for f in date_files:
                        # extract absolute path
                        absolute_file_name = f.split(os.sep)[-1]
                        new_absolute_file_name = absolute_file_name.replace(
                            ".tif", f"_{split_box_id}.tif"
                        )

                        # include date in path
                        new_full_file_name = (
                            f"{self.store_folder}/{date}/{new_absolute_file_name}"
                        )

                        # rename file
                        os.rename(f, new_full_file_name)

                        # store output file name
                        self.output_filenames.append(new_full_file_name)

            # rename file using new file name
            if os.path.exists(f"{folder}/response.tiff"):
                os.rename(f"{folder}/response.tiff", new_filename)
                self.output_filenames.append(new_filename)

        # remove raw storage folders (and not date folders!)
        for name in os.listdir(self.store_folder):
            if (
                os.path.isdir(os.path.join(self.store_folder, name))
            ) and "-" not in name:
                shutil.rmtree(f"{self.store_folder}/{name}")

        return None

    def merge_rasters(self) -> None:
        """Merge raster files downloaded in SM download mode using GDAL merge
        capability.  A "mosaic" code is added to the name of the file in which
        the different rasters have been merged.
        """

        # extract dates from file or folder names (depending on algorithm)
        if self.algorithm == "SICE":
            dates = [f.split(os.sep)[-2] for f in self.output_filenames]
        else:
            dates = [f.split(os.sep)[-1].split("_")[0] for f in self.output_filenames]

        # get distinct dates because several split boxes a day
        distinct_dates = list(Counter(dates).keys())

        # store new file names
        self.output_filenames_renamed = []

        # merge rasters for each distinct date (work with distinct dates because
        # of different trees depending on the algorithm used)
        for date in distinct_dates:
            # select files matching acquisition date only
            date_output_files = [f for f in self.output_filenames if date in f]

            # loop over response files if multiple ones (they all need to be
            # merged, but only to their respective boxes)
            if self.algorithm == "SICE":
                file_iterator = self.response_files
            else:
                # set to tif to select all files (but keep a general file_iterator)
                file_iterator = ["tif"]

            for pattern in file_iterator:
                date_response_files = [f for f in date_output_files if pattern in f]

                # set file name of merged raster: replace split box id by mosaic
                # and add download method name (SM)
                date_output_filename = date_response_files[0].replace(
                    "_0.tif",
                    "_SM_mosaic.tif",
                )

                # open files to merge
                rasters_to_merge = [rasterio.open(file) for file in date_response_files]

                # extract metadata
                output_meta = rasters_to_merge[0].meta.copy()

                # merge rasters
                mosaic, output_transform = merge(rasters_to_merge)

                # prepare mosaic metadata
                output_meta.update(
                    {
                        "driver": "GTiff",
                        "height": mosaic.shape[1],
                        "width": mosaic.shape[2],
                        "transform": output_transform,
                        "compress": self.raster_compression
                    }
                )

                # write mosaic
                with rasterio.open(date_output_filename, "w", **output_meta) as dst:
                    dst.write(mosaic)

                # save file name of merged raster
                self.output_filenames_renamed.append(date_output_filename)

                # remove split boxes to keep only the mosaic
                if self.remove_splitboxes:
                    for file in date_response_files:
                        os.remove(file)

        return None
