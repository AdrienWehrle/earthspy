# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, EO-IO, University of Zurich, Switzerland

TODO:
  - comment code properly
  - generate documentation
  - add tests
  - write NRT wrapper
  - add simple visualisations so rasters don't have to be loaded for
    very superficial checks

"""

from datetime import datetime, timedelta
import glob
import json
from multiprocessing import cpu_count, Pool, freeze_support
import numpy as np
import os
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
    def __init__(self, CLIENT_credentials_file: str) -> None:

        with open(CLIENT_credentials_file, "r") as file:
            credentials = file.read().splitlines()

        self.CLIENT_ID = credentials[0]
        self.CLIENT_SECRET = credentials[1]

        self.configure_connection()

        return None

    def configure_connection(self) -> shb.SHConfig:

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
        resolution: Union[int, None] = None,
        store_folder: Union[str, None] = None,
        multiprocessing: bool = True,
        nb_cores: Union[int, None] = None,
        download_method: str = "SPD",
        verbose: bool = True,
    ) -> None:

        self.multiprocessing = multiprocessing
        self.download_method = download_method
        self.verbose = verbose

        self.data_collection_str = data_collection
        self.get_data_collection()
        self.get_data_collection_resolution()

        if self.multiprocessing:
            self.set_number_of_cores(nb_cores)

        self.get_date_range(time_interval)
        self.get_bounding_box(bounding_box)

        if resolution:
            self.resolution = resolution
        else:
            max_resolution = self.get_max_resolution()

        if (
            max_resolution == self.data_collection_resolution
            and self.download_method == "SPD"
        ):
            self.download_method = "DD"

            if self.verbose:
                print(
                    "Split and Merge Download (SPD) is not needed to reach "\
                    "the maximum data resolution. Switching to Direct "\
                    "Download (DD)."
                )
        self.get_evaluation_script(evaluation_script)
        self.get_store_folder(store_folder)

        return None

    def get_data_collection(self):

        self.data_collection = shb.DataCollection[self.data_collection_str]

        return self.data_collection

    def get_data_collection_resolution(self):

        satellite = self.data_collection_str.split("_")[0]

        if satellite == "SENTINEL1":
            self.data_collection_resolution = 5
        elif satellite == "SENTINEL2":
            self.data_collection_resolution = 10
        elif satellite == "SENTINEL3":
            self.data_collection_resolution = 300
        else:
            self.data_collection_resolution = 1000

            if self.verbose:
                print(
                    "Satellite resolution not implemented yet. Data collection "\
                    "resolution is set to 1km and will be refined."
                )

        return self.data_collection_resolution

    def set_number_of_cores(self, nb_cores: Union[None, int]):

        if not nb_cores:
            self.nb_cores = cpu_count() - 2

        elif isinstance(nb_cores, int):
            self.nb_cores = nb_cores

        return self.nb_cores

    def get_date_range(
        self, time_interval: Union[int, list]
    ) -> pd.core.indexes.datetimes.DatetimeIndex:

        if isinstance(time_interval, int):

            today = datetime.today().strftime("%Y-%m-%d")
            nb_days_back = (datetime.today() - timedelta(days=time_interval)).strftime(
                "%Y-%m-%d"
            )

            date_range = pd.date_range(nb_days_back, today)
            self.date_range = date_range

        elif isinstance(time_interval, list):

            date_range = pd.date_range(time_interval[0], time_interval[1])
            self.date_range = date_range

        return self.date_range

    def get_bounding_box(self, bounding_box) -> list:

        if isinstance(bounding_box, list):
            self.bounding_box = bounding_box
            self.crs = "4326"

        elif isinstance(bounding_box, str):

            area_bounding_boxes = pd.read_csv("./area_bounding_boxes.csv", index_col=1)

            self.bounding_box = area_bounding_boxes[bounding_box]
            self.crs = area_bounding_boxes["crs"]

        return self.bounding_box

    def get_store_folder(self, store_folder) -> str:

        if not os.path.exists(store_folder):
            os.makedirs(store_folder)

        if isinstance(self.bounding_box, list):
            folder_name = "glacierspy"

        elif isinstance(self.bounding_box, str):
            folder_name = self.bounding_box

        full_path = f"{store_folder}/{folder_name}"

        if not os.path.exists(full_path):
            os.makedirs(full_path)

        self.store_folder = full_path

        return self.store_folder

    def convert_bounding_box_coordinates(self):

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

    def get_max_resolution(self) -> None:

        self.convert_bounding_box_coordinates()

        # trial resolutions in meters
        trial_resolutions = np.arange(self.data_collection_resolution, 10000)

        dy = np.abs(self.bounding_box_meters[2] - self.bounding_box_meters[0])
        dx = np.abs(self.bounding_box_meters[3] - self.bounding_box_meters[1])

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
                f"Calculated resolution above 10km forced by {origin} dimension(s), "\
                "please narrow down your study area."
            )
            return None  # self.resolution = None

        if "max_resolution" in locals() and max_resolution > self.resolution:

            self.resolution = max_resolution

            if self.verbose:
                print(
                    'The resolution entered is too high for a Direct Download (DD) '\
                    'and has been set to the maximum resolution achievable withis method. '\
                    'Consider using the Split and Merge Download (SMD) to always attain '\
                    'the highest resolution independently of the area.'\
                )

        return max_resolution

    def get_optimal_box_split(self):

        self.convert_bounding_box_coordinates()

        dx = np.abs(self.bounding_box_meters[2] - self.bounding_box_meters[0])
        dy = np.abs(self.bounding_box_meters[3] - self.bounding_box_meters[1])

        trial_split_boxes = np.arange(2, 100)

        boxes_pixels_x = (dx / trial_split_boxes) / self.data_collection_resolution
        boxes_pixels_y = (dy / trial_split_boxes) / self.data_collection_resolution

        min_nb_boxes_x = trial_split_boxes[np.where(boxes_pixels_x <= 2500)[0][0]]
        min_nb_boxes_y = trial_split_boxes[np.where(boxes_pixels_y <= 2500)[0][0]]

        return min_nb_boxes_x, min_nb_boxes_y

    def get_split_boxes(self):

        nb_boxes_x, nb_boxes_y = self.get_optimal_box_split()

        if self.verbose:
            print(
                f"Initial bounding box will be split into a ({nb_boxes_x}, {nb_boxes_y}) grid"
            )

        bbox = [
            (self.bounding_box[0][0], self.bounding_box[0][1]),
            (self.bounding_box[1][0], self.bounding_box[0][1]),
            (self.bounding_box[1][0], self.bounding_box[1][1]),
            (self.bounding_box[0][0], self.bounding_box[1][1]),
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

        self.evaluation_script = requests.get(evaluation_script).text

        return self.evaluation_script

    def get_evaluation_script(self, evaluation_script: Union[None, str]) -> None:

        if not evaluation_script:

            if self.data_collection_str == "SENTINEL2_L2A":
                self.get_evaluation_script_from_link(
                    "https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/"
                    + "true_color/script.js"
                )
            elif self.data_collection_str == "S1":
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

        date_string = date.strftime("%Y-%m-%d")

        loc_bbox = shb.BBox(bbox=self.bounding_box, crs=shb.CRS.WGS84)
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
            responses=[shb.SentinelHubRequest.output_response("default", shb.MimeType.TIFF),],
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

        folders = glob.glob(f"{self.store_folder}/*")

        self.output_filenames = []

        for i, folder in enumerate(folders):

            with open(f"{folder}/request.json") as json_file:
                request = json.load(json_file)

            date = request["payload"]["input"]["data"][0]["dataFilter"]["timeRange"][
                "from"
            ][:10]

            if self.download_method == "DD":
                new_filename = (
                    f"{self.store_folder}/{date}_{self.data_collection_str}.tif"
                )
            elif self.download_method == "SMD":
                new_filename = (
                    f"{self.store_folder}/{date}_{i}_{self.data_collection_str}.tif"
                )

            os.rename(f"{folder}/response.tiff", new_filename)

            self.output_filenames.append(new_filename)

        # remove temporary folders
        for name in os.listdir(self.store_folder):
            if os.path.isdir(os.path.join(self.store_folder, name)):
                shutil.rmtree(f"{self.store_folder}/{name}")

        return None

    def send_sentinelhub_requests(self) -> None:

        if self.verbose:
            start_time = time.time()
            start_local_time = time.ctime(start_time)

        if self.multiprocessing:

            # message about windows
            freeze_support()

            self.outputs = {}

            with Pool(self.nb_cores) as p:
                for date, output in p.map(self.sentinelhub_request, self.date_range):
                    self.outputs[date] = output

        else:
            self.outputs = [self.sentinelhub_request(date) for date in self.date_range]

        self.rename_output_files()

        if self.verbose:
            end_time = time.time()
            end_local_time = time.ctime(end_time)
            processing_time = (end_time - start_time) / 60
            print("--- Processing time: %s minutes ---" % processing_time)
            print("--- Start time: %s ---" % start_local_time)
            print("--- End time: %s ---" % end_local_time)

    def create_png_visuals(self):

        for file in self.output_filenames:

            # TODO
            c = False
