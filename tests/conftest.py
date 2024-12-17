#!/usr/bin/env python3
"""

@authors: Adrien Wehrlé (EO-IO), Antsalacia

"""

import os

import pytest

import earthspy.earthspy as es


def pytest_addoption(parser):
    """Add option to pass local path to authentication file"""
    parser.addoption(
        "--authfile",
        action="store",
        default="./auth.txt",
        help="Full path to Sentinel Hub credential file containing ID and password",
    )


# if running in Github action
if os.getenv("CI") is not None:

    @pytest.fixture(scope="session")
    def SH_CLIENT_ID() -> None:
        """Create local client id from environment variable"""
        # check if variable in environment variables
        SH_CLIENT_ID = os.environ["SH_CLIENT_ID"]
        return SH_CLIENT_ID

    @pytest.fixture(scope="session")
    def SH_CLIENT_SECRET() -> None:
        """Create local client secret from environment variable"""
        # check if variable in environment variables
        SH_CLIENT_SECRET = os.environ["SH_CLIENT_SECRET"]
        return SH_CLIENT_SECRET

    # path to credential file to be created
    @pytest.fixture(scope="session")
    def authfile(SH_CLIENT_ID, SH_CLIENT_SECRET):
        """Set credential file name and create credential file
        for testing"""
        authfile = "auth.txt"
        with open(authfile, "w") as out:
            out.write(f"{SH_CLIENT_ID}\n{SH_CLIENT_SECRET}")
        return authfile


# if running locally
else:

    @pytest.fixture(scope="session")
    def authfile(pytestconfig):
        """Get option from command line call"""
        return pytestconfig.getoption("authfile")

    @pytest.fixture(scope="session")
    def credentials(authfile):
        """Read credentials stored in text file"""

        with open(authfile) as file:
            credentials = file.read().splitlines()
        return credentials

    @pytest.fixture(scope="session")
    def SH_CLIENT_ID(credentials) -> None:
        """Extract client id from line"""
        SH_CLIENT_ID = credentials[0]
        return SH_CLIENT_ID

    @pytest.fixture(scope="session")
    def SH_CLIENT_SECRET(credentials) -> None:
        """Extract client secret from line"""
        SH_CLIENT_SECRET = credentials[1]
        return SH_CLIENT_SECRET


@pytest.fixture(scope="session")
def test_evalscript():
    """Set a test evalscript for Sentinel-2"""
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
    return test_evalscript


@pytest.fixture(scope="session")
def test_url():
    """Set a test evalscript pointing to Sentinel-2 True Color"""
    test_url = (
        "https://custom-scripts.sentinel-hub.com/custom-scripts/"
        + "sentinel-2/true_color/script.js"
    )
    return test_url


@pytest.fixture(scope="session")
def test_collection():
    """Set a test data collection"""
    test_collection = "SENTINEL2_L2A"
    return test_collection


@pytest.fixture(scope="session")
def test_bounding_box():
    """Set a test footprint area (bounding box)"""
    test_bounding_box = [-51.13, 69.204, -51.06, 69.225]
    return test_bounding_box


@pytest.fixture(scope="session")
def test_area_name():
    """Set a test area available as geojson file"""
    test_area_name = "Ilulissat"
    return test_area_name


@pytest.fixture(scope="session")
def t1(authfile, test_evalscript, test_collection, test_bounding_box):
    """Set a test query with default parameters"""
    t1 = es.EarthSpy(authfile)
    t1.set_query_parameters(
        bounding_box=test_bounding_box,
        time_interval=["2019-08-23"],
        evaluation_script=test_evalscript,
        data_collection=test_collection,
        download_mode="SM",
    )
    return t1


@pytest.fixture(scope="session")
def t2(authfile, test_evalscript, test_collection, test_area_name):
    """Set a test query with area name"""
    t2 = es.EarthSpy(authfile)
    t2.set_query_parameters(
        bounding_box=test_area_name,
        time_interval=["2019-08-23"],
        evaluation_script=test_evalscript,
        data_collection=test_collection,
        download_mode="SM",
    )
    return t2


@pytest.fixture(scope="session")
def t3(authfile, test_evalscript, test_collection, test_bounding_box):
    """Set a test query with direct download mode"""
    t3 = es.EarthSpy(authfile)
    t3.set_query_parameters(
        bounding_box=test_bounding_box,
        time_interval=["2019-08-23"],
        evaluation_script=test_evalscript,
        data_collection=test_collection,
        download_mode="D",
    )
    return t3


@pytest.fixture(scope="session")
def t4(authfile, test_evalscript, test_collection, test_bounding_box):
    """Set a test query with LZW raster compression"""
    t4 = es.EarthSpy(authfile)
    t4.set_query_parameters(
        bounding_box=test_bounding_box,
        time_interval=["2019-08-23"],
        evaluation_script=test_evalscript,
        data_collection=test_collection,
        download_mode="SM",
        raster_compression="LZW",
    )
    return t4
