#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, University of Zurich, Switzerland

"""

import earthspy.earthspy as es

# %% set example evalscript and bounding box

ex_evalscript = """
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

ex_collection = "SENTINEL2_L2A"

ex_bounding_box = [-51.13, 69.204, -51.06, 69.225]

# %% setup SentinelHub connection

# assume auth.txt is in root directory
job = es.EarthSpy('../../auth.txt')

# download all images available between 3 days ago and today
job.set_query_parameters(bounding_box=ex_bounding_box,
                         time_interval=-3,
                         evaluation_script=ex_evalscript,
                         data_collection='SENTINEL1_EW',
                         download_mode='SM')

# send request
job.send_sentinelhub_requests()

