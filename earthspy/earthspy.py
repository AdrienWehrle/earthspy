# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, EO-IO, University of Zurich, Switzerland

"""

from datetime import datetime, timedelta
import glob
import json
from multiprocessing import cpu_count, Pool, freeze_support
import numpy as np
import os
from osgeo_utils import gdal_merge
import pandas as pd
import pyproj
import requests
from shapely.geometry import Polygon
import sentinelhub as shb
import shutil
import time
from typing import Union, Tuple
import validators


class EarthSpy:
    """Monitor and study any place on Earth and in Near Real-Time 
    (NRT) using the SentinelHub services.

    """

    def __init__(self, CLIENT_credentials_file: str) -> None:
        """
        :param CLIENT_credentials_file: full path to file
          containing credentials with User's OAuth client ID
          (1st row) secrect (2nd row).
        :type CLIENT_credentials_file: str
        """
        with open(CLIENT_credentials_file, "r") as file:
            credentials = file.read().splitlines()

        self.CLIENT_ID = credentials[0]
        self.CLIENT_SECRET = credentials[1]

        self.configure_connection()

        return None

    def configure_connection(self) -> shb.SHConfig:
        """Build a shb configuration class for the
        connection to Sentinel Hub services.

        :return: sentinelhub-py package configuration
          class.
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
        evaluation_script: str,
        data_collection: str,
        resolution: Union[None, int] = None,
        store_folder: Union[None, str] = None,
        multiprocessing: bool = True,
        nb_cores: Union[None, int] = None,
        download_mode: str = "SM",
        verbose: bool = True,
    ) -> None:
        """Define a set of parameters used for the
        API request.
        
        :param bounding_box: Area footprint with the 
          format [min_x, min_y, max_x, max_y]. An area
          name stored in a JSON database can also be 
          passed.
        :type bounding_box: Union[list, str]

        :param time_interval: Number of days from 
          present date or beginning and end date 
          strings.
        :type time_interval: Union[int, tuple]

        :param evaluation_script: Custom script 
          (preferably evalscript V3) or URL to
          a custom script on https://custom\
          -scripts.sentinel-hub.com/.
        :type evaluation_script: str

        :param data_collection: Data collection name
          as listed at https://sentinelhub-py.\
          readthedocs.io/en/latest/examples/\
          data_collections.html
        :type data_collection: str

        :param resolution: Resolution in meters to use 
          for data download, defaults to None. If not 
          specified, the raw data collection resolution 
          is used.
        :type resolution: Union[None, int], optional

        :param store_folder: Local path to folder where 
          data will be store, defaults to None. If not
          specified, path set to local ~/Downloads/earthspy.
        :type store_folder: Union[None, str], optional

        :param multiprocessing: Whether or not to download 
          in multiprocessing, defaults to True.
        :type multiprocessing: bool, optional

        :param nb_cores: Number of cores to use in 
          multiprocessing, defaults to None. If not 
          specified, set to the number of cores available 
          minus 2 (to avoid CPU overload).
        :type nb_cores: Union[None, int], optional

        :param download_mode: Whether to perform a 
          Direct (D) or Split and Merge (SM) download, 
          defaults to "SM". D uses the maximum
          resolution achievable keeping the 2500*2500 
          pixels maximum size set by Sentinel Hub
          services. SM breaks the initial area in as 
          many bounding boxes needed to achieve 
          specified (or raw) resolution.
        :type download_mode: str, optional

        :param verbose: Whether to print processing 
          status, defaults to True.
        :type verbose: bool, optional
        """

        self.multiprocessing = multiprocessing
        self.download_mode = download_mode
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

        if self.multiprocessing:
            self.set_number_of_cores(nb_cores)

        self.get_evaluation_script(evaluation_script)
        self.get_store_folder(store_folder)

        if download_mode == "D":
            self.split_boxes = [
                shb.BBox(bbox=self.bounding_box, crs=shb.CRS.WGS84)
            ]
        elif download_mode == "SM":
            self.get_split_boxes()

        return None

    def get_data_collection(self):
        """_summary_

        :return: _description_
        :rtype: _type_
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
                    "Satellite resolution not implemented yet. Data collection "
                    "resolution is set to 1km and will be refined."
                )

        return self.data_collection_resolution

    def set_number_of_cores(self, nb_cores: Union[None, int]) -> int:
        """Set number of cores depending on 
        user specifications.

        :param nb_cores: Number of cores to use
          in multiprocessing. 
        :type nb_cores: Union[None, int]
        
        :return: Number of cores to use
          in multiprocessing.
        :rtype: int
        """
        if not nb_cores:
            self.nb_cores = cpu_count() - 2

        elif isinstance(nb_cores, int):
            self.nb_cores = nb_cores

        return self.nb_cores

    def get_date_range(
        self, time_interval: Union[int, list]
    ) -> pd.core.indexes.datetimes.DatetimeIndex:
        """Get date range for data download
        depending on user specifications.

        :param time_interval: Number of days from 
          present date or beginning and end date 
          strings.
        :type time_interval: Union[int, list]

        :return: Data range (can be one-day long).
        :rtype: pd.core.indexes.datetimes.DatetimeIndex
        """
        if isinstance(time_interval, int):

            today = datetime.today().strftime("%Y-%m-%d")
            nb_days_back = (
                datetime.today() - timedelta(days=time_interval)
            ).strftime("%Y-%m-%d")
            self.date_range = pd.date_range(nb_days_back, today)

        elif isinstance(time_interval, list):

            if len(time_interval) > 1:
                self.date_range = pd.date_range(
                    time_interval[0], time_interval[1]
                )
            else:
                self.date_range = pd.date_range(
                    time_interval[0], time_interval[0]
                )

        elif isinstance(time_interval, str):
            self.date_range = pd.date_range(time_interval, time_interval)

        return self.date_range

    def get_bounding_box(self, bounding_box: Union[list, str]) -> list:
        """Get bounding box for data download
        depending on user specifications.

        :param bounding_box: Area footprint with the 
          format [min_x, min_y, max_x, max_y]. An area
          name stored in a JSON database can also be 
          passed.
        :type bounding_box: Union[list, str]

        :return: Area footprint with the 
          format [min_x, min_y, max_x, max_y]. An area
          name stored in a JSON database can also be 
          passed.
        :rtype: list
        """
        if isinstance(bounding_box, list):
            self.bounding_box = bounding_box
            self.crs = "4326"

        elif isinstance(bounding_box, str):

            area_bounding_boxes = pd.read_csv(
                "./area_bounding_boxes.csv", index_col=1
            )

            self.bounding_box = area_bounding_boxes[bounding_box]
            self.crs = area_bounding_boxes["crs"]

        return self.bounding_box

    def get_store_folder(self, store_folder: str) -> str:
        """Get folder path for data storage
        depending on user specifications.

        :param store_folder: Local path to folder where 
          data will be store, defaults to None. If not
          specified, path set to local ~/Downloads/earthspy.
        :type store_folder: str

        :return: Local path to folder where 
          data will be store.
        :rtype: str
        """
        if store_folder is None:
            store_folder = f"/home/{os.getlogin()}/Downloads"

        if not os.path.exists(store_folder):
            os.makedirs(store_folder)

        if isinstance(self.bounding_box, list):
            folder_name = "earthspy"

        elif isinstance(self.bounding_box, str):
            folder_name = self.bounding_box

        full_path = f"{store_folder}/{folder_name}"

        if not os.path.exists(full_path):
            os.makedirs(full_path)

        self.store_folder = full_path

        return self.store_folder

    def convert_bounding_box_coordinates(self) -> list:
        """Convert bounding boxe coordinates
        to a Geodetic Parameter Dataset (EPSG)
        in meter unit, default to EPSG:3413
        (NSIDC Sea Ice Polar Stereographic North).

        :return: Bounding box coordinates in target
          projection.
        :rtype: list
        """
        trf = pyproj.Transformer.from_crs(
            f"epsg:{self.crs}", "epsg:3413", always_xy=True
        )

        points = [
            pt
            for pt in trf.itransform(
                [
                    (self.bounding_box[0], self.bounding_box[1]),
                    (self.bounding_box[2], self.bounding_box[3]),
                ]
            )
        ]

        self.bounding_box_meters = [
            points[0][0],
            points[0][1],
            points[1][0],
            points[1][1],
        ]

        return self.bounding_box_meters

    def get_max_resolution(self) -> Union[int, None]:
        """Get maximum resolution reachable
        in Direct Download mode.

        :raises IndexError: Estimated resolution
          above 10 kilometers.

        :return: Resolution in meters to use 
          for data download.
        :rtype: Union[int, None]
        """
        self.convert_bounding_box_coordinates()

        # trial resolutions in meters
        trial_resolutions = np.arange(self.data_collection_resolution, 10000)

        dx = np.abs(self.bounding_box_meters[2] - self.bounding_box_meters[0])
        dy = np.abs(self.bounding_box_meters[3] - self.bounding_box_meters[1])

        nb_xpixels = (dx / trial_resolutions).astype(int)
        nb_ypixels = (dy / trial_resolutions).astype(int)

        try:

            max_resolution = trial_resolutions[
                (nb_xpixels < 2500) & (nb_ypixels < 2500)
            ][1]

        except IndexError:

            if (
                np.sum(nb_xpixels < 2500) == 0
                and np.sum(nb_ypixels < 2500) == 0
            ):
                origin = "x and y"
            elif (
                np.sum(nb_xpixels < 2500) == 0
                and np.sum(nb_ypixels < 2500) != 0
            ):
                origin = "x"
            elif (
                np.sum(nb_xpixels < 2500) != 0
                and np.sum(nb_ypixels < 2500) == 0
            ):
                origin = "y"

            raise IndexError(
                f"Calculated resolution above 10km forced by {origin} dimension(s). "
                "Consider narrowing down the study area."
            )
            return None

        return max_resolution

    def set_correct_resolution(self) -> int:
        """Set download resolution based on
        a combination of download mode and 
        user specifications.

        :return: Resolution in meters to use 
          for data download.
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
                    "The resolution entered is too high for a Direct Download (D) "
                    "and has been set to the maximum resolution achievable with D. "
                    "Consider using the Split and Merge Download (SM) to always attain "
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
        """Get the minimum number of bounding boxes to 
        achieve maximum resolution in SM download mode.

        :return: Minimum number of boxes in x and y
          directions (1st and 2nd values, respectively).
        :rtype: Tuple[int, int]
        """
        self.convert_bounding_box_coordinates()

        dx = np.abs(self.bounding_box_meters[2] - self.bounding_box_meters[0])
        dy = np.abs(self.bounding_box_meters[3] - self.bounding_box_meters[1])

        trial_split_boxes = np.arange(2, 100)

        boxes_pixels_x = (
            dx / trial_split_boxes
        ) / self.data_collection_resolution
        boxes_pixels_y = (
            dy / trial_split_boxes
        ) / self.data_collection_resolution

        min_nb_boxes_x = int(
            trial_split_boxes[np.where(boxes_pixels_x <= 2500)[0][0]]
        )
        min_nb_boxes_y = int(
            trial_split_boxes[np.where(boxes_pixels_y <= 2500)[0][0]]
        )

        return min_nb_boxes_x, min_nb_boxes_y

    def get_split_boxes(self) -> list:
        """Build secondary bounding boxes used 
        for the SM download mode.

        :return: Secondary bounding boxes matching
          the initial bounding box when merged.
        :rtype: list
        """
        nb_boxes_x, nb_boxes_y = self.get_optimal_box_split()

        if self.verbose:
            print(
                f"Initial bounding box will be split into a ({nb_boxes_x}, "
                f"{nb_boxes_y}) grid"
            )

        bbox = [
            (self.bounding_box[0], self.bounding_box[1]),
            (self.bounding_box[2], self.bounding_box[1]),
            (self.bounding_box[2], self.bounding_box[3]),
            (self.bounding_box[0], self.bounding_box[3]),
        ]

        bbox_polygon = Polygon(bbox)

        bbox_splitter = shb.BBoxSplitter(
            [bbox_polygon], "epsg:4326", (nb_boxes_x, nb_boxes_y)
        )

        bbox_list = bbox_splitter.get_bbox_list()

        self.split_boxes = bbox_list

        return self.split_boxes

    def get_evaluation_script_from_link(
        self, evaluation_script: Union[None, str]
    ) -> None:
        """_summary_

        :param evaluation_script: _description_
        :type evaluation_script: Union[None, str]
        :return: _description_
        :rtype: _type_
        """
        self.evaluation_script = requests.get(evaluation_script).text

        return self.evaluation_script

    def get_evaluation_script(
        self, evaluation_script: Union[None, str]
    ) -> None:
        """_summary_

        :param evaluation_script: _description_
        :type evaluation_script: Union[None, str]
        :return: _description_
        :rtype: _type_
        """
        if not evaluation_script:

            if self.satellite == "SENTINEL2":
                self.get_evaluation_script_from_link(
                    "https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/"
                    + "true_color/script.js"
                )
            elif self.satellite == "SENTINEL1":
                self.get_evaluation_script_from_link(
                    "https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-1/"
                    + "sar_rvi_temporal_analysis/script.js"
                )

        elif validators.url(evaluation_script):

            self.evaluation_script = self.get_evaluation_script_from_link(
                evaluation_script
            )

        elif isinstance(evaluation_script, str):

            self.evaluation_script = evaluation_script

        return self.evaluation_script

    def sentinelhub_request(
        self, date: pd._libs.tslibs.timestamps.Timestamp
    ) -> Tuple[str, list]:
        """_summary_

        :param date: _description_
        :type date: pd._libs.tslibs.timestamps.Timestamp
        :return: _description_
        :rtype: Tuple[str, list]
        """
        date_string = date.strftime("%Y-%m-%d")

        for loc_bbox in self.split_boxes:

            loc_size = shb.bbox_to_dimensions(
                loc_bbox, resolution=self.resolution
            )

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
                return None

            else:
                print(f"Downloading {date_string}...")
                if self.store_folder:
                    request.save_data()

        return date_string, outputs

    def rename_output_files(self) -> None:
        """_summary_

        :return: _description_
        :rtype: _type_
        """
        folders = glob.glob(f"{self.store_folder}/*")

        self.output_filenames = []

        for i, folder in enumerate(folders):

            with open(f"{folder}/request.json") as json_file:
                request = json.load(json_file)

            date = request["payload"]["input"]["data"][0]["dataFilter"][
                "timeRange"
            ]["from"][:10]

            if self.download_mode == "D":
                new_filename = f"{self.store_folder}/{date}_{self.data_collection_str}.tif"
            elif self.download_mode == "SM":
                new_filename = f"{self.store_folder}/{date}_{i}_{self.data_collection_str}.tif"

            os.rename(f"{folder}/response.tiff", new_filename)

            self.output_filenames.append(new_filename)

        # remove temporary folders
        for name in os.listdir(self.store_folder):
            if os.path.isdir(os.path.join(self.store_folder, name)):
                shutil.rmtree(f"{self.store_folder}/{name}")

        return None

    def send_sentinelhub_requests(self) -> None:
        """_summary_
        """
        if self.verbose:
            start_time = time.time()
            start_local_time = time.ctime(start_time)

        if self.multiprocessing:

            # message about windows
            freeze_support()

            self.outputs = {}

            with Pool(self.nb_cores) as p:
                for date, output in p.map(
                    self.sentinelhub_request, self.date_range
                ):
                    self.outputs[date] = output

        else:
            self.outputs = [
                self.sentinelhub_request(date) for date in self.date_range
            ]

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

    def merge_rasters(self):
        """_summary_

        :return: _description_
        :rtype: _type_
        """
        output_files = sorted(glob.glob(f"{self.store_folder}/*.tif"))
        output_filename = output_files[0].rsplit(".", 4)[0] + "_mosaic.tif"

        parameters = (
            ["", "-o", output_filename]
            + ["-n", "0.0"]
            + output_files
            + ["-co", "COMPRESS=LZW"]
        )

        gdal_merge.main(parameters)

        return None

    def create_png_visuals(self):
        """_summary_

        :return: _description_
        :rtype: _type_
        """
        return None
