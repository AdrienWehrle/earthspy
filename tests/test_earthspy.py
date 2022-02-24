#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

@author: Adrien Wehrlé, EO-IO, University of Zurich, Switzerland

"""

import earthspy as es
import sentinelhub as shb

class TestEarthspy:

    def test_init(self) -> None:
        """Test successful auth.txt parsing and connection configuration.

        """
        self.t = es.EarthSpy('./auth_test.txt')

        assert self.t.CLIENT_ID == 'test_username'
        assert self.t.CLIENT_SECRET == 'test_password'

        assert isinstance(self.t.config, shb.config.SHConfig)
        assert self.t.config.sh_client_id == 'test_username'

        return None

    def test_set_query_parameters(self) -> None:
        """Test that direct attribute assignenent is successful.
        """
        s2_evalscript = """
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

        sentinel2_collection = "SENTINEL2_L2A"
        
        self.t.set_query_parameters(bounding_box=[-51.13, 69.204, -51.06, 69.225],
                                    time_interval=['2019-08-23'],
                                    evaluation_script=s2_evalscript,
                                    data_collection=sentinel2_collection,
                                    download_mode='SM')
        
        assert self.t.download_mode is not None
        assert self.t.verbose
        assert self.t.data_collection == sentinel2_collection

        return None

    def 
        
