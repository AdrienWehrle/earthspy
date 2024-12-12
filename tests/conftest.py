#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, University of Zurich, Switzerland

"""

import earthspy.earthspy as es
import pytest
import os

def pytest_addoption(parser):
    parser.addoption("--filepath", action="store", default="test")
    

if os.getenv("CI") is not None:    
    # create local variables from environment secrets for convenience
    SH_CLIENT_ID = os.environ["SH_CLIENT_ID"]
    SH_CLIENT_SECRET = os.environ["SH_CLIENT_SECRET"]
    
    # path to credential file to be created
    filepath = "auth.txt"
    
    # create file containing credentials for testing
    with open(filepath, "w") as out:
        out.write(f"{SH_CLIENT_ID}\n{SH_CLIENT_SECRET}")
else:
    @pytest.fixture(scope="session")
    def filepath(pytestconfig):
        return pytestconfig.getoption("filepath")
    
    @pytest.fixture(scope="session")
    def credentials(filepath):
        # read credentials stored in text file
        with open(filepath) as file:
            credentials = file.read().splitlines()
        return credentials
        
    @pytest.fixture(scope="session")
    def SH_CLIENT_ID(credentials) -> None: 
        # extract credentials from lines
        SH_CLIENT_ID = credentials[0]
        return SH_CLIENT_ID
    
    @pytest.fixture(scope="session")
    def SH_CLIENT_SECRET(credentials) -> None:
        SH_CLIENT_SECRET = credentials[1]
        return SH_CLIENT_SECRET


      
@pytest.fixture(scope="session")
def test_evalscript():
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
    test_url = (
        "https://custom-scripts.sentinel-hub.com/custom-scripts/"
        + "sentinel-2/true_color/script.js"
    )
    return test_url

@pytest.fixture(scope="session")
def test_collection():  
    # an example of data collection
    test_collection = "SENTINEL2_L2A"
    return test_collection
    
@pytest.fixture(scope="session")
def test_bounding_box():  
    # an example of footprint area
    test_bounding_box = [-51.13, 69.204, -51.06, 69.225]
    return test_bounding_box
    
@pytest.fixture(scope="session")
def test_area_name():  
    # an example of area available as GEOJSON file
    test_area_name = "Ilulissat"
    return test_area_name

@pytest.fixture(scope="session")
def t1(filepath, test_evalscript, test_collection, test_bounding_box):
    # example of query with default parameters
    t1 = es.EarthSpy(filepath)
    t1.set_query_parameters(
        bounding_box=test_bounding_box,
        time_interval=["2019-08-23"],
        evaluation_script=test_evalscript,
        data_collection=test_collection,
        download_mode="SM",
    )
    return t1

@pytest.fixture(scope="session")
def t2(filepath, test_evalscript, test_collection, test_area_name):
    # example of query with direct area name
    t2 = es.EarthSpy(filepath)
    t2.set_query_parameters(
        bounding_box=test_area_name,
        time_interval=["2019-08-23"],
        evaluation_script=test_evalscript,
        data_collection=test_collection,
        download_mode="SM",
    )
    return t2

@pytest.fixture(scope="session")
def t3(filepath, test_evalscript, test_collection, test_bounding_box):
    # example of query with direct mode
    t3 = es.EarthSpy(filepath)
    t3.set_query_parameters(
        bounding_box=test_bounding_box,
        time_interval=["2019-08-23"],
        evaluation_script=test_evalscript,
        data_collection=test_collection,
        download_mode="D",
    )
    return t3

@pytest.fixture(scope="session")
def t4(filepath, test_evalscript, test_collection, test_bounding_box):
    # example of query with direct mode
    t4 = es.EarthSpy(filepath)
    t4.set_query_parameters(
        bounding_box=test_bounding_box,
        time_interval=["2019-08-23"],
        evaluation_script=test_evalscript,
        data_collection=test_collection,
        download_mode="SM",
        raster_compression="LZW",
    )
    return t4
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    